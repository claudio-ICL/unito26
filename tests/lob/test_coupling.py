"""The idealised and the geometric placement of one order flow, on the same events.

Both placements read one recorded path, so whatever separates their books is the placement
and nothing else.  Where the two placements send the same orders the sessions coincide row
for row; the first order they send differently is the first discrepancy.
"""

import numpy as np
import pandas as pd
import pytest

from unito26.lob import config
from unito26.lob.coupling import (
    CoupledPlacements,
    RecordedEvents,
    agreement_probability,
    conditional_survival,
    first_discrepancy,
    distance_terms,
    limit_event_outcomes,
    geometric_mid_moves,
    geometric_readings,
    idealised_readings,
    target_offsets,
    touch_shares,
    touch_walk_exit,
)
from unito26.lob.hawkes import Clock, ExponentialHawkes, decayed_counts_at
from unito26.lob.idealised import AssumptionBreach, UniformDepth
from unito26.lob.messages import BUY, SELL, GridDepth
from unito26.lob.orderbook import AggregateBook
from unito26.lob.simulate import EventJournal, EventType, MarkParams, OrderFlowSimulator
from unito26.lob.visualization import (
    GEOMETRIC_COLOUR,
    IDEALISED_COLOUR,
    agreement_figure,
    coupled_book_figure,
    coupled_depth_figure,
    coupled_mid_figure,
    coupled_path_figure,
    coupled_touch_figure,
    discrepancy_figure,
    discrepancy_survival_figure,
    discrepancy_survival_panels,
    distance_terms_figure,
    fan_panels_figure,
)

DEPTH = UniformDepth(5)
LEVELS = GridDepth(60)
NARROW = {BUY: (1000, 3), SELL: (1001, 3)}
UNIT = config.unit_mark_params()
FREE = config.withdrawal_free_order_flow_params()
PRESSURE = np.array([event.pressure for event in EventType], dtype=float)


class Scripted:
    """A source of events in the place of a Hawkes process, for the corner cases."""

    params = config.resilient_order_flow_params()

    def __init__(self, events):
        self._events = [(float(time), int(event)) for time, event in events]

    def events(self, horizon):
        yield from ((time, event) for time, event in self._events if time <= horizon)


def scripted(*events, horizon=10.0):
    return RecordedEvents.drawn(
        Scripted([(k + 1, event) for k, event in enumerate(events)]), horizon
    )


def drawn(params, seed, horizon=20.0):
    return RecordedEvents.drawn(ExponentialHawkes(params, rng=seed), horizon)


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
        events = drawn(config.resilient_order_flow_params(), 3)
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
        events = drawn(FREE, 5)
        direct = list(ExponentialHawkes(FREE, rng=5).events(20.0))
        assert len(events) == len(direct) > 100
        assert np.array_equal(events.times, [time for time, _ in direct])
        assert np.array_equal(events.types, [event for _, event in direct])

    def test_a_replay_yields_exactly_the_recorded_path(self):
        events = drawn(FREE, 5)
        replayed = list(events.replay().events(events.horizon))
        assert np.array_equal([time for time, _ in replayed], events.times)
        assert np.array_equal([event for _, event in replayed], events.types)
        assert all(type(time) is float and type(event) is int for time, event in replayed)

    def test_a_second_call_continues_from_the_first(self):
        events = drawn(FREE, 5)
        replay = events.replay()
        first = list(replay.events(7.0))
        second = list(replay.events(events.horizon))
        assert first and all(time <= 7.0 for time, _ in first)
        assert np.array_equal([time for time, _ in first + second], events.times)

    def test_two_replays_are_independent(self):
        events = drawn(FREE, 5)
        one, other = events.replay(), events.replay()
        list(one.events(events.horizon))
        assert len(list(other.events(events.horizon))) == len(events)

    def test_a_horizon_past_the_recorded_one_is_refused(self):
        events = drawn(FREE, 5)
        with pytest.raises(ValueError, match="recorded to 20.0"):
            next(events.replay().events(21.0))

    def test_the_head_is_the_path_to_its_last_event(self):
        events = drawn(FREE, 5)
        head = events.head(10)
        assert head.horizon == events.times[9]
        assert len(list(head.replay().events(head.horizon))) == 10
        assert len(events.head(0)) == 0 and events.head(0).horizon == 0.0

    def test_a_cut_path_moves_the_clock_to_the_cut(self):
        events = drawn(FREE, 5)
        cut = events.after(7.5)
        kept = events.times > 7.5
        assert np.array_equal(cut.times, events.times[kept] - 7.5)
        assert np.array_equal(cut.types, events.types[kept])
        assert cut.horizon == events.horizon - 7.5

    def test_the_state_after_a_time_is_the_decayed_count_with_the_event_at_it(self):
        events = drawn(FREE, 5)
        between = 0.5 * (events.times[40] + events.times[41])
        left = decayed_counts_at(FREE.decay, events.times, events.types, np.zeros(6),
                                 Clock(np.array([between, events.times[41]])))
        assert events.state_after(between) == pytest.approx(left[0])
        jump = np.eye(6)[events.types[41]]
        assert events.state_after(events.times[41]) == pytest.approx(left[1] + jump)


