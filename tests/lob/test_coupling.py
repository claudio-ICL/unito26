"""The CKS placement and the geometric placement of one order flow, on the same events.

Both placements read one recorded path, so whatever separates their books is the placement
and nothing else.  Before ``chi`` the two books have the same best prices, and at ``chi``
exactly one of them differs.
"""

import dataclasses

import numpy as np
import pytest

from unito26.lob import config
from unito26.lob.coupling import (
    CoupledFlows,
    Mover,
    Parting,
    PlacementStatistics,
    RecordedEvents,
    SizeUnit,
    VarianceRates,
    cks_first_move,
    cks_mids,
    cks_touch_walks,
    closed_form_rates,
    diffusive_scale,
    distance_terms,
    first_price_discrepancy,
    first_price_moves,
    fluid_emptying_time,
    fluid_touch,
    hawkes_mids,
    second_regime_rate,
    side_vector,
    touch_walks,
    variance_split,
)
from unito26.lob.hawkes import Clock, ExponentialHawkes, decayed_counts_at
from unito26.lob.idealised import AssumptionBreach, UniformDepth, idealised_book
from unito26.lob.messages import BUY, SELL, GridDepth
from unito26.lob.orderbook import AggregateBook
from unito26.lob.simulate import EventJournal, EventType, MarkParams, OrderFlowSimulator
from unito26.lob.visualization import (
    CKS_COLOUR,
    HAW_1_COLOUR,
    HAW_Q_COLOUR,
    discrepancy_fan_figure,
    distance_terms_figure,
    first_times_figure,
    mids_figure,
    touch_walks_figure,
    variance_split_figure,
)

DEPTH = UniformDepth(5)
LEVELS = GridDepth(60)
NARROW = {BUY: (1000, 3), SELL: (1001, 3)}
BALANCED = config.balanced_order_flow_params()
UNIT = config.unit_mark_params()
UNCERTAIN = config.uncertain_size_mark_params()
ONE = SizeUnit(1)
MBAR = config.uncertain_size_unit()
#: haw-1 and haw-q.
FLOWS = [(UNIT, ONE), (UNCERTAIN, MBAR)]
PRESSURE = np.array([event.pressure for event in EventType], dtype=float)
PRICES = ["CKSBidPrice1", "CKSAskPrice1", "HawBidPrice1", "HawAskPrice1"]


class Scripted:
    """A source of events in the place of a Hawkes process, for the corner cases."""

    params = BALANCED

    def __init__(self, events):
        self._events = [(float(time), int(event)) for time, event in events]

    def events(self, horizon):
        yield from ((time, event) for time, event in self._events if time <= horizon)


def scripted(*events, horizon=10.0):
    """The events at times 1, 2, 3, ..."""
    return RecordedEvents.drawn(
        Scripted([(k + 1, event) for k, event in enumerate(events)]), horizon
    )


def drawn(seed, horizon=20.0):
    return RecordedEvents.drawn(ExponentialHawkes(BALANCED, rng=seed), horizon)


def scaled(book: AggregateBook, unit: int) -> AggregateBook:
    return AggregateBook.from_levels(
        *({price: size * unit for price, size in book.levels_map(side).items()}
          for side in (BUY, SELL))
    )


class TestTheSimulatorStream:
    def test_a_seeded_stream_is_unchanged(self):
        """Pinned from the simulator as it stood before a source could be passed to it."""
        simulator = OrderFlowSimulator(
            config.resilient_order_flow_params(), config.resilient_mark_params(), 1000, rng=7
        )
        book = AggregateBook()
        messages = []
        for message in simulator.stream(book, 2.0, None):
            book.apply(message, record=False)
            messages.append(message)
        assert len(messages) == 35
        assert messages[0].time == 0.3166946183220538
        assert [(m.size, m.price, m.direction, int(m.kind)) for m in messages[:8]] == [
            (60, 1012, -1, 1), (10, 1012, -1, 2), (20, 1000, -1, 1), (40, 1005, -1, 1),
            (60, 1003, -1, 1), (50, 1010, -1, 1), (20, 1003, -1, 2), (110, 0, -1, 1),
        ]

    def test_driven_by_a_source_the_events_are_the_source_s(self):
        events = RecordedEvents.drawn(
            ExponentialHawkes(config.resilient_order_flow_params(), rng=3), 20.0
        )
        times = []
        for seed in (0, 1):
            simulator = OrderFlowSimulator.driven_by(
                events.replay(), config.resilient_mark_params(), 1000, seed
            )
            journal = EventJournal.empty()
            book = AggregateBook()
            for message in simulator.stream(book, events.horizon, journal):
                book.apply(message, record=False)
            assert np.array_equal(journal.types, events.types)
            times.append(journal.times)
        assert np.array_equal(times[0], events.times) and np.array_equal(times[1], events.times)


