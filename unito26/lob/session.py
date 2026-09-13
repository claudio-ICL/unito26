"""The session: the time series of book states, and the statistics read off it.

A book holds *one* state.  The series of states is a :class:`MarketSession` -- a
LOBSTER-shaped frame plus what follows from it -- and this module is that type and the
ways of building one.  Three fold a stream of messages through a book, differing in what
they ask the book for after every message; a fourth replays a delta log and folds nothing.

A LOBSTER pair is *not* among them.  Its rows are executions of resting orders where these
are messages, so it is read as a ``LobsterMarketSession`` and coarsened -- see
``unito26.lob.lobster_session``, which is the only route from one to the other.

The statistics are computed twice over: once during a fold, from a live book, and once
from the finished frame.  The two routes are written beside each other because the claim
that they agree is checked by reading them against each other, and asserted in
``tests/lob/test_market_session.py``.

The frame and the book do not share an indexing: the book knows the price grid, the frame
knows only the levels it reports, and
``documentation/grid-levels-and-lobster-levels.md`` is the whole of the difference.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from operator import length_hint
from typing import Iterable

import numpy as np
import pandas as pd

from unito26.lob import frames
from unito26.lob.delta_log import DeltaLog
from unito26.lob.messages import (
    BUY,
    SELL,
    GridDepth,
    LevelDelta,
    Message,
    MessageType,
    PriceUnit,
    ReportedDepth,
    SweepSize,
    Window,
)
from unito26.lob.orderbook import AggregateBook, SideStatistics, _sweep_cost
from unito26.lob.statistics import SessionStatistics, _span, _whole

__all__ = ["run", "window_start", "rolling_sum", "MarketSession"]

def _quotient(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """``numerator / denominator`` where the denominator is positive, NaN elsewhere.

    Every ratio here divides a sum by a count of the same terms, so an empty window -- or a
    pair of empty level windows -- divides zero by zero.  ``where`` skips those entries
    instead of dividing by a stand-in and masking the result afterwards, so the invalid-value
    flag is never raised and there is no warning to suppress.
    """
    return np.divide(
        numerator,
        denominator,
        out=np.full(len(denominator), np.nan),
        where=denominator > 0,
    )


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
        book.apply(message, record=False)
        tally["messages"] += 1
        tally["fills"] += book.last_fill_count
        tally["traded"] += book.last_traded_size
        if message.kind is MessageType.WITHDRAW:
            tally["withdrawals"] += 1
    return tally


class _RowBuffer:
    """A two-dimensional buffer, sized ahead where the length is known.

    A list of messages knows its own length; the live simulator stream does not, since it
    reads the book as it folds and so cannot be materialised first.
    :func:`operator.length_hint` is exactly that distinction -- the exact length for a
    list, zero for a generator -- and where it answers zero the buffer doubles instead,
    which keeps the total copying linear.  A hint is documented as an estimate, so both
    directions stay open: too large is trimmed by :meth:`finished`, too small still
    grows.

    ``background`` is the row every unwritten row already holds, and carries the dtype.
    A recorder that writes only the levels a book has depends on it being there, so it is
    laid down at allocation *and* over every grown tail: growth allocates with
    ``np.empty``, and a row past a growth boundary would otherwise carry freed memory
    into the frame -- as plausible small integers that pass the schema.
    """

    def __init__(self, background: np.ndarray, expected: int):
        self.background = background
        capacity = expected if expected > 0 else INITIAL_CAPACITY
        self.array = np.empty((capacity, len(background)), background.dtype)
        self.array[:] = background
        self.used = 0

    def claim(self) -> int:
        """Index of the next row, growing the buffer first if it is full.

        Call this *before* reading :attr:`array`: growing replaces the array, so a
        reference taken earlier would be written into and then discarded.
        """
        if self.used == len(self.array):
            grown = np.empty((2 * len(self.array), self.array.shape[1]), self.array.dtype)
            grown[: self.used] = self.array[: self.used]
            grown[self.used:] = self.background
            self.array = grown
        self.used += 1
        return self.used - 1

    def finished(self) -> np.ndarray:
        return self.array[: self.used]


def _book_buffer(reported_depth: ReportedDepth, expected: int) -> _RowBuffer:
    """Rows of a LOBSTER book, padded before anything is written into them."""
    return _RowBuffer(frames.lobster_padding_row(reported_depth), expected)


def _statistics_buffer(spec: SessionStatistics, expected: int) -> _RowBuffer:
    """Rows of statistics.  Every column is written every time, so the background is
    only somewhere for the dtype to live -- which is why the buffer is sized to the row
    schema and not to the whole statistics frame."""
    return _RowBuffer(np.zeros(len(spec.row_schema().columns), dtype=np.float64), expected)


def _trades_buffer(spec: SessionStatistics, expected: int) -> _RowBuffer:
    """Rows of what traded: volume, signed volume and value, per message."""
    return _RowBuffer(
        np.zeros(len(spec.trade_row_schema().columns), dtype=np.float64), expected
    )


# ---- the statistics, read from a book -----------------------------------------------


def _side_covers(
    side: SideStatistics, n: GridDepth, reported_depth: ReportedDepth, truncated: bool
) -> bool:
    """Whether a frame reporting this side to this depth determines ``I^n`` on it.

    Sufficient rather than necessary: an unreported level may fall below the window, in
    which case the frame is right and this says otherwise.  It is the tightest rule
    decidable from a frame, since at ``n = grid_span + 1`` the frame is equally
    consistent with a level just below the window and with a gap there.

    An empty side contributes nothing at every ``n`` and so is covered.  A side reporting
    fewer levels than the depth is fully known -- unless the view is truncated, where it
    means only "nothing further in the visible price range".
    """
    if side.occupied == 0:
        return True
    if n <= side.grid_span:
        return True
    return side.occupied < reported_depth and not truncated


def _sweep_covers(
    side: SideStatistics,
    cost: float | None,
    mid: float | None,
    reported_depth: ReportedDepth,
    truncated: bool,
) -> bool:
    """Whether the frame determines the sweep cost, filled or not.

    Three cases, and only the first two are "covered".  The sweep filled, so the answer is
    a number.  Or it did not fill and the side genuinely ran out short of the reported
    depth, so the answer is that this size cannot be bought at any price -- a true answer,
    reported as NaN.  Or the window simply ended, and nothing is known.

    Conjoined with the mid existing, which the plain ``occupied`` rule cannot see: a frame
    with three ask levels and a padded bid side fills a buy perfectly well and still
    answers NaN, because what is missing is the *benchmark*.  Without this clause the flag
    would promise a determined answer where there is none.  :func:`_side_covers` gets this
    for nothing, being conjoined over both sides by its caller.
    """
    if mid is None:
        return False
    if cost is not None:
        return True
    return side.occupied < reported_depth and not truncated


def _touch(bid: SideStatistics, ask: SideStatistics) -> tuple:
    """``((P^b, S^b), (P^a, S^a))``, with None for a side that is not there."""
    return (
        bid.levels[0] if bid.levels else None,
        ask.levels[0] if ask.levels else None,
    )


def _order_flow_contribution(previous: tuple | None, current: tuple) -> float:
    """``e_n``: what one event contributed to the order flow imbalance.

    Both bid indicators fire when the best bid price is unchanged, so such an event
    contributes ``S^b_n - S^b_{n-1}``, the change in size at the touch; an event that moves
    the best bid contributes a whole queue.  Writing this as a single ``where`` on
    ``P^b_n >= P^b_{n-1}`` loses that case, which is most of the events.

    NaN when either state has a side missing, and NaN on the first row.  Not zero: zero is
    the claim that no flow was observed, where the truth is that nothing can be said.  The
    fold does hold the opening book and could answer the first row; it declines to, so that
    the frame route -- which has no predecessor at all -- gives the same series.
    """
    if previous is None:
        return float("nan")
    (bid_before, ask_before), (bid_now, ask_now) = previous, current
    if None in (bid_before, ask_before, bid_now, ask_now):
        return float("nan")
    bid = (
        (bid_now[0] >= bid_before[0]) * bid_now[1] - (bid_now[0] <= bid_before[0]) * bid_before[1]
    )
    ask = (
        (ask_now[0] <= ask_before[0]) * ask_now[1] - (ask_now[0] >= ask_before[0]) * ask_before[1]
    )
    return float(bid - ask)


def _write_statistics(
    book: AggregateBook,
    out: np.ndarray,
    row: int,
    reported_depth: ReportedDepth,
    spec: SessionStatistics,
    truncated: bool,
    bid: SideStatistics,
    ask: SideStatistics,
    previous_touch: tuple | None,
) -> tuple:
    """One row of statistics, read off the book as it currently stands.

    Restricted to ``reported_depth`` occupied levels wherever the frame would be, so the
    two ways of computing them are comparing the same quantity.  ``None`` becomes NaN
    here: the book says None for an undefined price and a frame cannot.

    Each side is read once, through :meth:`AggregateBook.side_statistics`; the individual
    statistics have their own methods, and calling those here would walk the book once per
    statistic.  The caller passes the two readings in, because it needs them itself -- the
    LOBSTER row is written from the same levels, and so are the sweep costs, which
    therefore cost no walk of their own.  On a deep book that reuse is most of what a sweep
    would otherwise cost, since walking the side dominates accumulating along it;
    ``notebooks/the-cost-of-the-statistics.ipynb`` is where the two are separated.

    Every position comes from ``spec.layout``, which found it by name in the declaration
    the schema is built from, so the row cannot be filled in an order the frame does not
    expect.

    Returns the touch it read, which the caller carries into the next call: ``e_n`` is the
    one statistic here that is a function of two states rather than one.
    """
    def as_float(value) -> float:
        return float("nan") if value is None else float(value)

    target = out[row]
    at = spec.layout
    mid = book.mid_price
    target[at.spread] = as_float(book.spread)
    target[at.mid_price] = as_float(mid)
    target[at.micro_price] = as_float(book.micro_price)
    for column, n, imbalance in zip(
        at.imbalance, spec.imbalance_levels,
        book.queue_imbalance_profile(spec.imbalance_levels),
    ):
        target[column] = imbalance
        target[column + 1] = float(
            _side_covers(bid, n, reported_depth, truncated)
            and _side_covers(ask, n, reported_depth, truncated)
        )
    buys = _sweep_cost(ask.levels, mid, spec.sweep_sizes, BUY)
    sells = _sweep_cost(bid.levels, mid, spec.sweep_sizes, SELL)
    for index, (buy_at, sell_at) in enumerate(at.sweep):
        for column, side, cost in (
            (buy_at, ask, buys[index]), (sell_at, bid, sells[index])
        ):
            target[column] = as_float(cost)
            target[column + 1] = float(
                _sweep_covers(side, cost, mid, reported_depth, truncated)
            )
    touch = _touch(bid, ask)
    target[at.order_flow] = _order_flow_contribution(previous_touch, touch)
    target[at.touch_depth] = (
        float("nan") if None in touch else float(touch[0][1] + touch[1][1])
    )
    target[at.gaps] = (
        bid.occupied, ask.occupied,
        bid.gap_count, ask.gap_count,
        bid.largest_gap, ask.largest_gap,
        as_float(bid.first_gap_distance), as_float(ask.first_gap_distance),
        bid.first_gap_size, ask.first_gap_size,
        as_float(bid.largest_gap_distance), as_float(ask.largest_gap_distance),
    )
    return touch


def _write_occupied_levels(
    target: np.ndarray,
    bid: SideStatistics,
    ask: SideStatistics,
    price_unit: PriceUnit,
    reported_depth: ReportedDepth,
) -> None:
    """A LOBSTER row from the levels the statistics already walked for.

    :meth:`AggregateBook.side_statistics` carries ``levels``, which *is*
    ``occupied_levels(direction, reported_depth)`` -- the same call -- so a fold computing
    the statistics has already paid for the walk that :meth:`to_lobster_row` would make
    again.

    Only the occupied levels are written.  ``target`` must already hold
    :func:`~unito26.lob.frames.lobster_padding_row`, which is what a row of a buffer from
    :func:`_book_buffer` holds; a row taken from anywhere else would keep whatever was
    there beyond the last level.
    """
    for offset, side in enumerate((ask, bid)):
        column = 2 * offset
        for level, (price, size) in enumerate(side.levels):
            target[4 * level + column] = price * price_unit
            target[4 * level + column + 1] = size


def _write_trades(
    book: AggregateBook, out: np.ndarray, row: int, direction: int
) -> None:
    """What the last message traded: volume, signed volume, and value.

    Read off the counters :meth:`AggregateBook.submit` keeps, so nothing was recorded and
    nothing allocated.  ``SignedVolume`` is section 7's ``V``, positive for a buy;
    ``Volume`` is the unsigned aggregate of section 3.  The notation reuses one letter for
    both and says outright that Python names must not, which is why there are two columns.

    ``TradedValue`` is in **tick-shares**: prices are tick counts everywhere inside the
    package, where ``lobster_book`` holds them in the file's units.
    """
    traded = book.last_traded_size
    out[row] = (traded, direction * traded, book.last_traded_value)


# ---- the same two statistics, read off a frame -----------------------------------------


def _frame_sweep_cost(
    prices: np.ndarray,
    sizes: np.ndarray,
    mid: np.ndarray,
    size: SweepSize,
    direction: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Sweep cost per row, and whether the reported levels filled the size.

    ``before`` is the size resting strictly above each level, and it is computed from the
    sizes **unmasked**.  That is what makes a padded level transparent: its size is zero,
    so it consumes nothing and the level below it still sees the right running total.
    Masking the sizes the way the prices are masked looks tidier and sends ``before`` to
    NaN for every level under a padded one.

    The ``where`` on the value is load-bearing for the mirror-image reason: a padded level
    has size 0 and price NaN, and ``0 * nan`` is NaN, silently and without a warning.
    """
    before = np.cumsum(sizes, axis=1) - sizes
    taken = np.clip(size - before, 0.0, sizes)
    filled = taken.sum(1) >= size
    value = np.where(taken > 0, taken * prices, 0.0).sum(1)
    return np.where(filled, direction * (value / size - mid), np.nan), filled


