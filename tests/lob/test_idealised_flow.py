"""The idealised book of section 1.4, checked on the package's own statistics.

The flow keeps the assumption true by construction, and everything downstream of it is
ordinary: the book that folds it and the session that records it.  So the identity of the
notes is checked on ``e_n``, the imbalance and the mid-price as the package computes them.
"""

import numpy as np
import pytest

from unito26.lob import config
from unito26.lob.hawkes import ExponentialHawkes
from unito26.lob.idealised import AssumptionBreach, IdealisedFlow, UniformDepth, idealised_book
from unito26.lob.messages import BUY, SELL, GridDepth, PriceUnit, ReportedDepth
from unito26.lob.session import MarketSession
from unito26.lob.simulate import EventJournal, EventType
from unito26.lob.statistics import SessionStatistics

DEPTH = UniformDepth(5)
SPEC = SessionStatistics((GridDepth(1),), (), (1,))
PRESSURE = np.array([event.pressure for event in EventType])
REGIMES = [config.resilient_order_flow_params(), config.trending_order_flow_params()]
WIDE = {BUY: (1000, 5), SELL: (1020, 5)}


class Scripted:
    """A source of events in the place of a Hawkes process, for the corner cases."""

    params = config.resilient_order_flow_params()

    def __init__(self, events):
        self._events = [(float(time), int(event)) for time, event in events]

    def events(self, horizon):
        yield from ((time, event) for time, event in self._events if time <= horizon)


def record(source, touches, horizon=10.0, levels=GridDepth(60)):
    """The session of the flow driven by ``source``, and the types behind its rows."""
    book = idealised_book(DEPTH, touches, levels)
    journal = EventJournal.empty()
    flow = IdealisedFlow(source, DEPTH)
    session = MarketSession.from_occupied_levels(
        book, flow.stream(book, horizon, journal), ReportedDepth(1), SPEC, PriceUnit(1), True
    )
    return session, np.array(journal.types)


def simulated(params, seed):
    return record(ExponentialHawkes(params, rng=seed), WIDE, horizon=20.0)


@pytest.mark.parametrize("params", REGIMES)
def test_every_event_contributes_its_pressure(params):
    """``prop.signedSizeContribution``: under the assumption ``e_n`` is the pressure of the
    event times its size, one share here."""
    session, types = simulated(params, seed=0)
    flow = session.stats["OrderFlowContribution"].to_numpy()
    assert len(types) > 300
    assert np.isnan(flow[0])
    assert np.array_equal(flow[1:], PRESSURE[types][1:])


@pytest.mark.parametrize("params", REGIMES)
def test_the_assumption_holds_after_every_message(params):
    book = idealised_book(DEPTH, WIDE, GridDepth(60))
    flow = IdealisedFlow(ExponentialHawkes(params, rng=1), DEPTH)
    count = 0
    for message in flow.stream(book, 20.0, None):
        book.apply(message, record=False)
        count += 1
        for direction in (BUY, SELL):
            levels = book.levels_map(direction)
            touch = book.best_price(direction)
            behind = sorted(levels, reverse=direction == BUY)[1:]
            assert 1 <= levels[touch] <= DEPTH
            assert all(levels[price] == DEPTH for price in behind)
            assert behind == [touch - direction * k for k in range(1, len(behind) + 1)]
        assert book.best_price(BUY) < book.best_price(SELL)
    assert count > 300


@pytest.mark.parametrize("params", REGIMES)
def test_the_mid_price_is_the_imbalance_plus_the_residual_exactly(params):
    """``prop.idealisedUpdate`` in integers: ``2 Sbar dP/tau = OFI - dS^b + dS^a``, over
    random windows that start after the first row, where ``e_1`` is undefined."""
    session, _ = simulated(params, seed=2)
    mid = session.stats["MidPrice"].to_numpy()
    flow = session.stats["OrderFlowContribution"].to_numpy()
    bid = session.lobster_book["BidSize1"].to_numpy()
    ask = session.lobster_book["AskSize1"].to_numpy()
    cumulative = np.r_[0.0, np.cumsum(flow[1:])]  # cumulative[k] = e_2 + ... + e_{k+1}
    rng = np.random.default_rng(3)
    for start, end in np.sort(rng.integers(1, len(mid), size=(2000, 2)), axis=1):
        imbalance = cumulative[end] - cumulative[start]
        residual = -((bid[end] - bid[start]) - (ask[end] - ask[start])) / (2 * DEPTH)
        assert 2 * DEPTH * (mid[end] - mid[start]) == imbalance - (bid[end] - bid[start]) + (
            ask[end] - ask[start]
        )
        assert mid[end] - mid[start] == pytest.approx(imbalance / (2 * DEPTH) + residual)
        assert abs(residual) <= 1