class TestRecordedEvents:
    def test_the_path_is_the_process_s(self):
        events = drawn(5)
        direct = list(ExponentialHawkes(BALANCED, rng=5).events(20.0))
        assert len(events) == len(direct) > 100
        assert np.array_equal(events.times, [time for time, _ in direct])
        assert np.array_equal(events.types, [event for _, event in direct])

    def test_a_replay_yields_exactly_the_recorded_path(self):
        events = drawn(5)
        replayed = list(events.replay().events(events.horizon))
        assert np.array_equal([time for time, _ in replayed], events.times)
        assert np.array_equal([event for _, event in replayed], events.types)
        assert all(type(time) is float and type(event) is int for time, event in replayed)

    def test_a_second_call_continues_from_the_first(self):
        events = drawn(5)
        replay = events.replay()
        first = list(replay.events(7.0))
        second = list(replay.events(events.horizon))
        assert first and all(time <= 7.0 for time, _ in first)
        assert np.array_equal([time for time, _ in first + second], events.times)

    def test_two_replays_are_independent(self):
        events = drawn(5)
        one, other = events.replay(), events.replay()
        list(one.events(events.horizon))
        assert len(list(other.events(events.horizon))) == len(events)

    def test_a_horizon_past_the_recorded_one_is_refused(self):
        events = drawn(5)
        with pytest.raises(ValueError, match="recorded to 20.0"):
            next(events.replay().events(21.0))

    def test_the_head_is_the_path_to_its_last_event(self):
        events = drawn(5)
        head = events.head(10)
        assert head.horizon == events.times[9]
        assert len(list(head.replay().events(head.horizon))) == 10
        assert len(events.head(0)) == 0 and events.head(0).horizon == 0.0

    def test_a_cut_path_moves_the_clock_to_the_cut(self):
        events = drawn(5)
        cut = events.after(7.5)
        kept = events.times > 7.5
        assert np.array_equal(cut.times, events.times[kept] - 7.5)
        assert np.array_equal(cut.types, events.types[kept])
        assert cut.horizon == events.horizon - 7.5

    def test_the_state_after_a_time_is_the_decayed_count_with_the_event_at_it(self):
        events = drawn(5)
        between = 0.5 * (events.times[40] + events.times[41])
        left = decayed_counts_at(BALANCED.decay, events.times, events.types, np.zeros(6),
                                 Clock(np.array([between, events.times[41]])))
        assert events.state_after(between) == pytest.approx(left[0])
        jump = np.eye(6)[events.types[41]]
        assert events.state_after(events.times[41]) == pytest.approx(left[1] + jump)


class TestTheFrozenRecords:
    def test_each_reserialises_to_its_frozen_records(self):
        assert BALANCED.to_records() == config.BALANCED_ORDER_FLOW_PARAMS
        assert UNIT.to_records() == config.UNIT_MARK_PARAMS
        assert UNCERTAIN.to_records() == config.UNCERTAIN_SIZE_MARK_PARAMS
        for marks in (UNIT, UNCERTAIN):
            assert MarkParams.from_json(marks.to_json(2)) == marks

    def test_the_balanced_flow_is_the_documented_one(self):
        stationary = BALANCED.stationary_intensity()
        assert stationary == pytest.approx([1.0, 1.0, 2.5, 2.5, 1.5, 1.5], abs=1e-8)
        limit, market, withdrawal = stationary[2:4], stationary[:2], stationary[4:]
        assert limit == pytest.approx(market + withdrawal, abs=1e-8)
        assert BALANCED.branching_ratio == pytest.approx(0.5, abs=1e-8)
        assert np.all(BALANCED.baseline > 0)
        assert BALANCED.baseline[[0, 2, 4]] == pytest.approx([0.442, 0.521, 1.140], abs=5e-4)
        assert BALANCED.endogenous_fraction() == pytest.approx(0.579, abs=5e-4)

    def test_the_balanced_flow_keeps_the_resilient_shape(self):
        ratio = BALANCED.excitation / config.resilient_order_flow_params().excitation
        assert ratio == pytest.approx(np.full((6, 6), ratio[0, 0]))

    def test_the_balanced_flow_is_direction_symmetric(self):
        swap = np.zeros((6, 6))
        for i in range(0, 6, 2):
            swap[i, i + 1] = swap[i + 1, i] = 1.0
        assert np.allclose(swap @ BALANCED.excitation @ swap, BALANCED.excitation)
        assert np.allclose(swap @ BALANCED.baseline, BALANCED.baseline)

    def test_every_unit_size_is_one_share(self):
        simulator = OrderFlowSimulator(BALANCED, UNIT, 1000, rng=0)
        assert {simulator._size() for _ in range(20000)} == {1}

    def test_the_size_unit_is_the_mean_uncertain_size(self):
        mean = np.exp(UNCERTAIN.mean_log_size + UNCERTAIN.sigma_log_size ** 2 / 2)
        assert mean == pytest.approx(MBAR, rel=1e-10)
        assert UNCERTAIN.depth_decay == UNIT.depth_decay


