"""Tests for the fold and the synthetic order flow."""

import pytest

from unito26.lob import config
from unito26.lob.orderbook import AggregateBook
from unito26.lob.session import run
from unito26.lob.simulate import EventType, OrderFlowSimulator

REFERENCE_PRICE = 10000


def simulator(seed, marks=None):
    return OrderFlowSimulator(
        config.example_order_flow_params(),
        marks or config.example_mark_params(),
        REFERENCE_PRICE,
        rng=seed,
    )


@pytest.fixture
def worked_example() -> AggregateBook:
    return AggregateBook.from_levels({1000: 100, 999: 200, 998: 150}, {1002: 120, 1003: 180})


class TestSimulatedFlow:
    def test_stream_keeps_the_book_valid(self):
        book = AggregateBook()
        for message in simulator(1).stream(book, horizon=300.0):
            book.apply(message, record=False)
            book.check_invariants()
        assert book.best_bid_price is not None
        assert book.spread >= 1

    def test_all_event_types_occur(self):
        book = AggregateBook()
        seen = set()
        for message in simulator(2).stream(book, horizon=300.0):
            seen.add((message.kind, message.direction))
            book.apply(message, record=False)
        assert len(seen) == 4

    def test_run_counts_what_went_past(self, worked_example):
        sim = simulator(7)
        messages = list(sim.stream(AggregateBook.from_levels({999: 10}, {1001: 10}), horizon=50.0))
        tally = run(worked_example, messages)
        assert tally["messages"] == len(messages)
        assert tally["traded"] >= 0

    def test_reproducible_from_a_seed(self):
        def session():
            book = AggregateBook()
            recorded = []
            for message in simulator(99).stream(book, horizon=60.0):
                book.apply(message, record=False)
                recorded.append(
                    (message.time, message.size, message.price, message.direction, message.kind)
                )
            return recorded

        assert session() == session()

    def test_the_example_flow_sits_in_the_documented_regime(self):
        params = config.example_order_flow_params()
        assert params.branching_ratio == pytest.approx(0.6)
        # Market orders excite the limit-order flow far more than the reverse.
        replenishment = params.excitation[EventType.LIMIT_SELL, EventType.MARKET_BUY]
        reverse = params.excitation[EventType.MARKET_BUY, EventType.LIMIT_SELL]
        assert replenishment > 5 * reverse