def test_where_no_quote_moves_the_residual_cancels_the_flow():
    """``remark.residualIsQueueFlow``: the flow went into the queues."""
    session, _ = record(
        Scripted([
            (1, EventType.LIMIT_BUY),
            (2, EventType.LIMIT_BUY),
            (3, EventType.WITHDRAW_SELL),
            (4, EventType.MARKET_BUY),
        ]),
        {BUY: (1000, 2), SELL: (1010, 4)},
    )
    mid = session.stats["MidPrice"].to_numpy()
    flow = session.stats["OrderFlowContribution"].to_numpy()
    assert np.all(mid == mid[0])
    assert np.array_equal(flow[1:], [1, 1, 1])


class TestTheCornerCases:
    def test_opening_inside_a_spread_of_two_contributes_one(self):
        session, _ = record(
            Scripted([(1, EventType.LIMIT_SELL), (2, EventType.LIMIT_BUY)]),
            {BUY: (1000, 5), SELL: (1002, 3)},
        )
        assert session.lobster_book["BidPrice1"].iloc[-1] == 1001
        assert session.stats["OrderFlowContribution"].iloc[-1] == 1

    @pytest.mark.parametrize("event", [EventType.WITHDRAW_BUY, EventType.MARKET_SELL])
    def test_emptying_the_bid_touch_contributes_minus_one(self, event):
        session, _ = record(
            Scripted([(1, EventType.LIMIT_SELL), (2, event)]),
            {BUY: (1000, 1), SELL: (1010, 3)},
        )
        assert session.lobster_book["BidPrice1"].iloc[-1] == 999
        assert session.lobster_book["BidSize1"].iloc[-1] == DEPTH
        assert session.stats["OrderFlowContribution"].iloc[-1] == -1


class TestTheBreaches:
    def test_a_limit_order_cannot_open_inside_a_spread_of_one_tick(self):
        with pytest.raises(AssumptionBreach, match="one tick"):
            record(Scripted([(1, EventType.LIMIT_BUY)]), {BUY: (1000, 5), SELL: (1001, 5)})

    def test_a_side_cannot_be_emptied(self):
        with pytest.raises(AssumptionBreach, match="ask side would empty"):
            record(
                Scripted([(1, EventType.MARKET_BUY)]),
                {BUY: (1000, 5), SELL: (1010, 1)},
                levels=GridDepth(1),
            )

    def test_the_book_refuses_a_touch_above_the_cap(self):
        with pytest.raises(ValueError, match="between 1 and 5"):
            idealised_book(DEPTH, {BUY: (1000, 6), SELL: (1010, 1)}, GridDepth(3))

    def test_a_side_holds_at_least_its_touch(self):
        with pytest.raises(ValueError, match="at least its touch"):
            idealised_book(DEPTH, {BUY: (1000, 5), SELL: (1010, 1)}, GridDepth(0))

    def test_a_starting_book_outside_the_assumption_is_refused(self):
        """The flow keeps the assumption true but cannot make it so."""
        book = idealised_book(UniformDepth(5), WIDE, GridDepth(10))
        flow = IdealisedFlow(Scripted([(1, EventType.LIMIT_BUY)]), UniformDepth(3))
        with pytest.raises(AssumptionBreach, match="bid touch holds 5"):
            next(flow.stream(book, 10.0, None))
        book.set_size(BUY, 995, 0)
        flow = IdealisedFlow(Scripted([(1, EventType.LIMIT_BUY)]), DEPTH)
        with pytest.raises(AssumptionBreach, match="every tick behind"):
            next(flow.stream(book, 10.0, None))