class TestThePair:
    def test_both_placements_see_the_same_events(self):
        events = drawn(FREE, 1)
        pair = CoupledPlacements.on(events, UNIT, DEPTH, NARROW, LEVELS, 2)
        assert pair.breach is None and len(pair.frame) == len(events)
        for journal in (pair.idealised_journal, pair.geometric_journal):
            assert np.array_equal(journal.times, events.times)
            assert np.array_equal(journal.types, events.types)
        assert np.array_equal(pair.frame["TimeStamp"], events.times)
        assert np.array_equal(pair.frame["EventType"], events.types)

    def test_the_idealised_contribution_is_the_pressure(self):
        """``prop.signedSizeContribution`` on the idealised half, whatever the other does."""
        events = drawn(FREE, 1)
        pair = CoupledPlacements.on(events, UNIT, DEPTH, NARROW, LEVELS, 2)
        flow = pair.frame["IdealisedOrderFlowContribution"].to_numpy()
        assert np.array_equal(flow[1:], PRESSURE[events.types][1:])

    def test_market_orders_and_limit_orders_joining_a_touch_coincide_row_for_row(self):
        """At a spread of one tick, with every touch below ``Sbar`` when a limit order joins
        it, the two placements send the same orders."""
        events = scripted(
            EventType.LIMIT_BUY, EventType.MARKET_BUY, EventType.LIMIT_SELL,
            EventType.MARKET_SELL, EventType.LIMIT_SELL, EventType.MARKET_SELL,
            EventType.LIMIT_BUY, EventType.MARKET_BUY,
        )
        pair = CoupledPlacements.on(events, UNIT, DEPTH, NARROW, LEVELS, 0)
        frame = pair.frame
        assert pair.first_discrepancy is None and pair.first_discrepancy_time is None
        assert not frame["BooksDiffer"].any()
        for column in ("MidPrice", "BidPrice1", "BidSize1", "AskPrice1", "AskSize1",
                       "OrderFlowContribution"):
            assert np.array_equal(
                frame[f"Idealised{column}"], frame[f"Geometric{column}"], equal_nan=True
            )
        pd.testing.assert_frame_equal(pair.idealised.lobster_book, pair.geometric.lobster_book)
        pd.testing.assert_frame_equal(pair.idealised.stats, pair.geometric.stats)
        pd.testing.assert_frame_equal(pair.idealised_depth, pair.geometric_depth)

    def test_a_limit_order_at_a_full_touch_facing_one_tick_is_the_first_discrepancy(self):
        """The idealised placement trades it at the ask; the geometric one rests it."""
        events = scripted(EventType.LIMIT_BUY, EventType.LIMIT_BUY)
        pair = CoupledPlacements.on(events, UNIT, DEPTH, {BUY: (1000, 4), SELL: (1001, 3)},
                                    LEVELS, 0)
        last = pair.frame.iloc[1]
        assert pair.first_discrepancy == 1 and pair.first_discrepancy_time == 2.0
        assert (last["IdealisedBidSize1"], last["IdealisedAskSize1"]) == (5, 2)
        assert (last["GeometricBidSize1"], last["GeometricAskSize1"]) == (6, 3)
        assert last["IdealisedOrderFlowContribution"] == last["GeometricOrderFlowContribution"]

    def test_a_limit_order_behind_the_touch_is_a_discrepancy(self):
        """At an offset of one and a spread of one tick the geometric placement rests a share
        one tick behind the bid, where the idealised one joins the bid."""
        marks = MarkParams(0.5, 0.0, 0.01, 1)
        events = scripted(EventType.MARKET_SELL, EventType.LIMIT_BUY)
        behind = [
            pair for pair in (
                CoupledPlacements.on(events, marks, DEPTH, NARROW, LEVELS, seed)
                for seed in range(20)
            )
            if pair.geometric_depth.loc[1, 999] == DEPTH + 1
        ]
        assert behind
        row = behind[0].frame.iloc[1]
        assert behind[0].first_discrepancy == 1
        assert row["IdealisedBidSize1"] == 3 and row["GeometricBidSize1"] == 2
        assert row["GeometricOrderFlowContribution"] == 0

    def test_a_withdrawal_behind_the_touch_is_a_discrepancy(self):
        pair = CoupledPlacements.on(scripted(EventType.WITHDRAW_BUY), UNIT, DEPTH, NARROW,
                                    LEVELS, 0)
        row = pair.frame.iloc[0]
        assert pair.first_discrepancy == 0
        assert row["IdealisedBidSize1"] == 2 and row["GeometricBidSize1"] == 3
        assert pair.geometric_depth.loc[0].sum() == pair.idealised_depth.loc[0].sum()

    def test_a_dropped_withdrawal_repeats_the_book_on_its_row(self):
        """A market sell of fifty shares empties a bid of ten under the geometric
        placement, which then drops the withdrawal; the idealised one takes a share each."""
        marks = MarkParams(1.0, np.log(50.0), 0.01, 1)
        events = scripted(EventType.MARKET_SELL, EventType.WITHDRAW_BUY, EventType.LIMIT_BUY)
        pair = CoupledPlacements.on(events, marks, DEPTH, {BUY: (1000, 5), SELL: (1001, 5)},
                                    GridDepth(2), 0)
        frame = pair.frame
        assert pair.geometric_journal.dropped == 1 and len(pair.geometric.lobster_book) == 2
        assert len(frame) == 3
        geometric = [column for column in frame if column.startswith("Geometric")]
        assert np.array_equal(frame.loc[1, geometric], frame.loc[0, geometric], equal_nan=True)
        assert np.isnan(frame.loc[1, "GeometricBidPrice1"])
        assert frame.loc[2, "GeometricBidSize1"] == 50
        assert list(frame["IdealisedBidSize1"]) == [4, 3, 4]
        assert pair.breach is None

    def test_a_breach_stops_the_pair_before_the_event(self):
        events = scripted(EventType.LIMIT_BUY, EventType.MARKET_BUY, EventType.LIMIT_SELL)
        pair = CoupledPlacements.on(events, UNIT, DEPTH, {BUY: (1000, 3), SELL: (1001, 1)},
                                    GridDepth(1), 0)
        assert isinstance(pair.breach, AssumptionBreach)
        assert "ask side would empty" in str(pair.breach)
        assert len(pair.events) == len(pair.frame) == 1
        assert len(pair.geometric.lobster_book) == len(pair.idealised.lobster_book) == 1


