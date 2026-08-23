"""The fold: driving a book with a stream of messages, and recording what happened.

A book holds *one* state.  The time series of states is made here, by folding a stream
through a book and tapping whatever the caller asked to record.  The tap is a
parameter because the right answer genuinely differs by use: a benchmark wants
nothing recorded, a signals study wants the top of book on every message, and a
comparison against a venue's own snapshot file wants a fixed-width ladder.

The alternative -- a ``history`` list on the book itself -- conflates two concerns and
walks straight into the aliasing bug that :func:`book_copy` exists to avoid.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable, Iterator

from unito26.lob.messages import BUY, SELL, LevelDelta, Message, MessageType
from unito26.lob.orderbook import AggregateBook, SubmitResult

__all__ = [
    "Tap",
    "run",
    "replay",
    "top_of_book",
    "book_levels",
    "lobster_levels",
    "book_copy",
    "level_deltas",
    "deltas_to_table",
    "snapshots_to_table",
]

#: A tap sees the book *after* the message was applied, along with what the message did.
Tap = Callable[[AggregateBook, Message, SubmitResult], Any]


def run(book: AggregateBook, messages: Iterable[Message]) -> Counter:
    """Fold the stream through the book, recording nothing.  The benchmark path.

    Returns counts of what went past -- messages, trades, shares traded -- which is
    enough to tell that two implementations did the same work without the cost of
    keeping the states they passed through.
    """
    tally: Counter = Counter()
    for message in messages:
        result = book.apply(message)
        tally["messages"] += 1
        tally["fills"] += len(result.fills)
        tally["traded"] += result.market_order_size
        if message.kind is MessageType.WITHDRAW:
            tally["withdrawals"] += 1
    return tally


def replay(
    book: AggregateBook, messages: Iterable[Message], record: Tap
) -> Iterator[Any]:
    """Fold the stream through the book, yielding ``record(...)`` after each message.

    A generator, so the series is consumed as it is produced and a long session never
    has to be held in memory at once.
    """
    for message in messages:
        result = book.apply(message)
        yield record(book, message, result)


# ---- taps -------------------------------------------------------------------------


def top_of_book(book: AggregateBook, message: Message, result: SubmitResult) -> tuple:
    """``(t, P^b, V^b, P^a, V^a)``.  Fixed width, cheap, and enough for section 4."""
    return (
        message.time,
        book.best_bid_price,
        book.best_bid_volume,
        book.best_ask_price,
        book.best_ask_volume,
    )


def book_levels(depth: int) -> Tap:
    """Tap factory: the first ``depth`` grid positions on each side."""

    def tap(book: AggregateBook, message: Message, result: SubmitResult) -> tuple:
        return (message.time, book.levels(BUY, depth), book.levels(SELL, depth))

    return tap


def lobster_levels(depth: int) -> Tap:
    """Tap factory: a ``4 * depth`` row in LOBSTER's own column order.

    That order is ask price, ask size, bid price, bid size, repeated per level.  Using
    it here means a later comparison against a shipped orderbook file is a matter of
    equality rather than translation.
    """

    def tap(book: AggregateBook, message: Message, result: SubmitResult) -> tuple:
        row: list[int | None] = []
        asks = book.levels(SELL, depth)
        bids = book.levels(BUY, depth)
        for index in range(depth):
            ask = asks[index] if index < len(asks) else (None, 0)
            bid = bids[index] if index < len(bids) else (None, 0)
            row.extend((ask[0], ask[1], bid[0], bid[1]))
        return tuple(row)

    return tap


def book_copy(book: AggregateBook, message: Message, result: SubmitResult) -> AggregateBook:
    """A deep-enough copy of the book.

    Storing ``book`` itself would store the same mutable object at every step, so every
    recorded snapshot would end up equal to the final state.  That bug is silent, it
    survives casual inspection, and it is the reason this tap exists rather than a
    ``lambda book, *_: book``.
    """
    return book.copy()


def level_deltas(
    book: AggregateBook, message: Message, result: SubmitResult
) -> list[LevelDelta]:
    """The level changes the message caused: the book's own incremental update."""
    return result.deltas


# ---- storage --------------------------------------------------------------------


def deltas_to_table(rows: Iterable[tuple[int, float, LevelDelta]]):
    """Columnar table of level deltas: ``(seq, time, side, price, volume)``.

    One row per level *change*, against one row per *message* for the dense form.  The
    saving comes from most messages touching a single level, and from the ``price``
    column compressing extremely well, since consecutive changes cluster around the
    touch.
    """
    import pyarrow as pa

    sequences, times, sides, prices, volumes = [], [], [], [], []
    for sequence, time, delta in rows:
        sequences.append(sequence)
        times.append(time)
        sides.append(delta.side)
        prices.append(delta.price)
        volumes.append(delta.volume)
    return pa.table(
        {
            "seq": pa.array(sequences, pa.int64()),
            "time": pa.array(times, pa.float64()),
            "side": pa.array(sides, pa.int8()),
            "price": pa.array(prices, pa.int32()),
            "volume": pa.array(volumes, pa.int32()),
        }
    )


def snapshots_to_table(rows: Iterable[tuple], depth: int):
    """Columnar table of dense snapshots, one row per message.

    The alternative to :func:`deltas_to_table`, kept so the two can be measured against
    each other rather than compared by assertion.
    """
    import pyarrow as pa

    rows = list(rows)
    names: list[str] = []
    for level in range(1, depth + 1):
        names += [
            f"ask_price_{level}",
            f"ask_size_{level}",
            f"bid_price_{level}",
            f"bid_size_{level}",
        ]
    columns = {
        name: pa.array([row[index] for row in rows], pa.int64())
        for index, name in enumerate(names)
    }
    return pa.table(columns)
