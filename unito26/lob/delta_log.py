"""A session recorded as level changes rather than as states.

A dense recorder writes the whole book after every message.  This writes only what moved,
and the opening state it moved from, which is the saving: most messages touch one level.

What a log determines is every statistic that is a function of the book configurations --
the sweep costs and the order flow among them.  What it cannot determine is a volume: a
level shrinks by cancellation as well as by execution, and a delta names the size now
resting at a price without saying why it changed.  That is the size-versus-volume
distinction of section 3, in the shape of a recording.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from unito26.lob.messages import BUY, SELL, LevelDelta, Message
from unito26.lob.orderbook import AggregateBook

__all__ = ["DeltaLog"]


@dataclass(frozen=True, slots=True)
class DeltaLog:
    """A replay recorded as level changes: the opening state, and what moved after it.

    A delta names only the levels a message changed, so the log determines the session
    relative to the state the replay started from; the opening book is part of the
    record and not an optional extra.

    ``times`` carries one entry per message, including the messages that changed nothing
    -- a withdrawal against an empty level produces no delta, so message boundaries
    cannot be recovered from ``entries`` by counting.
    """

    opening_bids: dict[int, int]
    opening_asks: dict[int, int]
    times: list[float]
    entries: list[tuple[int, float, LevelDelta]]
    """``(index into times, time, delta)``, in message order."""

    @classmethod
    def record(cls, book: AggregateBook, messages: Iterable[Message]) -> "DeltaLog":
        opening_bids = dict(book.levels_map(BUY))
        opening_asks = dict(book.levels_map(SELL))
        times: list[float] = []
        entries: list[tuple[int, float, LevelDelta]] = []
        for sequence, message in enumerate(messages):
            result = book.apply(message, record=True)
            times.append(message.time)
            entries += [(sequence, message.time, delta) for delta in result.deltas]
        return cls(opening_bids, opening_asks, times, entries)

    @property
    def prices(self) -> list[int]:
        """Every price the log touches, for the books that must be sized in advance."""
        return (
            list(self.opening_bids)
            + list(self.opening_asks)
            + [delta.price for _, _, delta in self.entries]
        )

    def opening_book(self, book_cls: type[AggregateBook], strict: bool) -> AggregateBook:
        """A book in the state the recorded replay began from, sized for the whole log."""
        book = book_cls.for_prices(self.prices, strict)
        for direction, levels in ((BUY, self.opening_bids), (SELL, self.opening_asks)):
            for price, resting in levels.items():
                book.set_size(direction, price, resting)
        return book

    def to_table(self):
        """Columnar table of the entries: ``(seq, time, side, price, resting)``.

        One row per level *change*, against one row per *message* for the dense form.
        The saving comes from most messages touching a single level, and from the
        ``price`` column compressing well, since consecutive changes cluster around the
        touch.
        """
        import pyarrow

        sequences, times, sides, prices, resting = [], [], [], [], []
        for sequence, time, delta in self.entries:
            sequences.append(sequence)
            times.append(time)
            sides.append(delta.side)
            prices.append(delta.price)
            resting.append(delta.resting)
        return pyarrow.table(
            {
                "seq": pyarrow.array(sequences, pyarrow.int64()),
                "time": pyarrow.array(times, pyarrow.float64()),
                "side": pyarrow.array(sides, pyarrow.int8()),
                "price": pyarrow.array(prices, pyarrow.int32()),
                "resting": pyarrow.array(resting, pyarrow.int32()),
            }
        )
