"""The fold: driving a book with a stream of messages, and recording what happened.

A book holds *one* state.  The time series of states is made here, by folding a stream
through a book, and it comes out as a :class:`MarketSession` -- a LOBSTER-shaped frame
plus the statistics read off it.

The same session is reachable three ways, and they must agree.  Two of them are recording
strategies, which differ in what they ask the book for; the third route recomputes the
statistics from the finished frame instead of from the book.  What that last pair does
*not* share is the indexing: the book knows the price grid, the frame knows only the
levels it reports, and section "the two indexings" of
``documentation/grid-levels-and-lobster-levels.md`` is the whole of the difference.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

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
from unito26.lob.orderbook import AggregateBook

__all__ = ["run", "MarketSession", "deltas_to_table"]


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


def _book_statistics(
    book: AggregateBook,
    reported_depth: ReportedDepth,
    imbalance_levels: tuple[GridDepth, ...],
    from_file: bool,
) -> list[float]:
    """One row of statistics, read off the book as it currently stands.

    Restricted to ``reported_depth`` occupied levels wherever the frame route would be,
    so the two routes are comparing the same quantity.  ``None`` becomes NaN here: the
    book says None for an undefined price and a frame cannot.
    """
    def nan_if_none(value):
        return float("nan") if value is None else float(value)

    row = [nan_if_none(book.spread), nan_if_none(book.mid_price), nan_if_none(book.micro_price)]
    for n in imbalance_levels:
        row.append(book.queue_imbalance(n))
        row.append(float(_book_covers(book, n, reported_depth, from_file)))
    for direction in (BUY, SELL):
        row.append(float(book.occupied_level_count(direction, reported_depth)))
    for direction in (BUY, SELL):
        row.append(float(book.gap_count(direction, reported_depth)))
    for direction in (BUY, SELL):
        row.append(float(book.largest_gap_size_between_non_empty_levels(direction, reported_depth)))
    return row


def _book_covers(
    book: AggregateBook, n: GridDepth, reported_depth: ReportedDepth, from_file: bool
) -> bool:
    """Whether a frame of this depth could answer ``I^n``, side by side then conjoined.

    Sufficient rather than necessary: an unreported level may fall below the window, in
    which case the frame is right and this says otherwise.  It is the tightest rule
    *decidable from a frame*, since at ``n = grid_span + 1`` the frame is equally
    consistent with a level just below the window and with a gap there.
    """
    for direction in (BUY, SELL):
        count = book.occupied_level_count(direction, reported_depth)
        if count == 0:
            continue
        if n <= book.grid_span(direction, reported_depth):
            continue
        # A side reporting fewer levels than the depth is fully known -- but only for a
        # book we hold.  In a file it means "nothing more in the visible price range",
        # which is not the same claim.
        if count < reported_depth and not from_file:
            continue
        return False
    return True


def _statistic_columns(imbalance_levels: tuple[GridDepth, ...]) -> list[str]:
    names = ["Spread", "MidPrice", "MicroPrice"]
    for n in imbalance_levels:
        names += [f"QueueImbalance{n}", f"QueueImbalance{n}Covered"]
    return names + [
        "BidOccupiedLevels", "AskOccupiedLevels",
        "BidGapCount", "AskGapCount",
        "BidLargestGap", "AskLargestGap",
    ]


@dataclass(eq=False)  # DataFrame fields make a generated __eq__ raise, not compare
class MarketSession:
    """A session: what the book looked like after every message, and what that implies.

    ``reported_depth`` counts occupied levels, the way a LOBSTER file does.
    ``imbalance_levels`` counts grid positions, the way section 4 does.  They are separate
    fields because they are separate quantities.
    """

    reported_depth: ReportedDepth
    imbalance_levels: tuple[GridDepth, ...]
    price_unit: int
    from_file: bool
    lobster_book: pd.DataFrame
    stats: pd.DataFrame
    level_deltas: list[tuple[int, float, LevelDelta]] | None = None

    # ---- axis C: three ways to record the same session ---------------------------

    @classmethod
    def from_occupied_levels(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        reported_depth: ReportedDepth,
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
        record_deltas: bool = False,
    ) -> "MarketSession":
        """Ask the book for its top ``reported_depth`` levels after every message."""
        times, rows, statistics = [], [], []
        deltas: list[tuple[int, float, LevelDelta]] = []
        for sequence, message in enumerate(messages):
            result = book.apply(message)
            times.append(message.time)
            rows.append(frames.book_to_lobster_row(book, price_unit, reported_depth))
            statistics.append(_book_statistics(book, reported_depth, imbalance_levels, False))
            if record_deltas:
                deltas += [(sequence, message.time, delta) for delta in result.deltas]
        return cls._assemble(
            reported_depth, imbalance_levels, price_unit,
            times, rows, statistics, deltas if record_deltas else None,
        )

    @classmethod
    def from_top_of_book(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
    ) -> "MarketSession":
        """Read the four touch properties instead, which is a depth-1 session.

        It must equal ``from_occupied_levels`` at ``reported_depth = 1``, and that is not
        luck: ``set_volume`` removes a level whose queue empties, so the best price always
        names an occupied level and grid level 1 is occupied level 1.
        """
        depth = ReportedDepth(1)
        times, rows, statistics = [], [], []
        for message in messages:
            book.apply(message)
            times.append(message.time)
            ask, bid = book.best_ask_price, book.best_bid_price
            rows.append([
                frames.ASK_PADDING if ask is None else ask * price_unit, book.best_ask_volume,
                frames.BID_PADDING if bid is None else bid * price_unit, book.best_bid_volume,
            ])
            statistics.append(_book_statistics(book, depth, imbalance_levels, False))
        return cls._assemble(depth, imbalance_levels, price_unit, times, rows, statistics, None)

    @classmethod
    def from_level_deltas(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        reported_depth: ReportedDepth,
        imbalance_levels: tuple[GridDepth, ...],
        price_unit: int,
    ) -> "MarketSession":
        """Record only what each message changed, then rebuild the session from that.

        Deltas are cheap to *store* -- most messages touch one level -- and that saving is
        real.  Reconstruction is not cheap: a delta says nothing about the levels a message
        left alone, so the frame needs full book state at every step and this route is a
        second fold.  It should therefore time worse than recording densely, and the point
        of having it is that it must produce the identical session.
        """
        opening = {direction: dict(book.levels_map(direction)) for direction in (BUY, SELL)}
        times, deltas = [], []
        for sequence, message in enumerate(messages):
            result = book.apply(message)
            times.append(message.time)
            deltas += [(sequence, message.time, delta) for delta in result.deltas]

        # Sized for every price the replay will touch, not just the opening state: a
        # band-indexed book refuses a write outside its band, and the deltas roam.
        shadow = type(book).for_prices(
            list(opening[BUY]) + list(opening[SELL]) + [delta.price for _, _, delta in deltas],
            book.strict,
        )
        for direction in (BUY, SELL):
            for price, volume in opening[direction].items():
                shadow.set_volume(direction, price, volume)
        rows, statistics = [], []
        pending = iter(deltas)
        upcoming = next(pending, None)
        for sequence in range(len(times)):
            while upcoming is not None and upcoming[0] == sequence:
                _, _, delta = upcoming
                shadow.set_volume(delta.side, delta.price, delta.volume)
                upcoming = next(pending, None)
            rows.append(frames.book_to_lobster_row(shadow, price_unit, reported_depth))
            statistics.append(_book_statistics(shadow, reported_depth, imbalance_levels, False))
        return cls._assemble(
            reported_depth, imbalance_levels, price_unit, times, rows, statistics, deltas
        )

    @classmethod
    def _assemble(cls, reported_depth, imbalance_levels, price_unit, times, rows, statistics, deltas):
        index = pd.Index(times, name="TimeStamp")
        book_frame = pd.DataFrame(
            rows, columns=frames.lobster_book_columns(reported_depth), index=index
        )
        stats = pd.DataFrame(
            statistics, columns=_statistic_columns(imbalance_levels), index=index, dtype=float
        )
        return cls(
            reported_depth=reported_depth,
            imbalance_levels=imbalance_levels,
            price_unit=price_unit,
            from_file=False,
            lobster_book=frames.lobster_book_schema(reported_depth).validate(book_frame),
            stats=stats,
            level_deltas=deltas,
        )

    # ---- the other route: the same statistics, from the frame alone ----------------

    def _side(self, side: str, padding: int):
        depth = self.reported_depth
        prices = self.lobster_book[[f"{side}Price{k}" for k in range(1, depth + 1)]].to_numpy(dtype=float)
        sizes = self.lobster_book[[f"{side}Size{k}" for k in range(1, depth + 1)]].to_numpy(dtype=float)
        return np.where(prices == padding, np.nan, prices) / self.price_unit, sizes

    def stats_from_frame(self) -> pd.DataFrame:
        """Recompute every statistic from ``lobster_book``, touching no book.

        Two things make this harder than it looks, and both return a plausible number when
        got wrong.  Levels are selected **by price**, never by column position: on a book
        with holes the k-th column is not the k-th grid level, so a column slice computes a
        different statistic under the same name.  And the sums are masked explicitly rather
        than left to ``sum``, whose default skips NaN and so quietly treats a missing level
        as absent instead of unknown.
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
                touch > 0, (best_ask * bid_top + best_bid * ask_top) / np.where(touch > 0, touch, 1), np.nan
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
            ask_total = (np.where(in_ask, ask_sizes, 0.0)).sum(1)
            bid_total = (np.where(in_bid, bid_sizes, 0.0)).sum(1)
            total = ask_total + bid_total
            covered = self._covers(n, ask_span, ask_count) & self._covers(n, bid_span, bid_count)
            imbalance = np.where(total > 0, (bid_total - ask_total) / np.where(total > 0, total, 1), np.nan)
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
        return pd.DataFrame(
            columns, index=self.lobster_book.index, dtype=float
        )[_statistic_columns(self.imbalance_levels)]

    def _covers(self, n: GridDepth, span, count):
        """Per side; the caller conjoins.  See :func:`_book_covers` for why it is one-way."""
        fully_reported = count < self.reported_depth if not self.from_file else np.zeros_like(count, dtype=bool)
        return (count == 0) | (n <= span) | fully_reported


def deltas_to_table(rows: Iterable[tuple[int, float, LevelDelta]]):
    """Columnar table of level deltas: ``(seq, time, side, price, volume)``.

    One row per level *change*, against one row per *message* for the dense form.  The
    saving comes from most messages touching a single level, and from the ``price``
    column compressing extremely well, since consecutive changes cluster around the touch.
    """
    import pyarrow

    sequences, times, sides, prices, volumes = [], [], [], [], []
    for sequence, time, delta in rows:
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