class TestThePair:
    @pytest.mark.parametrize("marks, unit", FLOWS)
    def test_both_books_read_the_same_events(self, marks, unit):
        """The CKS contribution is the pressure of each event, Proposition
        ``prop.signedSizeContribution``; the Hawkes book is the simulator's, fold for fold."""
        events = drawn(1)
        pair = CoupledFlows.on(events, marks, unit, DEPTH, NARROW, LEVELS, 2)
        frame = pair.frame
        assert pair.breach is None and len(frame) == len(events)
        assert np.array_equal(frame["TimeStamp"], events.times)
        assert np.array_equal(frame["EventType"], events.types)
        assert np.array_equal(frame["CKSOrderFlowContribution"], PRESSURE[events.types])

        book = scaled(idealised_book(DEPTH, NARROW, LEVELS), unit)
        journal = EventJournal.empty()
        simulator = OrderFlowSimulator.driven_by(events.replay(), marks, 1000, 2)
        bids = []
        for message in simulator.stream(book, events.horizon, journal):
            book.apply(message, record=False)
            bids.append((book.best_bid_price, book.best_bid_size / unit))
        assert np.array_equal(journal.types, events.types) and journal.dropped == 0
        assert bids == list(zip(frame["HawBidPrice1"], frame["HawBidSize1"]))
        last = pair.hawkes_depth.iloc[-1]
        assert last[last > 0].to_dict() == {p: s / unit for p, s in book.bids.items()}

    @pytest.mark.parametrize("marks, unit", FLOWS)
    def test_the_touches_are_the_best_levels_of_the_depth(self, marks, unit):
        pair = CoupledFlows.on(drawn(3), marks, unit, DEPTH, NARROW, LEVELS, 4)
        for prefix, depth in (("CKS", pair.cks_depth), ("Haw", pair.hawkes_depth)):
            prices = depth.columns.to_numpy()
            bid = np.where(depth > 0, prices, -np.inf).max(axis=1)
            ask = np.where(depth < 0, prices, np.inf).min(axis=1)
            assert np.array_equal(bid, pair.frame[f"{prefix}BidPrice1"])
            assert np.array_equal(ask, pair.frame[f"{prefix}AskPrice1"])
            rows = np.arange(len(depth))
            at_bid = depth.to_numpy()[rows, np.searchsorted(prices, bid)]
            assert at_bid == pytest.approx(pair.frame[f"{prefix}BidSize1"].to_numpy())

    def test_in_units_the_hawkes_book_opens_as_the_cks_one(self):
        pair = CoupledFlows.on(scripted(EventType.LIMIT_BUY), UNCERTAIN, MBAR, DEPTH, NARROW,
                               LEVELS, 0)
        cks, hawkes = pair.cks_depth.loc[0], pair.hawkes_depth.loc[0]
        assert hawkes[hawkes < 0].to_dict() == cks[cks < 0].to_dict()
        assert hawkes[1001] == -3 and hawkes[1002] == -DEPTH and len(hawkes[hawkes < 0]) == LEVELS


class TestTheParting:
    @pytest.mark.parametrize("marks, unit", FLOWS + [(MarkParams(0.6, 0.0, 0.01, 1), ONE)])
    def test_chi_is_the_first_event_at_which_the_mids_differ_and_one_best_price_does(
        self, marks, unit
    ):
        for seed in range(6):
            events = drawn(seed, horizon=10.0)
            pair = CoupledFlows.on(events, marks, unit, DEPTH, NARROW, LEVELS, seed)
            prices = pair.frame[PRICES].to_numpy()
            differ = prices[:, :2] != prices[:, 2:]
            mids = pair.frame["CKSMidPrice"] != pair.frame["HawMidPrice"]
            chi = pair.first_price_discrepancy
            assert mids.any() and chi == int(np.argmax(mids))
            assert not differ[:chi].any()
            assert differ[chi].sum() == 1
            parting = pair.parting
            assert parting.event == chi and parting.time == pair.first_price_discrepancy_time
            assert parting.side == (BUY if differ[chi, 0] else SELL)
            assert parting.event_type == EventType(int(events.types[chi]))
            assert first_price_discrepancy(events, marks, unit, DEPTH, NARROW, LEVELS,
                                           seed) == parting

    @pytest.mark.parametrize("marks, unit", FLOWS)
    def test_the_discrepancy_is_zero_before_chi(self, marks, unit):
        for seed in range(4):
            pair = CoupledFlows.on(drawn(seed), marks, unit, DEPTH, NARROW, LEVELS, seed)
            chi = pair.first_price_discrepancy
            discrepancy = pair.frame["CKSMidPrice"] - pair.frame["HawMidPrice"]
            assert (discrepancy.iloc[:chi] == 0).all() and discrepancy.iloc[chi] != 0
            assert not pair.frame["MidsDiffer"].iloc[:chi].any()

    def test_at_one_tick_with_touches_of_two_shares_no_event_moves_a_mid(self):
        """Every event takes or adds one share; one tick from the opposite touch a limit
        order joins its touch or rests behind it, and a touch of two survives a share."""
        events = scripted(
            EventType.LIMIT_BUY, EventType.MARKET_SELL, EventType.WITHDRAW_BUY,
            EventType.LIMIT_SELL, EventType.MARKET_BUY, EventType.WITHDRAW_SELL,
            EventType.LIMIT_BUY, EventType.LIMIT_SELL,
        )
        opening = {BUY: (1000, 4), SELL: (1001, 4)}
        marks = MarkParams(0.5, 0.0, 0.01, 1)
        for seed in range(10):
            pair = CoupledFlows.on(events, marks, ONE, DEPTH, opening, LEVELS, seed)
            sizes = pair.frame[["CKSBidSize1", "CKSAskSize1", "HawBidSize1", "HawAskSize1"]]
            assert (sizes >= 2).all().all()
            for prefix in ("CKS", "Haw"):
                assert (pair.frame[f"{prefix}MidPrice"] == 1000.5).all()
            assert pair.parting is None
            assert first_price_discrepancy(events, marks, ONE, DEPTH, opening, LEVELS,
                                           seed) is None

    def test_a_market_order_clearing_a_cks_touch_of_one_share_is_the_parting(self):
        """In units of two shares the Hawkes ask holds one unit, two shares, and a market buy
        of one share leaves half of it; the limit buy before acts on the bid alone."""
        events = scripted(EventType.LIMIT_BUY, EventType.MARKET_BUY)
        opening = {BUY: (1000, 3), SELL: (1001, 1)}
        unit = SizeUnit(2)
        pair = CoupledFlows.on(events, UNIT, unit, DEPTH, opening, LEVELS, 0)
        expected = Parting(1, 2.0, EventType.MARKET_BUY, Mover.CKS, SELL)
        assert pair.parting == expected
        assert first_price_discrepancy(events, UNIT, unit, DEPTH, opening, LEVELS, 0) == expected
        frame = pair.frame
        assert not frame.loc[0, "MidsDiffer"]
        assert list(frame.loc[1, ["CKSAskPrice1", "CKSAskSize1"]]) == [1002, DEPTH]
        assert list(frame.loc[1, ["HawAskPrice1", "HawAskSize1"]]) == [1001, 0.5]
        assert frame.loc[1, "CKSMidPrice"] - frame.loc[1, "HawMidPrice"] == 0.5