class TestTheFrozenRecords:
    def test_each_reserialises_to_its_frozen_records(self):
        assert FREE.to_records() == config.WITHDRAWAL_FREE_ORDER_FLOW_PARAMS
        assert UNIT.to_records() == config.UNIT_MARK_PARAMS
        assert MarkParams.from_json(UNIT.to_json(2)) == UNIT

    def test_the_withdrawal_free_flow_is_the_documented_one(self):
        withdrawals = [EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL]
        assert FREE.branching_ratio == pytest.approx(0.5)
        assert np.all(FREE.excitation[withdrawals, :] == 0)
        assert np.all(FREE.excitation[:, withdrawals] == 0)
        assert np.all(FREE.baseline >= 0) and np.all(FREE.baseline[withdrawals] == 0)
        assert FREE.stationary_intensity() == pytest.approx([2.5, 2.5, 2.5, 2.5, 0.0, 0.0])
        assert FREE.endogenous_fraction() == pytest.approx(0.690, abs=5e-4)

    def test_the_withdrawal_free_flow_keeps_the_resilient_shape(self):
        resilient = config.resilient_order_flow_params().excitation[:4, :4]
        ratio = FREE.excitation[:4, :4] / resilient
        assert ratio == pytest.approx(np.full((4, 4), ratio[0, 0]))

    def test_the_withdrawal_free_flow_is_direction_symmetric(self):
        swap = np.zeros((6, 6))
        for i in range(0, 6, 2):
            swap[i, i + 1] = swap[i + 1, i] = 1.0
        assert np.allclose(swap @ FREE.excitation @ swap, FREE.excitation)
        assert np.allclose(swap @ FREE.baseline, FREE.baseline)

    def test_every_unit_size_is_one_share_and_every_offset_zero(self):
        simulator = OrderFlowSimulator(FREE, UNIT, 1000, rng=0)
        assert {simulator._size() for _ in range(20000)} == {1}
        assert {simulator._offset() for _ in range(1000)} == {0}


