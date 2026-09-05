"""Tests for the fold and the synthetic order flow."""

import pytest

from unito26.lob import config
from unito26.lob.orderbook import AggregateBook
from unito26.lob.session import run
from unito26.lob.messages import BUY, SELL
from unito26.lob.simulate import EventJournal, EventType, OrderFlowSimulator

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
        for message in simulator(1).stream(book, horizon=300.0, journal=None):
            book.apply(message, record=False)
            book.check_invariants()
        assert book.best_bid_price is not None
        assert book.spread >= 1

    def test_all_event_types_occur(self):
        book = AggregateBook()
        seen = set()
        for message in simulator(2).stream(book, horizon=300.0, journal=None):
            seen.add((message.kind, message.direction))
            book.apply(message, record=False)
        assert len(seen) == 4

    def test_run_counts_what_went_past(self, worked_example):
        sim = simulator(7)
        messages = list(sim.stream(AggregateBook.from_levels({999: 10}, {1001: 10}), horizon=50.0, journal=None))
        tally = run(worked_example, messages)
        assert tally["messages"] == len(messages)
        assert tally["traded"] >= 0

    def test_reproducible_from_a_seed(self):
        def session():
            book = AggregateBook()
            recorded = []
            for message in simulator(99).stream(book, horizon=60.0, journal=None):
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


class TestPressure:
    def test_it_is_the_direction_except_on_the_withdrawals(self):
        """Withdrawing a bid takes size off the buy side, so it pushes the price down."""
        crossing = {
            event for event in EventType if event.pressure != event.direction
        }
        assert crossing == {EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL}

    def test_every_type_pushes_one_way_or_the_other(self):
        assert {event.pressure for event in EventType} == {BUY, SELL}
        assert [EventType(i).pressure for i in range(6)] == [1, -1, 1, -1, -1, 1]


class TestTheEventJournal:
    def test_it_holds_every_hawkes_event_the_stream_drew(self):
        """The message count is not the event count: a withdrawal on an empty side is
        dropped, so the message stream is a thinning of the point process."""
        book = AggregateBook()
        journal = EventJournal.empty()
        messages = list(simulator(4).stream(book, horizon=1.0, journal=journal))
        assert len(journal) == len(messages) + journal.dropped

    def test_the_drops_are_the_withdrawals_the_book_refused(self):
        book = AggregateBook()
        journal = EventJournal.empty()
        for message in simulator(4).stream(book, horizon=60.0, journal=journal):
            book.apply(message, record=False)
        refused = [
            EventType(kind)
            for kind, emitted in zip(journal.types, journal.emitted)
            if not emitted
        ]
        assert refused
        assert set(refused) <= {EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL}

    def test_it_records_the_point_process_and_not_the_message_stream(self):
        book = AggregateBook()
        journal = EventJournal.empty()
        for message in simulator(4).stream(book, horizon=20.0, journal=journal):
            book.apply(message, record=False)
        assert journal.times == sorted(journal.times)
        assert max(journal.times) <= 20.0
        assert set(journal.types) <= {int(event) for event in EventType}


class TestTheWarmUpSeam:
    def test_a_warm_up_then_a_run_samples_the_second_stretch(self):
        """The horizon is absolute and the Hawkes state is shared, so ``stream`` picks up
        where ``warm_up`` left off rather than restarting the clock."""
        simulation = simulator(6)
        book = AggregateBook()
        journal = EventJournal.empty()
        simulation.warm_up(book, horizon=30.0, journal=journal)
        messages = []
        for message in simulation.stream(book, horizon=90.0, journal=journal):
            book.apply(message, record=False)
            messages.append(message)
        assert messages
        assert min(m.time for m in messages) > 30.0
        assert max(m.time for m in messages) <= 90.0

    def test_the_split_run_draws_what_the_whole_run_draws(self):
        """The event that ends a stretch is drawn before it is known to be past the
        horizon, and it has already excited the state.  Discarding it would lose one
        event at every seam."""
        whole = simulator(6)
        book = AggregateBook()
        journal = EventJournal.empty()
        for message in whole.stream(book, horizon=90.0, journal=journal):
            book.apply(message, record=False)

        split = simulator(6)
        book = AggregateBook()
        in_two = EventJournal.empty()
        split.warm_up(book, horizon=30.0, journal=in_two)
        for message in split.stream(book, horizon=90.0, journal=in_two):
            book.apply(message, record=False)

        assert in_two.times == journal.times
        assert in_two.types == journal.types
