"""The fold: driving a book with a stream of messages, and recording what happened.

A book holds *one* state.  The time series of states is made here, by folding a stream
through a book, and it comes out as a :class:`MarketSession` -- a LOBSTER-shaped frame
plus the statistics read off it.

Three recorders build the same session, differing in what they ask the book for after
every message, and the statistics can be computed either during the fold or afterwards
from the finished frame.  The frame and the book do not share an indexing: the book knows
the price grid, the frame knows only the levels it reports, and
``documentation/grid-levels-and-lobster-levels.md`` is the whole of the difference.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob import frames
from unito26.lob.messages import (
    BUY,
    SELL,
    GridDepth,
    LevelDelta,
    Message,
    MessageType,
    ReportedDepth,
)
from unito26.lob.orderbook import AggregateBook, SideStatistics

__all__ = ["run", "DeltaLog", "MarketSession"]

#: Rows a recorder allocates before it has to grow.  Small enough that a short session
#: does not over-allocate, large enough that a long one doubles only a dozen times.
INITIAL_CAPACITY = 1024


def run(book: AggregateBook, messages: Iterable[Message]) -> Counter:
    """Fold the stream through the book, recording no states.  The benchmark path.

    Returns counts of what went past -- messages, trades, shares traded -- which is
    enough to tell that two implementations did the same work without the cost of
    keeping the states they passed through.
    """
    tally: Counter = Counter()
    for message in messages:
        result = book.apply(message, record=True)
        tally["messages"] += 1
        tally["fills"] += len(result.fills)
        tally["traded"] += result.market_order_size
        if message.kind is MessageType.WITHDRAW:
            tally["withdrawals"] += 1
    return tally


class _RowBuffer:
    """A two-dimensional buffer that doubles when full.

    The number of messages is not known in advance: the simulator reads the book as it
    folds, so the stream cannot be materialised first.  Doubling keeps the total copying
    linear in the number of rows, and the rows stay contiguous, so the frame at the end
    wraps one array rather than inferring a dtype from a list of lists.
    """

    def __init__(self, width: int, dtype):
        self.array = np.zeros((INITIAL_CAPACITY, width), dtype=dtype)
        self.used = 0

    def claim(self) -> int:
        """Index of the next row, growing the buffer first if it is full.

        Call this *before* reading :attr:`array`: growing replaces the array, so a
        reference taken earlier would be written into and then discarded.
        """
        if self.used == len(self.array):
            grown = np.empty((2 * len(self.array), self.array.shape[1]), self.array.dtype)
            grown[: self.used] = self.array
            self.array = grown
        self.used += 1
        return self.used - 1

    def finished(self) -> np.ndarray:
        return self.array[: self.used]


# ---- the statistics, read from a book -----------------------------------------------


def _statistic_columns(imbalance_levels: tuple[GridDepth, ...]) -> list[str]:
    names = ["Spread", "MidPrice", "MicroPrice"]
    for n in imbalance_levels:
        names += [f"QueueImbalance{n}", f"QueueImbalance{n}Covered"]
    return names + [
        "BidOccupiedLevels", "AskOccupiedLevels",
        "BidGapCount", "AskGapCount",
        "BidLargestGap", "AskLargestGap",
    ]


def _side_covers(
    side: SideStatistics, n: GridDepth, reported_depth: ReportedDepth, from_file: bool
) -> bool:
    """Whether a frame reporting this side to this depth determines ``I^n`` on it.

    Sufficient rather than necessary: an unreported level may fall below the window, in
    which case the frame is right and this says otherwise.  It is the tightest rule
    decidable from a frame, since at ``n = grid_span + 1`` the frame is equally
    consistent with a level just below the window and with a gap there.

    An empty side contributes nothing at every ``n`` and so is covered.  A side reporting
    fewer levels than the depth is fully known -- but only for a book we hold; in a file
    it means "nothing further in the visible price range", which is a weaker claim.
    """
    if side.occupied == 0:
        return True
    if n <= side.grid_span:
        return True
    return side.occupied < reported_depth and not from_file


def _write_statistics(
    book: AggregateBook,
    out: np.ndarray,
    row: int,
    reported_depth: ReportedDepth,
    imbalance_levels: tuple[GridDepth, ...],
    from_file: bool,
) -> None:
    """One row of statistics, read off the book as it currently stands.

    Restricted to ``reported_depth`` occupied levels wherever the frame would be, so the
    two ways of computing them are comparing the same quantity.  ``None`` becomes NaN
    here: the book says None for an undefined price and a frame cannot.

    Each side is read once, through :meth:`AggregateBook.side_statistics`; the individual
    statistics have their own methods, and calling those here would walk the book eight
    times per message.
    """
    def as_float(value) -> float:
        return float("nan") if value is None else float(value)

    bid = book.side_statistics(BUY, reported_depth)
    ask = book.side_statistics(SELL, reported_depth)

    target = out[row]
    target[0] = as_float(book.spread)
    target[1] = as_float(book.mid_price)
    target[2] = as_float(book.micro_price)
    column = 3
    for n in imbalance_levels:
        target[column] = book.queue_imbalance(n)
        target[column + 1] = float(
            _side_covers(bid, n, reported_depth, from_file)
            and _side_covers(ask, n, reported_depth, from_file)
        )
        column += 2
    target[column:] = (
        bid.occupied, ask.occupied,
        bid.gap_count, ask.gap_count,
        bid.largest_gap, ask.largest_gap,
    )


# ---- a replay recorded sparsely ------------------------------------------------------


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
            for price, volume in levels.items():
                book.set_volume(direction, price, volume)
        return book

    def to_table(self):
        """Columnar table of the entries: ``(seq, time, side, price, volume)``.

        One row per level *change*, against one row per *message* for the dense form.
        The saving comes from most messages touching a single level, and from the
        ``price`` column compressing well, since consecutive changes cluster around the
        touch.
        """
        import pyarrow

        sequences, times, sides, prices, volumes = [], [], [], [], []
        for sequence, time, delta in self.entries:
            sequences.append(sequence)
            times.append(time)
            sides.append(delta.side)
            prices.append(delta.price)
            volumes.append(delta.volume)
        return pyarrow.table(
            {
                "seq": pyarrow.array(sequences, pyarrow.int64()),
                "time": pyarrow.array(times, pyarrow.float64()),
                "side": pyarrow.array(sides, pyarrow.int8()),
                "price": pyarrow.array(prices, pyarrow.int32()),
                "volume": pyarrow.array(volumes, pyarrow.int32()),
            }
        )


# ---- the session ---------------------------------------------------------------------


@dataclass(eq=False)  # DataFrame fields make a generated __eq__ raise, not compare
class MarketSession:
    """A session: what the book looked like after every message, and what that implies.

    ``reported_depth`` counts occupied levels, the way a LOBSTER file does.
    ``imbalance_levels`` counts grid positions, the way section 4 does.  They are separate
    fields because they are separate quantities.

    ``stats`` is None for a session folded without online statistics; call
    :meth:`stats_from_frame` to compute them from ``lobster_book``.
    """

    reported_depth: ReportedDepth
    imbalance_levels: tuple[GridDepth, ...]
    price_unit: int
    from_file: bool
    lobster_book: pd.DataFrame
    stats: pd.DataFrame | None
    level_deltas: list[tuple[int, float, LevelDelta]] | None = None

    # ---- the frame schemas ------------------------------------------------------------
    #
    # Both are parametrized, so unlike the model parameters of `frames.FrameSerializable`
    # a session's frame shape is not fixed by its type.

    @staticmethod
    def lobster_schema(reported_depth: ReportedDepth) -> pa.DataFrameSchema:
        return frames.lobster_book_schema(reported_depth)

    @staticmethod
    def statistics_schema(imbalance_levels: tuple[GridDepth, ...]) -> pa.DataFrameSchema:
        columns = {
            name: pa.Column(float, nullable=True, coerce=True)
            for name in _statistic_columns(imbalance_levels)
        }
        for n in imbalance_levels:
            columns[f"QueueImbalance{n}Covered"] = pa.Column(
                float, pa.Check.isin((0.0, 1.0)), coerce=True
            )
        return pa.DataFrameSchema(columns, strict=True, ordered=True)

    # ---- axis C: three ways to record the same session --------------------------------

    @classmethod
    def from_occupied_levels(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        reported_depth: ReportedDepth,
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
        online_statistics: bool,
    ) -> "MarketSession":
        """Ask the book for its top ``reported_depth`` levels after every message."""
        times: list[float] = []
        rows = _RowBuffer(4 * reported_depth, np.int64)
        statistics = _RowBuffer(len(_statistic_columns(imbalance_levels)), np.float64)
        for message in messages:
            book.apply(message)
            times.append(message.time)
            index = rows.claim()
            book.write_lobster_row(rows.array, index, price_unit, reported_depth)
            if online_statistics:
                at = statistics.claim()
                _write_statistics(
                    book, statistics.array, at, reported_depth, imbalance_levels, False
                )
        return cls._assemble(
            reported_depth, imbalance_levels, price_unit,
            times, rows, statistics if online_statistics else None, None,
        )

    @classmethod
    def from_top_of_book(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
        online_statistics: bool,
    ) -> "MarketSession":
        """Read the four touch properties instead, which is a depth-1 session.

        This produces the same session as :meth:`from_occupied_levels` at
        ``reported_depth = 1``.  :meth:`AggregateBook.set_volume` removes a level whose
        volume reaches zero, so a best price always names an occupied price, and grid
        level 1 therefore coincides with occupied level 1.
        """
        depth = ReportedDepth(1)
        times: list[float] = []
        rows = _RowBuffer(4, np.int64)
        statistics = _RowBuffer(len(_statistic_columns(imbalance_levels)), np.float64)
        for message in messages:
            book.apply(message)
            times.append(message.time)
            ask, bid = book.best_ask_price, book.best_bid_price
            index = rows.claim()
            rows.array[index] = (
                frames.ASK_PADDING if ask is None else ask * price_unit,
                book.best_ask_volume,
                frames.BID_PADDING if bid is None else bid * price_unit,
                book.best_bid_volume,
            )
            if online_statistics:
                at = statistics.claim()
                _write_statistics(
                    book, statistics.array, at, depth, imbalance_levels, False
                )
        return cls._assemble(
            depth, imbalance_levels, price_unit,
            times, rows, statistics if online_statistics else None, None,
        )

    @classmethod
    def from_delta_log(
        cls,
        log: DeltaLog,
        book_cls: type[AggregateBook],
        reported_depth: ReportedDepth,
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
        online_statistics: bool,
    ) -> "MarketSession":
        """Rebuild the session from a sparse recording, with no messages and no matching.

        The log replaces the stream: applying a delta is a write of an absolute volume,
        where applying a message is a search plus a match.  What the comparison with the
        dense recorders has to include is the cost of :meth:`DeltaLog.record`, which had
        to run first.
        """
        book = log.opening_book(book_cls, False)
        times = log.times
        rows = _RowBuffer(4 * reported_depth, np.int64)
        statistics = _RowBuffer(len(_statistic_columns(imbalance_levels)), np.float64)
        pending = iter(log.entries)
        upcoming = next(pending, None)
        for sequence in range(len(times)):
            while upcoming is not None and upcoming[0] == sequence:
                _, _, delta = upcoming
                book.set_volume(delta.side, delta.price, delta.volume)
                upcoming = next(pending, None)
            index = rows.claim()
            book.write_lobster_row(rows.array, index, price_unit, reported_depth)
            if online_statistics:
                at = statistics.claim()
                _write_statistics(
                    book, statistics.array, at, reported_depth, imbalance_levels, False
                )
        return cls._assemble(
            reported_depth, imbalance_levels, price_unit,
            times, rows, statistics if online_statistics else None, log.entries,
        )

    @classmethod
    def _assemble(
        cls,
        reported_depth: ReportedDepth,
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
        times: list[float],
        rows: _RowBuffer,
        statistics: _RowBuffer | None,
        deltas: list[tuple[int, float, LevelDelta]] | None,
    ) -> "MarketSession":
        index = pd.Index(times, name="TimeStamp")
        book_frame = pd.DataFrame(
            rows.finished(), columns=frames.lobster_book_columns(reported_depth), index=index
        )
        stats = None if statistics is None else pd.DataFrame(
            statistics.finished(), columns=_statistic_columns(imbalance_levels), index=index
        )
        return cls(
            reported_depth=reported_depth,
            imbalance_levels=imbalance_levels,
            price_unit=price_unit,
            from_file=False,
            lobster_book=cls.lobster_schema(reported_depth).validate(book_frame),
            stats=stats,
            level_deltas=deltas,
        )

    # ---- the statistics, computed from the finished frame -----------------------------

    def _side(self, side: str, padding: int) -> tuple[np.ndarray, np.ndarray]:
        depth = self.reported_depth
        prices = self.lobster_book[
            [f"{side}Price{k}" for k in range(1, depth + 1)]
        ].to_numpy(dtype=float)
        sizes = self.lobster_book[
            [f"{side}Size{k}" for k in range(1, depth + 1)]
        ].to_numpy(dtype=float)
        return np.where(prices == padding, np.nan, prices) / self.price_unit, sizes

    def stats_from_frame(self) -> pd.DataFrame:
        """Recompute every statistic from ``lobster_book``, touching no book.

        Two things make this harder than it looks, and both return a plausible number
        when got wrong.  Levels are selected **by price**, never by column position: on a
        book with holes the k-th column is not the k-th grid level, so a column slice
        computes a different statistic under the same name.  And the sums are masked
        explicitly rather than left to ``sum``, whose default skips NaN and so treats a
        missing level as absent instead of unknown.
        """
        ask_prices, ask_sizes = self._side("Ask", frames.ASK_PADDING)
        bid_prices, bid_sizes = self._side("Bid", frames.BID_PADDING)
        best_ask, best_bid = ask_prices[:, 0], bid_prices[:, 0]

        ask_here, bid_here = ~np.isnan(ask_prices), ~np.isnan(bid_prices)
        ask_top, bid_top = ask_sizes[:, 0], bid_sizes[:, 0]
        touch = ask_top + bid_top

        columns = {
            "Spread": best_ask - best_bid,
            "MidPrice": (best_ask + best_bid) / 2,
            "MicroPrice": np.where(
                touch > 0,
                (best_ask * bid_top + best_bid * ask_top) / np.where(touch > 0, touch, 1),
                np.nan,
            ),
        }

        # Filled rather than nan-aggregated: an entirely padded side is all-NaN, which
        # nanmax warns about and answers NaN to.  Its span is 0.
        ask_count, bid_count = ask_here.sum(1), bid_here.sum(1)
        deepest_ask = np.where(ask_here, ask_prices, -np.inf).max(1)
        deepest_bid = np.where(bid_here, bid_prices, np.inf).min(1)
        ask_span = np.where(ask_count > 0, deepest_ask - best_ask + 1, 0)
        bid_span = np.where(bid_count > 0, best_bid - deepest_bid + 1, 0)

        for n in self.imbalance_levels:
            in_ask = ask_here & (ask_prices <= best_ask[:, None] + (n - 1))
            in_bid = bid_here & (bid_prices >= best_bid[:, None] - (n - 1))
            ask_total = np.where(in_ask, ask_sizes, 0.0).sum(1)
            bid_total = np.where(in_bid, bid_sizes, 0.0).sum(1)
            total = ask_total + bid_total
            covered = self._covers(n, ask_span, ask_count) & self._covers(n, bid_span, bid_count)
            imbalance = np.where(
                total > 0, (bid_total - ask_total) / np.where(total > 0, total, 1), np.nan
            )
            columns[f"QueueImbalance{n}"] = np.where(covered, imbalance, np.nan)
            columns[f"QueueImbalance{n}Covered"] = covered.astype(float)

        columns["BidOccupiedLevels"] = bid_count.astype(float)
        columns["AskOccupiedLevels"] = ask_count.astype(float)
        bid_gaps = -np.diff(bid_prices, axis=1) - 1  # bid prices descend with level
        ask_gaps = np.diff(ask_prices, axis=1) - 1
        for name, gaps in (("Bid", bid_gaps), ("Ask", ask_gaps)):
            positive = np.where(np.isnan(gaps), 0.0, np.maximum(gaps, 0.0))
            columns[f"{name}GapCount"] = (positive > 0).sum(1).astype(float)
            columns[f"{name}LargestGap"] = positive.max(1) if positive.size else 0.0
        return pd.DataFrame(columns, index=self.lobster_book.index, dtype=float)[
            _statistic_columns(self.imbalance_levels)
        ]

    def column_sliced_imbalance(self, n: GridDepth) -> pd.Series:
        """The imbalance computed from the first ``n`` size *columns* of the frame.

        This is not ``I^n``.  Section 4 sums volume over the first ``n`` positions on the
        price grid; summing the first ``n`` columns sums the first ``n`` prices that carry
        volume, and the two windows coincide only where the reported levels are
        contiguous.  Kept because the difference is invisible in the output -- both stay
        in ``[-1, 1]`` and both move with the market -- and because it is what a column
        slice of a LOBSTER file gives.
        """
        if n <= 0:
            raise ValueError(f"n counts levels from the touch and must be >= 1, got {n}")
        width = min(int(n), self.reported_depth)
        bids = self.lobster_book[[f"BidSize{k}" for k in range(1, width + 1)]].sum(axis=1)
        asks = self.lobster_book[[f"AskSize{k}" for k in range(1, width + 1)]].sum(axis=1)
        total = bids + asks
        return ((bids - asks) / total.where(total > 0)).astype(float)

    def _covers(self, n: GridDepth, span, count):
        """Per side; the caller conjoins.  See :func:`_side_covers` for why it is one-way."""
        fully_reported = (
            count < self.reported_depth if not self.from_file
            else np.zeros_like(count, dtype=bool)
        )
        return (count == 0) | (n <= span) | fully_reported