class TestTheFirstDiscrepancyAlone:
    @pytest.mark.parametrize(
        "params, marks",
        [
            (FREE, UNIT),
            (FREE, MarkParams(0.5, 0.0, 0.01, 1)),
            (config.resilient_order_flow_params(), UNIT),
            (config.resilient_order_flow_params(), config.resilient_mark_params()),
        ],
    )
    def test_it_is_the_pair_s(self, params, marks):
        for seed in range(6):
            events = drawn(params, seed, horizon=10.0)
            pair = CoupledPlacements.on(events, marks, DEPTH, NARROW, LEVELS, seed)
            assert first_discrepancy(events, marks, DEPTH, NARROW, LEVELS, seed) == (
                pair.first_discrepancy
            )

    def test_a_pair_that_never_parts_returns_none(self):
        events = scripted(EventType.LIMIT_BUY, EventType.MARKET_BUY)
        assert first_discrepancy(events, UNIT, DEPTH, NARROW, LEVELS, 0) is None


class TestTheTargetOffsets:
    def test_a_row_per_limit_event_read_on_the_book_before_it(self):
        """The third limit buy meets a full bid facing one tick and trades; six market
        sells then clear the bid, and the last limit buy finds a spread of two."""
        events = scripted(
            EventType.LIMIT_BUY, EventType.LIMIT_BUY, EventType.LIMIT_BUY,
            *[EventType.MARKET_SELL] * 6, EventType.LIMIT_BUY,
        )
        offsets = target_offsets(events, DEPTH, NARROW, LEVELS)
        assert list(offsets.index) == [0, 1, 2, 9]
        assert list(offsets["Spread"]) == [1, 1, 1, 2]
        assert list(offsets["TouchFull"]) == [False, False, True, False]
        assert list(offsets["TargetOffset"]) == [0, 0, -1, 1]

    def test_at_depth_decay_one_the_first_discrepancy_is_the_first_nonzero_offset(self):
        """Every offset drawn is zero, so the books part at the first limit event whose
        target is not."""
        for seed in range(10):
            events = drawn(FREE, seed)
            offsets = target_offsets(events, DEPTH, NARROW, LEVELS)
            moved = offsets.index[offsets["TargetOffset"] != 0]
            expected = int(moved[0]) if len(moved) else None
            assert first_discrepancy(events, UNIT, DEPTH, NARROW, LEVELS, seed) == expected

    def test_the_conditional_survival_at_depth_decay_one_is_an_indicator(self):
        events = drawn(FREE, 3)
        offsets = target_offsets(events, DEPTH, NARROW, LEVELS)
        first = first_discrepancy(events, UNIT, DEPTH, NARROW, LEVELS, 0)
        clock = np.linspace(0.0, events.horizon, 2001)
        survival = conditional_survival(
            offsets["TimeStamp"], agreement_probability(offsets["TargetOffset"], 1.0), clock
        )
        assert np.array_equal(survival, (clock < events.times[first]).astype(float))

    def test_the_conditional_survival_is_the_product_of_the_agreements(self):
        agreement = agreement_probability(np.array([0, 2, 1]), 0.5)
        survival = conditional_survival(
            np.array([1.0, 2.0, 3.0]), agreement, np.array([0.5, 1.0, 2.5, 3.0])
        )
        assert survival == pytest.approx([1.0, 0.5, 0.5 * 0.125, 0.5 * 0.125 * 0.25])

    def test_the_agreement_probability_is_the_geometric_law_and_zero_at_minus_one(self):
        offsets = np.arange(-1, 200)
        for decay in (0.08, 0.5, 1.0):
            q = agreement_probability(offsets, decay)
            assert q[0] == 0.0 and q[1] == decay
            assert q[1:].sum() == pytest.approx(1.0)

    def test_the_outcomes_stop_at_the_first_discrepancy(self):
        offsets = target_offsets(drawn(FREE, 1), DEPTH, NARROW, LEVELS)
        first = int(offsets.index[2])
        outcomes = limit_event_outcomes(offsets, first)
        assert list(outcomes["Agreed"]) == [True, True, False]
        assert limit_event_outcomes(offsets, None)["Agreed"].all()