class TestTheStop:
    def test_an_event_that_would_empty_a_cks_side_stops_the_pair_before_it(self):
        events = scripted(EventType.LIMIT_BUY, EventType.MARKET_BUY, EventType.LIMIT_SELL)
        opening = {BUY: (1000, 3), SELL: (1001, 1)}
        pair = CoupledFlows.on(events, UNIT, ONE, DEPTH, opening, GridDepth(1), 0)
        assert isinstance(pair.breach, AssumptionBreach)
        assert str(pair.breach).startswith("CKS book: at 2.000000 s the ask side")
        assert len(pair.events) == len(pair.frame) == len(pair.cks_depth) == 1
        with pytest.raises(AssumptionBreach, match="CKS book"):
            first_price_discrepancy(events, UNIT, ONE, DEPTH, opening, GridDepth(1), 0)

    def test_an_emptied_side_of_the_hawkes_book_stops_the_pair_before_the_event(self):
        """A market sell of fifty shares takes the whole bid of ten."""
        marks = MarkParams(0.2, np.log(50.0), 0.01, 1)
        events = scripted(EventType.LIMIT_SELL, EventType.MARKET_SELL, EventType.LIMIT_BUY)
        opening = {BUY: (1000, 5), SELL: (1001, 5)}
        pair = CoupledFlows.on(events, marks, ONE, DEPTH, opening, GridDepth(2), 0)
        assert str(pair.breach) == "Hawkes book: at 2.000000 s the bid side empties"
        assert len(pair.frame) == len(pair.hawkes_depth) == 1

    def test_the_cks_mid_is_nan_from_a_breach_on(self):
        events = scripted(EventType.LIMIT_BUY, EventType.MARKET_BUY, EventType.LIMIT_SELL)
        opening = {BUY: (1000, 3), SELL: (1001, 1)}
        clock = Clock(np.array([0.5, 1.0, 1.9, 2.0, 5.0]))
        mids = cks_mids(events, DEPTH, opening, GridDepth(1), clock)
        assert list(mids[:3]) == [1000.5] * 3 and np.isnan(mids[3:]).all()

    def test_the_hawkes_mid_is_nan_while_a_side_is_empty(self):
        """The market sell leaves its remainder of forty at the last bid, as an ask; the
        limit buy after it is priced against that ask."""
        marks = MarkParams(1.0, np.log(50.0), 0.01, 1)
        events = scripted(EventType.MARKET_SELL, EventType.LIMIT_BUY)
        opening = {BUY: (1000, 5), SELL: (1001, 5)}
        clock = Clock(np.array([0.5, 1.0, 1.5, 2.0]))
        mids = hawkes_mids(events, marks, ONE, DEPTH, opening, GridDepth(2), clock, 0)
        assert mids[0] == 1000.5 and np.isnan(mids[1:3]).all() and mids[3] == 998.5


class TestTheFirstMoves:
    @pytest.mark.parametrize("marks, unit", FLOWS)
    def test_they_are_the_first_rows_at_which_each_book_s_prices_leave_the_opening(
        self, marks, unit
    ):
        for seed in range(4):
            events = drawn(seed)
            pair = CoupledFlows.on(events, marks, unit, DEPTH, NARROW, LEVELS, seed)
            prices = pair.frame[PRICES].to_numpy()
            moved = prices != [1000, 1001, 1000, 1001]
            assert moved[:, :2].any() and moved[:, 2:].any()
            cks = int(np.argmax(moved[:, :2].any(axis=1)))
            hawkes = int(np.argmax(moved[:, 2:].any(axis=1)))
            moves = first_price_moves(events, marks, unit, DEPTH, NARROW, LEVELS, seed)
            assert (moves.cks, moves.hawkes) == (cks, hawkes)
            assert (moves.cks_time, moves.hawkes_time) == (events.times[cks],
                                                           events.times[hawkes])

    def test_the_cks_move_is_a_function_of_the_path(self):
        events = drawn(2)
        moves = {first_price_moves(events, marks, unit, DEPTH, NARROW, LEVELS, seed).cks
                 for marks, unit in FLOWS for seed in range(3)}
        assert len(moves) == 1

    def test_a_book_that_never_moves_has_none(self):
        moves = first_price_moves(scripted(EventType.LIMIT_BUY), UNIT, ONE, DEPTH, NARROW,
                                  LEVELS, 0)
        assert (moves.cks, moves.hawkes, moves.cks_time, moves.hawkes_time) == (None,) * 4

    @pytest.mark.parametrize("marks, unit", FLOWS)
    def test_the_walks_are_the_touch_sizes_to_each_move(self, marks, unit):
        events = drawn(3)
        pair = CoupledFlows.on(events, marks, unit, DEPTH, NARROW, LEVELS, 1)
        moves = first_price_moves(events, marks, unit, DEPTH, NARROW, LEVELS, 1)
        walks = touch_walks(events, marks, unit, DEPTH, NARROW, LEVELS, 1)
        assert len(walks) == max(moves.cks, moves.hawkes) + 2
        assert walks.index[0] == 0.0 and np.array_equal(walks.index[1:],
                                                        events.times[:len(walks) - 1])
        assert list(walks.iloc[0]) == [3.0, 3.0, 3.0, 3.0]
        for prefix, move in (("CKS", moves.cks), ("Haw", moves.hawkes)):
            for side in ("BidSize1", "AskSize1"):
                walk = walks[f"{prefix}{side}"].to_numpy()
                assert np.array_equal(walk[1:move + 1], pair.frame[f"{prefix}{side}"][:move])
                assert np.isnan(walk[move + 1:]).all()


