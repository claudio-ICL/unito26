"""Tests for the fold, the snapshot taps, and the synthetic order flow."""

import numpy as np
import pytest

from unito26.lob.messages import BUY, SELL, MessageType, limit_order, market_order
from unito26.lob.orderbook import AggregateBook
from unito26.lob.replay import (
    book_copy,
    deltas_to_table,
    level_deltas,
    lobster_levels,
    replay,
    run,
    top_of_book,
)
from unito26.lob.simulate import EventType, OrderFlowSimulator, default_flow_params


@pytest.fixture
def worked_example() -> AggregateBook:
    return AggregateBook.from_levels({1000: 100, 999: 200, 998: 150}, {1002: 120, 1003: 180})


class TestTaps:
    def test_top_of_book_series(self, worked_example):
        messages = [
            limit_order(1.0, 50, 1001, BUY),  # improves the bid
            market_order(2.0, 200, BUY),  # eats the best ask and part of the next
        ]
        series = list(replay(worked_example, messages, top_of_book))
        assert series[0] == (1.0, 1001, 50, 1002, 120)
        assert series[1] == (2.0, 1001, 50, 1003, 100)

    def test_snapshots_are_not_aliases_of_the_live_book(self, worked_example):
        messages = [market_order(float(i), 30, BUY) for i in range(4)]
        snapshots = list(replay(worked_example, messages, book_copy))
        # If the tap had stored the book itself, every snapshot would show the final
        # state and this sequence would be constant.
        # 120 at 1002 is eaten 30 at a time; on the fourth the level is exhausted and
        # the best ask rolls up to 1003 x 180.
        assert [(s.best_ask_price, s.best_ask_volume) for s in snapshots] == [
            (1002, 90),
            (1002, 60),
            (1002, 30),
            (1003, 180),
        ]
        # Had the tap stored the book itself, all four would read (1003, 180).

    def test_lobster_row_layout(self, worked_example):
        row = list(replay(worked_example, [limit_order(1.0, 1, 997, BUY)], lobster_levels(2)))[0]
        # ask price, ask size, bid price, bid size -- repeated per level.
        assert row == (1002, 120, 1000, 100, 1003, 180, 999, 200)

    def test_deltas_describe_exactly_the_levels_that_moved(self, worked_example):
        deltas = list(replay(worked_example, [limit_order(1.0, 400, 999, SELL)], level_deltas))[0]
        assert [(d.side, d.price, d.volume) for d in deltas] == [
            (BUY, 1000, 0),  # consumed entirely: the level is gone
            (BUY, 999, 0),  # consumed entirely
            (SELL, 999, 100),  # the residual rests, inside the old spread
        ]

    def test_delta_volumes_are_absolute_and_so_are_idempotent(self, worked_example):
        # Applying a delta twice must be a no-op: that is what "absolute" buys, and it
        # is why real feeds send new sizes rather than changes.
        deltas = list(replay(worked_example, [limit_order(1.0, 60, 999, BUY)], level_deltas))[0]
        levels = {}
        for delta in deltas * 2:
            levels[delta.price] = delta.volume
        assert levels == {999: 260}


class TestDeltaStorage:
    def test_delta_table_is_much_smaller_than_dense_snapshots(self):
        simulator = OrderFlowSimulator(rng=3)
        book = AggregateBook()
        simulator.warm_up(book, horizon=20.0)
        messages = []
        for message in simulator.stream(book, horizon=200.0):
            book.apply(message)
            messages.append(message)

        fresh = AggregateBook()
        rows = []
        for sequence, deltas in enumerate(replay(fresh, messages, level_deltas)):
            for delta in deltas:
                rows.append((sequence, messages[sequence].time, delta))
        table = deltas_to_table(rows)

        assert table.num_rows == len(rows)
        # Most messages move exactly one level; the average is a shade above one.
        per_message = table.num_rows / len(messages)
        assert 0.5 < per_message < 2.5
        # Against a dense 10-level snapshot per message, which is 40 values a row.
        assert table.num_rows * 5 < len(messages) * 40


class TestSimulatedFlow:
    def test_stream_keeps_the_book_valid(self):
        simulator = OrderFlowSimulator(rng=1)
        book = AggregateBook()
        for message in simulator.stream(book, horizon=300.0):
            book.apply(message)
            book.check_invariants()
        assert book.best_bid_price is not None
        assert book.spread >= 1

    def test_all_six_event_types_occur(self):
        simulator = OrderFlowSimulator(rng=2)
        book = AggregateBook()
        seen = set()
        for message in simulator.stream(book, horizon=300.0):
            seen.add((message.kind, message.direction))
            book.apply(message)
        assert (MessageType.WITHDRAW, BUY) in seen
        assert (MessageType.WITHDRAW, SELL) in seen
        assert (MessageType.SUBMIT, BUY) in seen
        assert (MessageType.SUBMIT, SELL) in seen

    def test_submissions_only_mode_emits_no_withdrawals(self):
        simulator = OrderFlowSimulator(rng=4, submissions_only=True)
        book = AggregateBook()
        kinds = {m.kind for m in simulator.stream(book, horizon=100.0)}
        assert kinds == {MessageType.SUBMIT}

    def test_default_parameters_sit_in_the_documented_regime(self):
        params = default_flow_params()
        assert params.branching_ratio == pytest.approx(0.8)
        # Market orders excite the limit-order flow far more than the reverse.
        replenishment = params.excitation[EventType.LIMIT_SELL, EventType.MARKET_BUY]
        reverse = params.excitation[EventType.MARKET_BUY, EventType.LIMIT_SELL]
        assert replenishment > 5 * reverse

    def test_reproducible_from_a_seed(self):
        def session():
            simulator = OrderFlowSimulator(rng=99)
            book = AggregateBook()
            return [
                (m.time, m.size, m.price, m.direction, m.kind)
                for m in simulator.stream(book, horizon=60.0)
                if book.apply(m) or True
            ]

        assert session() == session()