class TestTheTouchShares:
    def test_a_row_per_withdrawal_read_on_the_book_before_it(self):
        events = scripted(EventType.WITHDRAW_BUY, EventType.LIMIT_SELL, EventType.WITHDRAW_SELL,
                          EventType.WITHDRAW_BUY)
        shares = touch_shares(events, DEPTH, NARROW, LEVELS)
        behind = (LEVELS - 1) * DEPTH
        assert list(shares.index) == [0, 2, 3]
        assert shares["TouchShare"].to_numpy() == pytest.approx(
            [3 / (3 + behind), 4 / (4 + behind), 2 / (2 + behind)]
        )

    def test_a_withdrawal_from_a_side_of_one_level_always_agrees(self):
        events = scripted(EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL)
        shares = touch_shares(events, DEPTH, NARROW, GridDepth(1))
        assert list(shares["TouchShare"]) == [1.0, 1.0]
        for seed in range(10):
            assert first_discrepancy(events, UNIT, DEPTH, NARROW, GridDepth(1), seed) is None


class TestTheTouchWalks:
    def test_the_walk_leaves_through_the_cap(self):
        events = scripted(EventType.LIMIT_BUY, EventType.LIMIT_BUY, EventType.LIMIT_BUY)
        assert touch_walk_exit(events, NARROW, DEPTH) == 3.0

    def test_the_walk_leaves_through_zero(self):
        events = scripted(EventType.MARKET_BUY, EventType.LIMIT_BUY, EventType.WITHDRAW_SELL,
                          EventType.MARKET_BUY)
        assert touch_walk_exit(events, NARROW, DEPTH) == 4.0

    def test_from_a_spread_of_one_tick_the_books_part_no_earlier(self):
        """At ``DepthDecay`` one, before the exit every limit event has a target of zero."""
        for seed in range(20):
            events = drawn(FREE, seed)
            exit_time = touch_walk_exit(events, NARROW, DEPTH)
            first = first_discrepancy(events, UNIT, DEPTH, NARROW, LEVELS, seed)
            if first is not None:
                assert events.times[first] >= exit_time