class TestTheMidsOnAClock:
    @pytest.mark.parametrize("marks, unit", FLOWS)
    def test_they_are_the_pair_s_at_every_event(self, marks, unit):
        events = drawn(4)
        pair = CoupledFlows.on(events, marks, unit, DEPTH, NARROW, LEVELS, 1)
        clock = Clock(events.times)
        assert np.array_equal(cks_mids(events, DEPTH, NARROW, LEVELS, clock),
                              pair.frame["CKSMidPrice"])
        assert np.array_equal(
            hawkes_mids(events, marks, unit, DEPTH, NARROW, LEVELS, clock, 1),
            pair.frame["HawMidPrice"],
        )

    def test_a_time_before_the_first_event_reads_the_opening_book(self):
        events = drawn(4)
        clock = Clock(np.array([0.0, events.times[0] / 2]))
        assert list(cks_mids(events, DEPTH, NARROW, LEVELS, clock)) == [1000.5, 1000.5]
        mids = hawkes_mids(events, UNCERTAIN, MBAR, DEPTH, NARROW, LEVELS, clock, 1)
        assert list(mids) == [1000.5, 1000.5]


class TestTheVarianceSplit:
    def test_the_parts_add_up_to_the_total_on_the_sample(self):
        sample = np.random.default_rng(0).standard_t(3, size=(7, 5, 11))
        split = variance_split(sample)
        assert len(split) == 11
        assert np.array_equal(split["Total"], split["FlowPart"] + split["PlacementPart"])
        assert split["Mean"].to_numpy() == pytest.approx(sample.mean(axis=(0, 1)))
        assert split["StandardError"].to_numpy() == pytest.approx(
            sample.mean(axis=1).std(axis=0, ddof=1) / np.sqrt(7)
        )

    def test_a_known_split_is_recovered_in_expectation(self):
        """``D = a + b``, ``a`` drawn once per path with variance 1 and ``b`` once per run
        with variance 4, on five paths of three seeds.  Each time is an independent
        replication, so the mean over times is the expectation of each estimate.  The
        population variances would give ``4/5 (1 + 4/3)`` and ``2/3 * 4``."""
        rng = np.random.default_rng(2)
        paths, seeds, replications = 5, 3, 20_000
        sample = (rng.normal(0, 1, size=(paths, 1, replications))
                  + rng.normal(0, 2, size=(paths, seeds, replications)))
        split = variance_split(sample).mean()
        assert split["FlowPart"] == pytest.approx(1.0, abs=0.05)
        assert split["PlacementPart"] == pytest.approx(4.0, abs=0.05)
        assert split["Total"] == pytest.approx(5.0, abs=0.07)

    def test_the_flow_part_can_be_negative(self):
        """Seed terms alone, with the path means close together by chance."""
        sample = np.array([[[1.0], [-1.0]], [[2.0], [-2.0]]])
        split = variance_split(sample)
        assert split["PlacementPart"].iloc[0] == pytest.approx(5.0)
        assert split["FlowPart"].iloc[0] == pytest.approx(-2.5)


class TestTheDistance:
    @pytest.mark.parametrize("marks, unit", FLOWS + [(MarkParams(0.6, 0.0, 0.01, 1), ONE)])
    def test_the_three_terms_add_up_to_the_distance(self, marks, unit):
        pair = CoupledFlows.on(drawn(2, horizon=40.0), marks, unit, DEPTH, NARROW, LEVELS, 3)
        terms = distance_terms(pair)
        assert terms["Distance"].to_numpy() == pytest.approx(
            (terms["ImbalanceMismatch"] - terms["TouchSizeMismatch"]
             - terms["DepthMismatch"]).to_numpy(), abs=1e-9
        )
        assert (terms["Distance"] != 0).any()
        assert (terms["CKSDepthMismatch"] == 0).all()

    def test_the_imbalances_are_the_frame_s(self):
        pair = CoupledFlows.on(drawn(2), UNCERTAIN, MBAR, DEPTH, NARROW, LEVELS, 3)
        terms = distance_terms(pair)
        flow = (pair.frame["CKSOrderFlowContribution"]
                - pair.frame["HawOrderFlowContribution"]).to_numpy()
        assert terms["ImbalanceMismatch"].to_numpy() == pytest.approx(np.cumsum(flow))


class TestTheSideVectors:
    def test_they_differ_by_the_pressure(self):
        assert np.array_equal(side_vector(BUY) - side_vector(SELL), PRESSURE)

    def test_with_orders_of_one_share_a_side_of_the_hawkes_book_is_its_walk(self):
        """Eq. (1.1): a withdrawal from an occupied side removes one share wherever it is
        drawn, so the whole side is its opening size plus ``(u^d)' N``."""
        events = drawn(1, horizon=60.0)
        pair = CoupledFlows.on(events, UNIT, ONE, DEPTH, NARROW, LEVELS, 2)
        depth = pair.hawkes_depth.to_numpy()
        opening = 3 + DEPTH * (LEVELS - 1)
        for direction, sign in ((BUY, 1), (SELL, -1)):
            side = np.where(sign * depth > 0, sign * depth, 0.0).sum(axis=1)
            walk = opening + np.cumsum(side_vector(direction)[events.types])
            assert np.array_equal(side, walk)