def _frame_order_flow(
    bid_price: np.ndarray, bid_size: np.ndarray,
    ask_price: np.ndarray, ask_size: np.ndarray,
) -> np.ndarray:
    """``e_n`` from consecutive touches.  See :func:`_order_flow_contribution`.

    The mask is not implied by the formula and has to be written: a padded touch gives a
    NaN price, ``NaN >= NaN`` is False, so both indicators are False and the expression
    evaluates to a perfectly ordinary zero where the event is undefined.
    """
    contribution = np.full(len(bid_price), np.nan)
    if len(bid_price) < 2:
        return contribution
    now, before = slice(1, None), slice(None, -1)
    bid = (
        (bid_price[now] >= bid_price[before]) * bid_size[now]
        - (bid_price[now] <= bid_price[before]) * bid_size[before]
    )
    ask = (
        (ask_price[now] <= ask_price[before]) * ask_size[now]
        - (ask_price[now] >= ask_price[before]) * ask_size[before]
    )
    known = (
        np.isfinite(bid_price[now]) & np.isfinite(bid_price[before])
        & np.isfinite(ask_price[now]) & np.isfinite(ask_price[before])
    )
    contribution[1:] = np.where(known, bid - ask, np.nan)
    return contribution


# ---- the windows, shared by both routes -------------------------------------------------
#
# A window is a reduction over a recorded series, not a statistic of the book, so it is
# made once here rather than carried through the fold.  Every rolling column is one
# difference of a cumulative sum, and every window's search is shared by the four series
# that use it.