LOGNORMAL = MarkParams(0.2, 0.0, 0.8, 1)


class TestTheReadingsOnAClock:
    @pytest.mark.parametrize(
        "params, marks",
        [
            (FREE, UNIT),
            (FREE, LOGNORMAL),
            (config.resilient_order_flow_params(), config.resilient_mark_params()),
        ],
    )
    def test_they_are_the_pair_s_at_every_event(self, params, marks):
        events = drawn(params, 4, horizon=10.0)
        pair = CoupledPlacements.on(events, marks, DEPTH, NARROW, LEVELS, 1)
        readings = {
            "Idealised": idealised_readings(events, DEPTH, NARROW, LEVELS, events.times),
            "Geometric": geometric_readings(events, marks, DEPTH, NARROW, LEVELS,
                                            events.times, 1),
        }
        depths = {"Idealised": pair.idealised_depth, "Geometric": pair.geometric_depth}
        for placement, reading in readings.items():
            assert np.array_equal(
                reading["MidPrice"], pair.frame[f"{placement}MidPrice"], equal_nan=True
            )
            depth = depths[placement]
            assert np.array_equal(reading["BidDepth"], depth.clip(lower=0).sum(axis=1))
            assert np.array_equal(reading["AskDepth"], -depth.clip(upper=0).sum(axis=1))

    def test_a_time_before_the_first_event_reads_the_opening_book(self):
        events = drawn(FREE, 4, horizon=10.0)
        clock = np.array([0.0, events.times[0] / 2, events.horizon])
        readings = geometric_readings(events, UNIT, DEPTH, NARROW, LEVELS, clock, 1)
        assert list(readings["MidPrice"].iloc[:2]) == [1000.5, 1000.5]
        assert list(readings["BidDepth"].iloc[:2]) == [3 + 59 * 5] * 2

    def test_a_dropped_withdrawal_keeps_the_mid_before_it(self):
        marks = MarkParams(1.0, np.log(50.0), 0.01, 1)
        events = scripted(EventType.MARKET_SELL, EventType.WITHDRAW_BUY, EventType.LIMIT_BUY)
        opening = {BUY: (1000, 5), SELL: (1001, 5)}
        pair = CoupledPlacements.on(events, marks, DEPTH, opening, GridDepth(2), 0)
        mids = geometric_readings(events, marks, DEPTH, opening, GridDepth(2),
                                  np.array([0.5, 1.0, 2.0, 3.0]), 0)["MidPrice"]
        assert np.isnan(mids.iloc[1:3]).all()
        assert mids.iloc[0] == 1000.5
        assert mids.iloc[3] == pair.frame["GeometricMidPrice"].iloc[2]


class TestTheMovesOfTheGeometricMid:
    def test_they_add_up_to_the_change_of_the_mid(self):
        events = drawn(config.resilient_order_flow_params(), 4, horizon=10.0)
        marks = config.resilient_mark_params()
        pair = CoupledPlacements.on(events, marks, DEPTH, NARROW, LEVELS, 1)
        moves = geometric_mid_moves(events, marks, DEPTH, NARROW, LEVELS, 1)
        mids = pair.frame["GeometricMidPrice"].dropna()
        assert moves["Move"].sum() == mids.iloc[-1] - 1000.5
        assert (moves["Move"] != 0).all()

    def test_a_move_across_an_empty_side_is_marked(self):
        """The market sell empties the bid; the limit buy after it is priced against the
        reference price, and the mid it restores is a move across an empty side."""
        marks = MarkParams(1.0, np.log(50.0), 0.01, 1)
        events = scripted(EventType.MARKET_SELL, EventType.LIMIT_BUY, EventType.MARKET_BUY)
        moves = geometric_mid_moves(events, marks, DEPTH, {BUY: (1000, 5), SELL: (1001, 5)},
                                    GridDepth(2), 0)
        assert moves["AcrossEmptySide"].iloc[0] and not moves["AcrossEmptySide"].iloc[1:].any()