#: Scripted paths and the opening each is read from, ``Sbar`` being five.
WALKS = [
    ((EventType.LIMIT_BUY,) * 5, {BUY: (1000, 5), SELL: (1001, 5)}),
    ((EventType.MARKET_SELL,) * 3, NARROW),
    ((EventType.LIMIT_BUY, EventType.LIMIT_BUY, EventType.LIMIT_BUY,
      EventType.WITHDRAW_SELL, EventType.MARKET_BUY), NARROW),
    ((EventType.LIMIT_SELL, EventType.LIMIT_SELL, EventType.LIMIT_SELL, EventType.LIMIT_SELL,
      EventType.WITHDRAW_BUY, EventType.LIMIT_BUY, EventType.MARKET_SELL,
      EventType.MARKET_SELL, EventType.MARKET_SELL), {BUY: (1000, 4), SELL: (1001, 2)}),
    ((EventType.LIMIT_BUY, EventType.MARKET_BUY, EventType.WITHDRAW_BUY), NARROW),
]


class TestTheCKSTouchWalks:
    @pytest.mark.parametrize("types, opening", WALKS)
    def test_the_drawdown_is_the_first_move_of_the_folded_book_on_scripted_paths(
        self, types, opening
    ):
        events = scripted(*types, horizon=20.0)
        folded = first_price_moves(events, UNIT, ONE, DEPTH, opening, LEVELS, 0).cks
        assert cks_first_move(events, DEPTH, opening) == folded

    def test_the_scripted_moves_are_the_ones_worked_by_hand(self):
        moves = [cks_first_move(scripted(*types), DEPTH, opening) for types, opening in WALKS]
        assert moves == [4, 2, 4, 8, None]

    @pytest.mark.parametrize("opening", [NARROW, {BUY: (1000, 5), SELL: (1001, 5)}])
    def test_the_drawdown_is_the_first_move_of_the_folded_book_on_drawn_paths(self, opening):
        for seed in range(12):
            events = drawn(seed, horizon=60.0)
            folded = first_price_moves(events, UNIT, ONE, DEPTH, opening, LEVELS, seed).cks
            assert folded is not None
            assert cks_first_move(events, DEPTH, opening) == folded

    def test_before_the_move_the_walks_less_the_cap_are_the_folded_touches(self):
        for seed in range(6):
            events = drawn(seed, horizon=60.0)
            walks = cks_touch_walks(events, DEPTH, NARROW)
            folded = touch_walks(events, UNIT, ONE, DEPTH, NARROW, LEVELS, seed)
            move = cks_first_move(events, DEPTH, NARROW)
            assert len(walks) == move + 2
            assert np.array_equal(walks.index, folded.index[: move + 2])
            for side in ("CKSBidSize1", "CKSAskSize1"):
                assert np.array_equal(walks[side].iloc[:-1], folded[side].iloc[: move + 1])
            last = walks.iloc[-1]
            assert min(last["CKSBidSize1"], last["CKSAskSize1"]) == 0
            assert (walks["RunningMaximum"] >= DEPTH).all()


L = GridDepth(10)


def with_decay(depth_decay):
    return dataclasses.replace(UNIT, depth_decay=depth_decay)


class TestTheFluidTouch:
    @pytest.mark.parametrize("depth_decay", [0.1, 0.2, 0.35, 0.7])
    def test_it_solves_its_equation(self, depth_decay):
        market, limit, withdrawal = 1.0, 2.5, 1.5
        s = np.linspace(0.0, 4.0, 401)
        step = 1e-6
        r = fluid_touch(BALANCED, with_decay(depth_decay), L, s)
        slope = (fluid_touch(BALANCED, with_decay(depth_decay), L, s + step) - r) / step
        assert r[0] == pytest.approx(1.0, abs=1e-12)
        assert slope == pytest.approx(
            depth_decay * limit - market - withdrawal / L * r, abs=1e-5
        )

    @pytest.mark.parametrize("depth_decay", [0.1, 0.2, 0.3, 0.35])
    def test_in_the_first_regime_it_reaches_zero_at_s_star(self, depth_decay):
        s_star = fluid_emptying_time(BALANCED, with_decay(depth_decay), L)
        s = np.linspace(0.0, s_star, 200)
        r = fluid_touch(BALANCED, with_decay(depth_decay), L, s)
        assert r[-1] == pytest.approx(0.0, abs=1e-12) and (r[:-1] > 0).all()

    @pytest.mark.parametrize("depth_decay", [0.4, 0.5, 0.7, 1.0])
    def test_in_the_second_regime_it_stays_positive_and_s_star_is_infinite(self, depth_decay):
        assert fluid_emptying_time(BALANCED, with_decay(depth_decay), L) == np.inf
        r = fluid_touch(BALANCED, with_decay(depth_decay), L, np.geomspace(1e-3, 1e4, 50))
        assert (r > 0).all()
        assert r[-1] == pytest.approx(L * (depth_decay * 2.5 - 1.0) / 1.5, abs=1e-8)

    def test_the_base_case_is_the_documented_one(self):
        s_star = [fluid_emptying_time(BALANCED, with_decay(eta), L)
                  for eta in (0.1, 0.2, 0.3, 0.35)]
        assert s_star == pytest.approx([1.2155, 1.7491, 3.1334, 5.2564], abs=1e-4)
        assert diffusive_scale(BALANCED, UniformDepth(20)) == pytest.approx(134.0, abs=0.05)
        assert second_regime_rate(BALANCED, UniformDepth(20)) == pytest.approx(
            0.003635, abs=1e-6
        )


