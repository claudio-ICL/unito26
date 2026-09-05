"""Tests for the sparse recording: a session as level changes, not as states."""

from unito26.lob import config
from unito26.lob.delta_log import DeltaLog
from unito26.lob.orderbook import AggregateBook
from unito26.lob.simulate import OrderFlowSimulator

REFERENCE_PRICE = 10000


def simulator(seed):
    return OrderFlowSimulator(
        config.example_order_flow_params(),
        config.example_mark_params(),
        REFERENCE_PRICE,
        rng=seed,
    )


class TestDeltaStorage:
    def test_delta_table_is_much_smaller_than_dense_snapshots(self):
        sim = simulator(3)
        book = AggregateBook()
        sim.warm_up(book, horizon=20.0)
        messages = []
        for message in sim.stream(book, horizon=200.0):
            book.apply(message, record=False)
            messages.append(message)

        log = DeltaLog.record(AggregateBook(), messages)
        table = log.to_table()

        assert table.num_rows == len(log.entries)
        assert table.column_names == ["seq", "time", "side", "price", "resting"]
        # Most messages move exactly one level; the average is a shade above one.
        assert 0.5 < table.num_rows / len(messages) < 2.5
        # Against a dense 10-level snapshot per message, which is 40 values a row.
        assert table.num_rows * 5 < len(messages) * 40