class TestTheDistance:
    @pytest.mark.parametrize("marks", [UNIT, MarkParams(0.5, 0.0, 0.01, 1), LOGNORMAL])
    def test_the_three_terms_add_up_to_the_distance(self, marks):
        events = drawn(FREE, 2, horizon=40.0)
        pair = CoupledPlacements.on(events, marks, DEPTH, NARROW, LEVELS, 3)
        terms = distance_terms(pair, DEPTH, NARROW)
        assert np.array_equal(
            terms["Distance"],
            terms["ImbalanceMismatch"] - terms["TouchSizeMismatch"] - terms["DepthMismatch"],
        )
        assert (terms["Distance"] != 0).any()
        assert (terms["IdealisedDepthMismatch"] == 0).all()

    def test_the_contributions_are_the_session_s(self):
        """Read from the touches with the opening prepended, so defined on the first row."""
        events = drawn(FREE, 2, horizon=40.0)
        pair = CoupledPlacements.on(events, LOGNORMAL, DEPTH, NARROW, LEVELS, 3)
        terms = distance_terms(pair, DEPTH, NARROW)
        flow = pair.frame[["GeometricOrderFlowContribution", "IdealisedOrderFlowContribution"]]
        recorded = (flow.iloc[:, 0] - flow.iloc[:, 1]).to_numpy()
        assert np.array_equal(np.diff(terms["ImbalanceMismatch"]), recorded[1:])

    def test_at_depth_decay_one_with_unit_sizes_the_imbalances_agree(self):
        events = drawn(FREE, 2, horizon=40.0)
        pair = CoupledPlacements.on(events, UNIT, DEPTH, NARROW, LEVELS, 3)
        assert (distance_terms(pair, DEPTH, NARROW)["ImbalanceMismatch"] == 0).all()


@pytest.fixture(scope="module")
def pair():
    return CoupledPlacements.on(drawn(FREE, 1), UNIT, DEPTH, NARROW, LEVELS, 2)