class TestTheClosedForm:
    def test_with_nothing_placed_at_the_touch_it_is_the_second_regime_rate(self):
        rate = second_regime_rate(BALANCED, DEPTH)
        for statistics in (
            PlacementStatistics(np.ones(6), np.inf),
            PlacementStatistics(np.array([0.0, 0.0, 0.7, 0.7, 0.9, 0.9]), np.inf),
            PlacementStatistics(np.ones(6), 12.0),
        ):
            for size_variance in (0.0, 0.896):
                rates = closed_form_rates(BALANCED, DEPTH, statistics, size_variance)
                assert rates.flow_part == pytest.approx(rate, rel=1e-12)
                assert rates.placement_part == 0.0
                assert rates.total == rates.flow_part

    def test_it_is_the_formula_of_the_approximation(self):
        """``approx.firstRegimeVariance`` written out, at ``alpha`` and ``S~`` of the order
        that the books of haw-1 give at ``eta = 0.2``."""
        alpha, depth = np.array([0, 0, 0.724, 0.724, 0.963, 0.963]), 9.4
        rates = closed_form_rates(BALANCED, UniformDepth(20), PlacementStatistics(alpha, depth),
                                  0.0)
        weighted = PRESSURE * (1 / 40 - (1 - alpha) / (2 * depth))
        assert rates.flow_part == pytest.approx(
            weighted @ BALANCED.count_covariance_rate() @ weighted
        )
        assert rates.placement_part == pytest.approx(
            alpha * (1 - alpha) @ BALANCED.stationary_intensity() / (2 * depth) ** 2
        )
        assert (rates.flow_part, rates.placement_part) == pytest.approx((0.0057, 0.0031),
                                                                        abs=1e-4)

    def test_the_size_term_is_var_xi_times_the_events_that_reach_the_touch(self):
        alpha = np.array([0.0, 0.0, 0.6, 0.6, 0.9, 0.9])
        statistics = PlacementStatistics(alpha, 8.0)
        with_sizes = closed_form_rates(BALANCED, DEPTH, statistics, 0.5)
        without = closed_form_rates(BALANCED, DEPTH, statistics, 0.0)
        term = 0.5 * (1 - alpha) @ BALANCED.stationary_intensity() / 16.0**2
        assert with_sizes.placement_part - without.placement_part == pytest.approx(term)
        assert with_sizes.flow_part == without.flow_part
        assert isinstance(with_sizes, VarianceRates)


class TestThePlacementStatistics:
    def test_the_fraction_behind_is_read_type_by_type(self):
        """At ``eta = 1`` a limit order rests one tick inside the opposite touch, which at a
        spread of one tick is its own; at ``eta = 1e-9`` it rests a billion ticks behind.  On
        a book of one level a side a withdrawal can only draw the touch."""
        one_level = GridDepth(1)
        at_the_touch = CoupledFlows.on(
            scripted(EventType.LIMIT_BUY, EventType.WITHDRAW_BUY, EventType.LIMIT_SELL,
                     EventType.WITHDRAW_SELL, EventType.MARKET_BUY),
            with_decay(1.0), ONE, DEPTH, NARROW, one_level, 0,
        )
        behind = CoupledFlows.on(
            scripted(EventType.LIMIT_BUY, EventType.LIMIT_SELL, EventType.LIMIT_BUY,
                     EventType.MARKET_SELL),
            with_decay(1e-9), ONE, DEPTH, NARROW, one_level, 0,
        )
        assert at_the_touch.breach is None and behind.breach is None
        statistics = PlacementStatistics.of([at_the_touch, behind])
        assert statistics.behind_probability == pytest.approx([0, 0, 2 / 3, 1 / 2, 0, 0])
        assert statistics.effective_depth == np.inf

    @staticmethod
    def depth_runs(marks, size_unit):
        """Orders of three units on levels of five.  From a bid of one and an ask of two the
        market sell takes the bid and two units behind it, leaving three at 999, ``e = -1``;
        the market buy takes the ask and one unit behind it, leaving four at 1002, ``e = 2``;
        the limit buy opens 1001, ``e = 3``.  So the imbalance is 4 and ``Pi`` is 2.  With the
        mirror image of that book and flow, the market sell alone, and a limit buy that joins
        the bid, ``(Pi, OFI)`` runs over ``(2, 4)``, ``(-2, -4)``, ``(-1, -1)`` and
        ``(0, 3)``."""
        bid_heavy = {BUY: (1000, 2), SELL: (1001, 1)}
        ask_heavy = {BUY: (1000, 1), SELL: (1001, 2)}
        runs = [
            (ask_heavy, (EventType.MARKET_SELL, EventType.MARKET_BUY, EventType.LIMIT_BUY)),
            (bid_heavy, (EventType.MARKET_BUY, EventType.MARKET_SELL, EventType.LIMIT_SELL)),
            (ask_heavy, (EventType.MARKET_SELL,)),
            (ask_heavy, (EventType.LIMIT_BUY,)),
        ]
        return [
            CoupledFlows.on(scripted(*events), marks, size_unit, DEPTH, touches, GridDepth(3), 0)
            for touches, events in runs
        ]

    def test_the_effective_depth_is_the_regression_of_the_imbalance_on_the_move(self):
        pairs = self.depth_runs(MarkParams(1.0, np.log(3.0), 0.01, 1), ONE)
        assert list(pairs[0].frame["HawBidPrice1"]) == [999, 999, 1001]
        assert list(pairs[0].frame["HawAskPrice1"]) == [1001, 1002, 1002]
        assert list(pairs[1].frame["HawBidPrice1"]) == [1000, 999, 999]
        assert list(pairs[1].frame["HawAskPrice1"]) == [1002, 1002, 1000]
        assert list(pairs[3].frame["HawBidPrice1"]) == [1000]
        statistics = PlacementStatistics.of(pairs)
        assert [pair.frame["HawOrderFlowContribution"].sum() for pair in pairs] == [4, -4, -1, 3]
        slope = np.polyfit([2, -2, -1, 0], [4, -4, -1, 3], 1)[0]
        assert statistics.effective_depth == pytest.approx(slope)
        assert statistics.behind_probability[EventType.LIMIT_BUY] == 0.0

    def test_the_effective_depth_is_read_in_units(self):
        in_shares = PlacementStatistics.of(
            self.depth_runs(MarkParams(1.0, np.log(3.0), 0.01, 1), ONE)
        )
        in_units = PlacementStatistics.of(
            self.depth_runs(MarkParams(1.0, np.log(6.0), 0.01, 1), SizeUnit(2))
        )
        assert in_units.effective_depth == pytest.approx(in_shares.effective_depth)