def window_start(times: np.ndarray, window: float) -> np.ndarray:
    """First index inside ``(t - window, t]``, for every ``t`` in ``times``.

    ``side="right"`` puts an event exactly ``window`` old outside the window, and events
    sharing a timestamp with ``t - window`` outside it too.  The right edge is the current
    row: the sum runs over ``[start, i]``, so two rows at the same timestamp get different
    windows and row ``i`` does not see row ``i + 1``.  That is the causal reading, and it
    is what a hand-check at a repeated timestamp -- of which LOBSTER has many -- will
    otherwise fail to reproduce.

    Exactness at the boundary needs a whole ``window``: ``t - window`` is then exact at
    LOBSTER's seconds-after-midnight offsets, and the boundary is where it says it is.
    The declared statistics keep that restriction, a window there being part of a column's
    name (:func:`unito26.lob.statistics._whole`).  A float window is admitted for the
    long-form results, where a window is a value rather than a name, at the cost of some
    ``4e-12`` of slack that can land on the wrong side of an exact tie.
    """
    return np.searchsorted(times, times - window, side="right")


def rolling_sum(start: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Sum of ``values`` over each window, by differencing a cumulative sum.

    Exact rather than merely accurate, which is why this is preferred to a sliding window:
    prices are integer ticks and sizes integer shares, so every partial sum is an
    integer-valued float64, and it stays below 2**53 by four orders of magnitude over a
    full session.
    """
    cumulative = np.concatenate(([0.0], np.cumsum(values)))
    return cumulative[1:] - cumulative[start]


def _with_rolling(
    spec: SessionStatistics, clock: np.ndarray, rows: np.ndarray
) -> dict[str, np.ndarray]:
    """The statistics frame: the recorded rows, plus what windows make of two of them."""
    columns = {name: rows[:, i] for i, name in enumerate(spec.row_schema().columns)}
    flow, depth = columns["OrderFlowContribution"], columns["TouchDepth"]
    undefined = np.isnan(flow).astype(float)
    measured = np.isfinite(depth).astype(float)
    for window in spec.windows:
        start = window_start(clock, window)
        missing = rolling_sum(start, undefined)
        # Two sums rather than one: a NaN inside a cumulative sum poisons every window
        # after it, where the count confines it to the windows that contain it.
        columns[f"OrderFlowImbalance{window}"] = np.where(
            missing > 0, np.nan, rolling_sum(start, np.nan_to_num(flow))
        )
        columns[f"OrderFlowImbalance{window}Covered"] = (missing == 0).astype(float)
        events = rolling_sum(start, measured)
        columns[f"AverageDepth{window}"] = _quotient(
            rolling_sum(start, np.nan_to_num(depth)), 2 * events
        )
    return columns


def _with_vwap(
    spec: SessionStatistics, clock: np.ndarray, rows: np.ndarray
) -> dict[str, np.ndarray]:
    """The trades frame: what traded per message, and the VWAPs over the windows."""
    columns = {name: rows[:, i] for i, name in enumerate(spec.trade_row_schema().columns)}
    volume, signed, value = (columns[n] for n in ("Volume", "SignedVolume", "TradedValue"))
    for window in spec.windows:
        start = window_start(clock, window)
        for label, taken in (
            ("", volume > 0), ("Buy", signed > 0), ("Sell", signed < 0)
        ):
            traded = rolling_sum(start, np.where(taken, volume, 0.0))
            # A window that traded nothing has no price.  Not zero, which is a price.
            columns[f"VWAP{label}{window}"] = _quotient(
                rolling_sum(start, np.where(taken, value, 0.0)), traded
            )
    return columns


# ---- the statistics an assembled frame determines ---------------------------------------
#
# Read off a frame of book states and its clock, and nothing else.  Free functions rather
# than methods because two session types compute them -- one whose rows are messages and one
# whose rows are executions of resting orders -- and the arithmetic is the same for both.
# What differs is the index the answer is laid out over, so the frame comes back unvalidated
# and each caller validates against its own schema.


@dataclass(frozen=True, slots=True)
class _SideShape:
    """One side of a frame, per row: how many levels it reports, and how far they reach.

    The frame-route counterpart of :class:`~unito26.lob.orderbook.SideStatistics`, named
    after it.  Two arrays of one shape and opposite meanings, which is why they travel as
    one object rather than as two arguments a caller could exchange in silence.
    """

    occupied: np.ndarray
    grid_span: np.ndarray


@dataclass(frozen=True, slots=True)
class _SideGaps:
    """The holes on one side, per row and per reported level.

    ``sizes`` counts the grid positions a gap spans; ``starts`` says how far from the touch
    it opens.  Same shape again, and exchanged they answer a distance where a length was
    asked for.
    """

    sizes: np.ndarray
    starts: np.ndarray


def _side(
    book: pd.DataFrame, side: str, reported_depth: ReportedDepth, price_unit: PriceUnit
) -> tuple[np.ndarray, np.ndarray]:
    """One side's prices and sizes: prices in ticks, a padded level NaN, sizes as written.

    The prices divide an already-checked frame.  ``lobster.prices_on_the_tick_grid`` refuses
    an off-grid book once, at load, which is what lets this divide without a remainder test
    per statistic.
    """
    padding = frames.ASK_PADDING if side == "Ask" else frames.BID_PADDING
    prices = book[
        [f"{side}Price{k}" for k in range(1, reported_depth + 1)]
    ].to_numpy(dtype=float)
    sizes = book[
        [f"{side}Size{k}" for k in range(1, reported_depth + 1)]
    ].to_numpy(dtype=float)
    return np.where(prices == padding, np.nan, prices) / price_unit, sizes


def _covers(
    n: GridDepth, side: _SideShape, reported_depth: ReportedDepth, truncated: bool
) -> np.ndarray:
    """Per side; the caller conjoins.  See :func:`_side_covers` for why it is one-way."""
    fully_reported = (
        side.occupied < reported_depth
        if not truncated
        else np.zeros_like(side.occupied, dtype=bool)
    )
    return (side.occupied == 0) | (n <= side.grid_span) | fully_reported


def _gap_positions(name: str, gaps: _SideGaps, rows: int) -> dict:
    """Where the nearest and the largest gap open, in ticks from the touch.

    ``argmax`` returns the *first* of equal elements and the columns run outward from the
    touch, so the largest gap's tie-break -- the nearest of those that tie -- needs no
    expression of its own.  A side with no gap has no position to name and answers NaN; its
    gap has no length and answers zero, as ``LargestGap`` does.
    """
    if gaps.sizes.shape[1] == 0:
        return {
            f"{name}FirstGapDistance": np.full(rows, np.nan),
            f"{name}FirstGapSize": np.zeros(rows),
            f"{name}LargestGapDistance": np.full(rows, np.nan),
        }
    somewhere = (gaps.sizes > 0).any(1)
    index = np.arange(rows)
    first = np.argmax(gaps.sizes > 0, axis=1)
    biggest = np.argmax(gaps.sizes, axis=1)
    return {
        f"{name}FirstGapDistance": np.where(somewhere, gaps.starts[index, first], np.nan),
        f"{name}FirstGapSize": np.where(somewhere, gaps.sizes[index, first], 0.0),
        f"{name}LargestGapDistance": np.where(
            somewhere, gaps.starts[index, biggest], np.nan
        ),
    }


def statistics_from_book(
    book: pd.DataFrame,
    clock: np.ndarray,
    reported_depth: ReportedDepth,
    price_unit: PriceUnit,
    truncated: bool,
    spec: SessionStatistics,
) -> pd.DataFrame:
    """Every statistic the frame determines, on the frame's own index, unvalidated.

    Two things make this harder than it looks, and both return a plausible number when got
    wrong.  Levels are selected **by price**, never by column position: on a book with holes
    the k-th column is not the k-th grid level, so a column slice computes a different
    statistic under the same name.  And the sums are masked explicitly rather than left to
    ``sum``, whose default skips NaN and so treats a missing level as absent instead of
    unknown.

    ``clock`` is passed rather than taken from the index because the two are not the same
    thing on every session: a frame of file rows is indexed by position and carries its
    clock in the message file beside it.
    """
    ask_prices, ask_sizes = _side(book, "Ask", reported_depth, price_unit)
    bid_prices, bid_sizes = _side(book, "Bid", reported_depth, price_unit)
    best_ask, best_bid = ask_prices[:, 0], bid_prices[:, 0]

    ask_here, bid_here = ~np.isnan(ask_prices), ~np.isnan(bid_prices)
    ask_top, bid_top = ask_sizes[:, 0], bid_sizes[:, 0]
    touch = ask_top + bid_top

    columns = {
        "Spread": best_ask - best_bid,
        "MidPrice": (best_ask + best_bid) / 2,
        # A zero touch means both tops are padded, so both best prices are NaN and the
        # numerator is NaN already: this division is the one that needs no guard.
        "MicroPrice": np.where(
            touch > 0, (best_ask * bid_top + best_bid * ask_top) / touch, np.nan
        ),
    }

    # Filled rather than nan-aggregated: an entirely padded side is all-NaN, which nanmax
    # warns about and answers NaN to.  Its span is 0.
    ask_count, bid_count = ask_here.sum(1), bid_here.sum(1)
    deepest_ask = np.where(ask_here, ask_prices, -np.inf).max(1)
    deepest_bid = np.where(bid_here, bid_prices, np.inf).min(1)
    ask = _SideShape(ask_count, np.where(ask_count > 0, deepest_ask - best_ask + 1, 0))
    bid = _SideShape(bid_count, np.where(bid_count > 0, best_bid - deepest_bid + 1, 0))

    for n in spec.imbalance_levels:
        in_ask = ask_here & (ask_prices <= best_ask[:, None] + (n - 1))
        in_bid = bid_here & (bid_prices >= best_bid[:, None] - (n - 1))
        ask_total = np.where(in_ask, ask_sizes, 0.0).sum(1)
        bid_total = np.where(in_bid, bid_sizes, 0.0).sum(1)
        total = ask_total + bid_total
        covered = _covers(n, ask, reported_depth, truncated) & _covers(
            n, bid, reported_depth, truncated
        )
        imbalance = _quotient(bid_total - ask_total, total)
        columns[f"QueueImbalance{n}"] = np.where(covered, imbalance, np.nan)
        columns[f"QueueImbalance{n}Covered"] = covered.astype(float)

    mid = columns["MidPrice"]
    for size in spec.sweep_sizes:
        for label, prices, sizes, count, direction in (
            ("Buy", ask_prices, ask_sizes, ask_count, BUY),
            ("Sell", bid_prices, bid_sizes, bid_count, SELL),
        ):
            cost, filled = _frame_sweep_cost(prices, sizes, mid, size, direction)
            # Determined when it filled, or when the side genuinely ran out on a book we
            # hold -- and never without a mid to price it against.
            covered = np.isfinite(mid) & (
                filled | ((count < reported_depth) & (not truncated))
            )
            columns[f"SweepCost{label}{size}"] = cost
            columns[f"SweepCost{label}{size}Covered"] = covered.astype(float)

    columns["OrderFlowContribution"] = _frame_order_flow(
        best_bid, bid_sizes[:, 0], best_ask, ask_sizes[:, 0]
    )
    columns["TouchDepth"] = np.where(
        np.isfinite(best_bid) & np.isfinite(best_ask), bid_top + ask_top, np.nan
    )

    columns["BidOccupiedLevels"] = bid_count.astype(float)
    columns["AskOccupiedLevels"] = ask_count.astype(float)
    rows = len(book)
    # Bid prices descend with the level and ask prices climb, so each side's gap lengths and
    # the distances they open at carry that sign of their own.
    for label, spans, starts in (
        ("Bid", -np.diff(bid_prices, axis=1) - 1, best_bid[:, None] - bid_prices[:, :-1] + 1),
        ("Ask", np.diff(ask_prices, axis=1) - 1, ask_prices[:, :-1] - best_ask[:, None] + 1),
    ):
        gaps = _SideGaps(np.where(np.isnan(spans), 0.0, np.maximum(spans, 0.0)), starts)
        columns[f"{label}GapCount"] = (gaps.sizes > 0).sum(1).astype(float)
        columns[f"{label}LargestGap"] = gaps.sizes.max(1) if gaps.sizes.size else 0.0
        columns.update(_gap_positions(label, gaps, rows))

    # Validated, not merely reordered: a projection by name list drops a column the dict
    # holds and the list does not, silently, and the two are built in different orders.
    # Strict and ordered, so an extra, a missing and a misplaced column all raise here
    # rather than surfacing as a shape mismatch further down.
    row_schema = spec.row_schema()
    written = row_schema.validate(
        pd.DataFrame(columns, index=book.index, dtype=float)[list(row_schema.columns)]
    )
    return pd.DataFrame(
        _with_rolling(spec, clock, written.to_numpy(dtype=float)), index=book.index
    )


# ---- the session ---------------------------------------------------------------------


@dataclass(eq=False)  # DataFrame fields make a generated __eq__ raise, not compare
class MarketSession:
    """A session: what the book looked like after every message, and what that implies.

    ``reported_depth`` counts occupied levels, the way a LOBSTER file does; the depths and
    sizes inside ``statistics`` count other things, which is why they live in a type of
    their own rather than beside it.

    **The two Nones mean different things.**  ``stats`` is None when the statistics were
    not computed: a deferral, and :meth:`stats_from_frame` computes them from
    ``lobster_book`` whenever they are wanted.  ``trades`` is None when they *cannot* be
    computed, because the record the session was built from determines no volume.  One is
    about what was asked for, the other about what the data can answer.
    """

    reported_depth: ReportedDepth
    statistics: SessionStatistics
    price_unit: PriceUnit
    truncated: bool
    """Whether an unreported level may exist below the ones the frame carries.

    False for a book we folded: a side holding fewer levels than the reported depth is
    exhausted, and the frame says everything there is.  True for a frame read from a file,
    where the same shortfall means only "nothing further in the visible price range", so
    every coverage claim that rests on it weakens to an upper bound.  Named for what it
    asserts rather than for where the frame came from, because four sites test it and only
    the property is what they mean.
    """
    lobster_book: pd.DataFrame
    stats: pd.DataFrame | None
    level_deltas: list[tuple[int, float, LevelDelta]] | None = None

    trades: pd.DataFrame | None = None
    """What traded after every message, and the VWAPs over the windows.

    Held apart from ``stats`` because :meth:`stats_from_frame` reproduces ``stats`` and no
    route reproduces this: a level shrinks by cancellation as well as by execution, so no
    sequence of book configurations determines a volume.  None for a session rebuilt from a
    delta log, which records configurations and nothing else.  A LOBSTER pair carries them,
    the message file recording executions beside the states -- which is the whole of why the
    pair is read together and not the orderbook file alone.
    """

    # ---- axis C: three ways to record the same session --------------------------------

    @classmethod
    def from_occupied_levels(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        reported_depth: ReportedDepth,
        spec: SessionStatistics,
        price_unit: PriceUnit,
        online_statistics: bool,
    ) -> "MarketSession":
        """Ask the book for its top ``reported_depth`` levels after every message.

        With the statistics on, the row and the statistics come from one walk of each
        side; with them off there is nothing to share and the book is asked for the row
        directly.  The two paths are held together by a test.

        The fold does not record.  What it needs of the trades is three integers, which
        :meth:`AggregateBook.submit` accumulates in the loop it already runs; recovering
        them from the fills instead means allocating several objects per message on a path
        that otherwise allocates none, and throwing all of them away.
        """
        times: list[float] = []
        expected = length_hint(messages, 0)
        rows = _book_buffer(reported_depth, expected)
        # None rather than an unused buffer: the statistics-off path must not touch these,
        # and None makes an attempt to do so loud rather than merely wasteful.
        statistics = _statistics_buffer(spec, expected) if online_statistics else None
        trades = _trades_buffer(spec, expected) if online_statistics else None
        touch = None
        for message in messages:
            book.apply(message, record=False)
            times.append(message.time)
            index = rows.claim()
            if not online_statistics:
                book.write_lobster_row(rows.array, index, price_unit, reported_depth)
                continue
            bid = book.side_statistics(BUY, reported_depth)
            ask = book.side_statistics(SELL, reported_depth)
            _write_occupied_levels(rows.array[index], bid, ask, price_unit, reported_depth)
            at = statistics.claim()
            touch = _write_statistics(
                book, statistics.array, at, reported_depth, spec, False, bid, ask, touch,
            )
            # claim() may grow the buffer, which replaces `array`; read it after.
            traded_at = trades.claim()
            _write_trades(book, trades.array, traded_at, message.direction)
        return cls._assemble(
            reported_depth, spec, price_unit, False, times, rows.finished(),
            None if statistics is None else statistics.finished(),
            None if trades is None else trades.finished(), None,
        )

    @classmethod
    def from_top_of_book(
        cls,
        book: AggregateBook,
        messages: Iterable[Message],
        spec: SessionStatistics,
        price_unit: PriceUnit,
        online_statistics: bool,
    ) -> "MarketSession":
        """Read the four touch properties instead, which is a depth-1 session.

        This produces the same session as :meth:`from_occupied_levels` at
        ``reported_depth = 1``.  :meth:`AggregateBook.set_size` removes a level whose
        size reaches zero, so a best price always names an occupied price, and grid
        level 1 therefore coincides with occupied level 1.  A sweep cost read here can
        only ever reach the touch, one level being all there is.
        """
        depth = ReportedDepth(1)
        times: list[float] = []
        expected = length_hint(messages, 0)
        rows = _book_buffer(depth, expected)
        statistics = _statistics_buffer(spec, expected) if online_statistics else None
        trades = _trades_buffer(spec, expected) if online_statistics else None
        touch = None
        for message in messages:
            book.apply(message, record=False)
            times.append(message.time)
            ask, bid = book.best_ask_price, book.best_bid_price
            index = rows.claim()
            rows.array[index] = (
                frames.ASK_PADDING if ask is None else ask * price_unit,
                book.best_ask_size,
                frames.BID_PADDING if bid is None else bid * price_unit,
                book.best_bid_size,
            )
            if online_statistics:
                at = statistics.claim()
                touch = _write_statistics(
                    book, statistics.array, at, depth, spec, False,
                    book.side_statistics(BUY, depth), book.side_statistics(SELL, depth),
                    touch,
                )
                # claim() may grow the buffer, which replaces `array`; read it after.
                traded_at = trades.claim()
                _write_trades(book, trades.array, traded_at, message.direction)
        return cls._assemble(
            depth, spec, price_unit, False, times, rows.finished(),
            None if statistics is None else statistics.finished(),
            None if trades is None else trades.finished(), None,
        )

    @classmethod
    def from_delta_log(
        cls,
        log: DeltaLog,
        book_cls: type[AggregateBook],
        reported_depth: ReportedDepth,
        spec: SessionStatistics,
        price_unit: PriceUnit,
        online_statistics: bool,
    ) -> "MarketSession":
        """Rebuild the session from a sparse recording, with no messages and no matching.

        The log replaces the stream: applying a delta is a write of an absolute size,
        where applying a message is a search plus a match.  What the comparison with the
        dense recorders has to include is the cost of :meth:`DeltaLog.record`, which had
        to run first.

        A delta names the size now resting at a price and says nothing about why it
        changed, so a log determines every statistic that is a function of the
        configurations -- the sweep costs and the order flow among them -- and no volume
        at all.  That is the size-versus-volume distinction of section 3, in the shape of
        the data, and it is why the session comes back with ``trades`` None.
        """
        book = log.opening_book(book_cls, False)
        times = log.times
        # The log knows its own length exactly; no hint is involved.
        rows = _book_buffer(reported_depth, len(times))
        statistics = _statistics_buffer(spec, len(times)) if online_statistics else None
        pending = iter(log.entries)
        upcoming = next(pending, None)
        touch = None
        for sequence in range(len(times)):
            while upcoming is not None and upcoming[0] == sequence:
                _, _, delta = upcoming
                book.set_size(delta.side, delta.price, delta.resting)
                upcoming = next(pending, None)
            index = rows.claim()
            if online_statistics:
                bid = book.side_statistics(BUY, reported_depth)
                ask = book.side_statistics(SELL, reported_depth)
                _write_occupied_levels(rows.array[index], bid, ask, price_unit, reported_depth)
                at = statistics.claim()
                touch = _write_statistics(
                    book, statistics.array, at, reported_depth, spec, False, bid, ask, touch,
                )
            else:
                book.write_lobster_row(rows.array, index, price_unit, reported_depth)
        return cls._assemble(
            reported_depth, spec, price_unit, False, times, rows.finished(),
            None if statistics is None else statistics.finished(), None, log.entries,
        )

    @classmethod
    def _assemble(
        cls,
        reported_depth: ReportedDepth,
        spec: SessionStatistics,
        price_unit: PriceUnit,
        truncated: bool,
        times: Sequence[float] | np.ndarray,
        rows: np.ndarray,
        statistics: np.ndarray | None,
        trades: np.ndarray | None,
        deltas: list[tuple[int, float, LevelDelta]] | None,
    ) -> "MarketSession":
        """Arrays in declared column order to validated frames.

        The arrays are what a recorder produced; whether it folded a book, replayed a log
        or read a file is spent by the time they arrive, and only ``truncated`` survives it.
        """
        clock = np.asarray(times, dtype=float)
        # From the array, not the list: `pd.Index([])` is dtype object, and an empty
        # session would then fail the index schema rather than validate as empty.
        index = pd.Index(clock, name="TimeStamp")
        book_frame = pd.DataFrame(
            rows, columns=frames.lobster_book_columns(reported_depth), index=index
        )
        stats = None if statistics is None else pd.DataFrame(
            _with_rolling(spec, clock, statistics),
            index=index,
        )
        traded = None if trades is None else pd.DataFrame(
            _with_vwap(spec, clock, trades), index=index
        )
        return cls(
            reported_depth=reported_depth,
            statistics=spec,
            price_unit=price_unit,
            truncated=truncated,
            lobster_book=frames.session_book_schema(reported_depth).validate(book_frame),
            stats=None if stats is None else spec.statistics_schema().validate(stats),
            level_deltas=deltas,
            trades=None if traded is None else spec.trades_schema().validate(traded),
        )

    # ---- the statistics, computed from the finished frame -----------------------------

    def stats_from_frame(self) -> pd.DataFrame:
        """Recompute every statistic from ``lobster_book``, touching no book.

        The reconciliation this session's online route is checked against: one quantity
        computed twice, once from a live book and once from the finished frame.
        """
        return self.statistics.statistics_schema().validate(
            statistics_from_book(
                self.lobster_book,
                self.lobster_book.index.to_numpy(dtype=float),
                self.reported_depth,
                self.price_unit,
                self.truncated,
                self.statistics,
            )
        )

    def vwap(self, window: int) -> pd.Series:
        """VWAP over ``(t - window, t]``, for a window the specification did not name.

        Stands to the ``VWAP{w}`` columns as :meth:`column_sliced_imbalance` stands to the
        ``QueueImbalance{n}`` ones: the columns are what a session records, this is how to
        ask it something else.

        Raises where ``trades`` is None, which is the honest answer rather than a NaN
        column: a delta log records configurations, and no sequence of configurations
        determines a volume.  An orderbook file alone is in the same position; its message
        file is what supplies the executions, and that is why the two are read as a pair.

        Covers the executions the fold saw, or the visible ones the file reported.  The
        tape's VWAP also carries hidden and auction prints, which rest at or inside the
        touch and so print better than these.
        """
        if self.trades is None:
            raise ValueError(
                "this session has no trades: it was built from book configurations, and a "
                "level shrinks by cancellation as well as by execution, so the volume "
                "traded is not recoverable from them"
            )
        window = _whole("window", window)
        clock = self.lobster_book.index.to_numpy(dtype=float)
        start = window_start(clock, window)
        traded = rolling_sum(start, self.trades["Volume"].to_numpy(dtype=float))
        value = rolling_sum(start, self.trades["TradedValue"].to_numpy(dtype=float))
        return pd.Series(
            _quotient(value, traded),
            index=self.lobster_book.index,
            name=f"VWAP{window}",
        )

    def order_flow_imbalance(self, window: Window) -> pd.Series:
        """``OFI`` over ``(t - window, t]``, for a window the specification did not name.

        Stands to the ``OrderFlowImbalance{w}`` columns as :meth:`vwap` stands to the
        ``VWAP{w}`` ones, and differs from them in one way only: ``window`` is seconds
        and need not be whole.  The declared columns cannot admit that, a window being
        part of their name there; a study that sweeps ``w`` over a decade needs it.

        The NaN rule is the columns' rule, and it is the one that matters.  ``e_n`` is
        undefined on the first row of a session and wherever a side is empty -- and on
        the row *after* one, ``_order_flow_contribution`` reading both states -- so a
        window containing any such row has no sum, rather than a sum over the rest.
        Counting the undefined rows and masking is not the same as summing with NaNs:
        a NaN inside a cumulative sum poisons every window after it.
        """
        window = _span("window", window)
        clock = self.lobster_book.index.to_numpy(dtype=float)
        flow = self.stats["OrderFlowContribution"].to_numpy(dtype=float)
        start = window_start(clock, window)
        missing = rolling_sum(start, np.isnan(flow).astype(float))
        return pd.Series(
            np.where(missing > 0, np.nan, rolling_sum(start, np.nan_to_num(flow))),
            index=self.lobster_book.index,
            name=f"OrderFlowImbalance{window:g}",
        )

    def column_sliced_imbalance(self, n: GridDepth) -> pd.Series:
        """The imbalance computed from the first ``n`` size *columns* of the frame.

        This is not ``I^n``.  Section 4 sums size over the first ``n`` positions on the
        price grid; summing the first ``n`` columns sums the first ``n`` prices that carry
        size, and the two windows coincide only where the reported levels are
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