class TestTheFigures:
    def test_the_mid_difference_is_zero_until_the_first_discrepancy(self, pair):
        figure = coupled_mid_figure(pair)
        idealised, geometric, difference = figure.data
        first = pair.first_discrepancy
        assert idealised.line.dash == "dot" and geometric.line.dash == "solid"
        assert np.all(np.asarray(difference.y)[:first] == 0)
        assert figure.layout.shapes[0].x0 == pair.first_discrepancy_time

    def test_the_touches_are_drawn_per_side_and_placement(self, pair):
        figure = coupled_touch_figure(pair)
        assert len(figure.data) == 4
        assert np.array_equal(figure.data[0].y, pair.frame["IdealisedBidSize1"])
        assert np.array_equal(figure.data[3].y, pair.frame["GeometricAskSize1"])

    def test_the_two_depth_panels_share_one_scale_and_one_price_axis(self, pair):
        figure = coupled_depth_figure(pair)
        idealised, geometric = figure.data
        assert (idealised.zmin, idealised.zmax) == (geometric.zmin, geometric.zmax)
        assert idealised.zmin == -idealised.zmax
        assert np.array_equal(idealised.y, geometric.y)
        assert np.asarray(idealised.z).shape == (len(idealised.y), len(pair.frame))

    def test_the_survival_falls_by_one_path_at_each_discrepancy(self):
        times = [1.0, np.nan, 3.0, 2.0]
        grid = np.linspace(0.0, 5.0, 6)
        figure = discrepancy_survival_figure(times, 5.0, (grid, np.exp(-grid)))
        empirical, theoretical = figure.data
        assert np.array_equal(empirical.x, [0.0, 1.0, 2.0, 3.0, 5.0])
        assert np.array_equal(empirical.y, [1.0, 0.75, 0.5, 0.25, 0.25])
        assert np.array_equal(theoretical.y, np.exp(-grid))
        assert len(discrepancy_survival_figure(times, 5.0, None).data) == 1

    def test_the_discrepancy_has_a_line_per_size_law(self):
        decays = [1.0, 0.5, 0.2]
        figure = discrepancy_figure(
            {"unit": pd.Series([0.1, 0.4, 0.9], decays),
             "lognormal": pd.Series([0.5, 0.8, 1.2], decays)}
        )
        assert len(figure.data) == 2
        assert list(figure.data[1].x) == decays

    def test_the_path_figure_keeps_one_colour_per_placement_in_every_panel(self, pair):
        figure = coupled_path_figure(pair, "")
        assert len(figure.data) == 6
        colours = {trace.name: trace.line.color for trace in figure.data}
        assert colours == {"idealised": IDEALISED_COLOUR, "geometric": GEOMETRIC_COLOUR}
        assert np.array_equal(figure.data[5].y, pair.frame["GeometricAskSize1"])
        assert len(figure.layout.shapes) == 3 and len(figure.layout.annotations) == 4

    def test_the_book_figure_draws_both_books_after_the_event(self, pair):
        first = pair.first_discrepancy
        figure = coupled_book_figure(pair, first, 3, "")
        idealised_bid, _, geometric_bid, _ = figure.data
        row = pair.geometric_depth.loc[first]
        assert len(idealised_bid.y) == 3
        assert list(geometric_bid.x) == list(row[row > 0].sort_index(ascending=False).head(3))

    def test_the_survival_panels_hold_a_grid_and_one_legend_entry_a_name(self):
        clock = np.geomspace(0.1, 10.0, 50)
        times = {row: {"a": np.array([1.0, np.nan]), "b": np.array([2.0, 3.0])}
                 for row in ("one", "two")}
        curves = {row: {column: {"formula": np.exp(-clock)} for column in ("a", "b")}
                  for row in ("one", "two")}
        figure = discrepancy_survival_panels(times, clock, curves, "")
        assert len(figure.data) == 8
        assert sum(bool(trace.showlegend) for trace in figure.data) == 2
        assert figure.data[0].y[np.searchsorted(clock, 1.0)] == 0.5
        assert figure.layout.xaxis.type == "log"

    def test_the_agreement_figure_has_a_panel_per_depth_decay(self):
        table = pd.DataFrame(
            {"TargetOffset": [0, -1, 1], "LimitEvents": [100, 20, 50],
             "Agreed": [0.5, 0.0, 0.3], "StandardError": [0.05, 0.0, 0.06],
             "Formula": [0.5, 0.0, 0.25]},
            index=pd.MultiIndex.from_tuples([(1, False), (1, True), (2, False)],
                                            names=["Spread", "TouchFull"]),
        )
        figure = agreement_figure({0.5: table, 0.2: table}, "")
        assert len(figure.data) == 6
        assert list(figure.data[0].x) == [-1, 0, 1]
        assert figure.data[0].y[0] == 0.0 and figure.data[0].y[1] == 0.5

    def test_the_distance_figure_draws_the_terms_as_they_enter(self):
        events = drawn(FREE, 2, horizon=20.0)
        pair = CoupledPlacements.on(events, LOGNORMAL, DEPTH, NARROW, LEVELS, 3)
        terms = distance_terms(pair, DEPTH, NARROW)
        figure = distance_terms_figure(terms, "")
        distance, imbalance, sizes, depth = figure.data
        assert np.array_equal(distance.y, imbalance.y + sizes.y + depth.y)

    def test_the_fan_panels_draw_the_paths_shown_and_the_curves(self):
        clock = np.arange(5.0)
        paths = {"row": {"a": np.ones((4, 5)), "b": np.zeros((4, 5))}}
        curves = {"row": {"a": {"mean": np.ones(5), "other": np.zeros(5)},
                          "b": {"mean": np.zeros(5), "other": np.ones(5)}}}
        figure = fan_panels_figure(paths, clock, curves, 2, "ticks", False, "")
        assert len(figure.data) == 8
        assert figure.data[2].line.color == GEOMETRIC_COLOUR