@pytest.fixture(scope="module")
def pairs():
    events = drawn(1)
    return {
        "haw-1": CoupledFlows.on(events, UNIT, ONE, DEPTH, NARROW, LEVELS, 2),
        "haw-q": CoupledFlows.on(events, UNCERTAIN, MBAR, DEPTH, NARROW, LEVELS, 2),
    }


class TestTheFigures:
    def test_the_mids_keep_one_colour_a_flow_and_mark_chi_for_each(self, pairs):
        figure = mids_figure(pairs, "")
        assert [trace.line.color for trace in figure.data] == [
            CKS_COLOUR, HAW_1_COLOUR, HAW_Q_COLOUR
        ]
        assert np.array_equal(figure.data[2].y, pairs["haw-q"].frame["HawMidPrice"])
        rules = sorted(shape.x0 for shape in figure.layout.shapes)
        assert rules == sorted(pair.first_price_discrepancy_time for pair in pairs.values())

    def test_the_walks_end_at_each_move(self):
        events = drawn(3)
        walks = touch_walks(events, UNIT, ONE, DEPTH, NARROW, LEVELS, 1)
        moves = first_price_moves(events, UNIT, ONE, DEPTH, NARROW, LEVELS, 1)
        figure = touch_walks_figure(walks, "haw-1", "")
        assert len(figure.data) == 4
        assert {trace.line.color for trace in figure.data} == {CKS_COLOUR, HAW_1_COLOUR}
        assert sorted({shape.x0 for shape in figure.layout.shapes}) == sorted(
            {moves.cks_time, moves.hawkes_time}
        )

    def test_the_first_times_fall_by_one_path_at_each_and_carry_the_curves(self):
        clock = np.geomspace(0.1, 10.0, 50)
        times = {row: {"a": {"haw-1": np.array([1.0, np.nan]), "haw-q": np.array([2.0, 3.0])},
                       "b": {"CKS": np.array([0.5, 0.5])}}
                 for row in ("one", "two")}
        predicted = {"one": {"a": {"formula": np.exp(-clock)}}}
        figure = first_times_figure(times, clock, predicted, "P(χ > t)", "")
        assert len(figure.data) == 2 * 3 + 1
        assert figure.data[0].y[np.searchsorted(clock, 1.0)] == 0.5
        assert sum(bool(trace.showlegend) for trace in figure.data) == 4
        assert figure.layout.xaxis.type == "log"

    def test_the_fan_draws_the_runs_shown_the_mean_and_a_band_of_one_sd(self):
        clock = np.arange(5.0)
        fan = np.random.default_rng(0).normal(size=(3, 4, 5))
        figure = discrepancy_fan_figure({"haw-1": fan, "haw-q": fan}, clock, 2, "")
        assert len(figure.data) == 2 * (2 + 2)
        runs = fan.reshape(-1, 5)
        band, mean = figure.data[2], figure.data[3]
        assert mean.y == pytest.approx(runs.mean(axis=0))
        assert band.y[:5] == pytest.approx(runs.mean(axis=0) + runs.std(axis=0))
        assert mean.line.color == HAW_1_COLOUR and figure.data[7].line.color == HAW_Q_COLOUR

    def test_the_split_has_a_panel_per_flow_and_room_for_a_prediction(self):
        clock = np.arange(11.0)
        split = variance_split(np.random.default_rng(0).normal(size=(6, 4, 11)))
        figure = variance_split_figure(
            {"haw-1": split, "haw-q": split}, clock, {"haw-q": {"predicted": clock}}, ""
        )
        assert len(figure.data) == 3 + 3 + 1
        assert np.array_equal(figure.data[0].y, split["Total"])
        assert sum(bool(trace.showlegend) for trace in figure.data) == 4

    def test_the_distance_figure_draws_the_terms_as_they_enter(self, pairs):
        terms = distance_terms(pairs["haw-q"])
        distance, imbalance, sizes, depth = distance_terms_figure(terms, "").data
        assert np.asarray(distance.y) == pytest.approx(imbalance.y + sizes.y + depth.y)
