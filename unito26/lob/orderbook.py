"""The aggregate book, and the ladder of faster ways to find its best price.

The state is ``{price: size}`` on each side, in tick counts.  ``prop.lobUpdate`` is
stated entirely on that state, which is the whole content of holding it: the aggregate
book is closed under the arrival of an order, so the queue inside a level never has to
be represented.  What it cannot do is answer a question about a *named* order -- how
much size is ahead of mine, whose fill was that -- and that is the order-level book,
which lives elsewhere.

Every class here is a **mutable fold accumulator**: one state, the current one, with no
history and no time index.  The time series is the business of :mod:`unito26.lob.session`.

The faster variants change *only* how the best price is found; the matching logic is
written once, in :class:`AggregateBook`, and inherited unchanged.  That isolation is
what makes the benchmark measure one thing.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from itertools import accumulate
from dataclasses import dataclass, field

import numpy as np

from unito26.lob.binary_gaps import count_binary_gaps, measure_largest_binary_gap
from unito26.lob.frames import ASK_PADDING, BID_PADDING
from unito26.lob.messages import (
    BUY,
    SELL,
    Fill,
    GridDepth,
    LevelDelta,
    Message,
    MessageType,
    ReportedDepth,
    SweepSize,
    is_market_price,
)

__all__ = [
    "grid_prices",
    "SubmitResult",
    "SideStatistics",
    "AggregateBook",
    "CachedBestBook",
    "HeapBook",
    "BitmapBook",
    "TickArrayBook",
    "AXIS_B_VARIANTS",
]


def _span_bits(bits: int, origin: int, levels: list[tuple[int, int]]) -> int:
    """Occupancy between the best and deepest of ``levels``, shifted to start at bit 0.

    Bit 0 is always set, so the result is odd and needs no normalising before
    :func:`measure_largest_binary_gap`.  Gap length and gap count are invariant under
    reversal of the bit string, which is what lets the bid side -- read downward from the
    top bit -- share this with the ask side.
    """
    if len(levels) < 2:
        return 0
    low = min(levels[0][0], levels[-1][0]) - origin
    high = max(levels[0][0], levels[-1][0]) - origin
    return (bits & (((1 << (high - low + 1)) - 1) << low)) >> low


def grid_prices(prices: Iterable[int]) -> list[int]:
    """Those of ``prices`` that name a position on the grid.

    A market order carries a price specification guaranteeing execution rather than a
    position: ``MARKET_SELL_PRICE`` is 0 and ``MARKET_BUY_PRICE`` is ``sys.maxsize``, so
    a band sized from a raw message stream would run from one to the other.  The two fail
    differently -- the buy sentinel is the maximum and raises, the sell sentinel is the
    minimum and silently widens the band -- so a filter written for one lets the other
    through, and both are dropped here rather than at each call site.
    """
    return [price for price in prices if not is_market_price(price)]


def _runs(positions: list[int]) -> list[tuple[int, int]]:
    """Maximal runs of consecutive integers, as ``(first value, length)``, in order.

    Every gap statistic is a reading of this list, so there is one place where "maximal
    run" is defined and the five of them cannot drift apart.
    """
    runs: list[tuple[int, int]] = []
    for index, value in enumerate(positions):
        if index and value == positions[index - 1] + 1:
            start, length = runs[-1]
            runs[-1] = (start, length + 1)
        else:
            runs.append((value, 1))
    return runs


def _sweep_cost(
    levels: list[tuple[int, int]],
    mid: float | None,
    sizes: tuple[SweepSize, ...],
    direction: int,
) -> list[float | None]:
    """Per-share cost, in ticks, of market orders of each size in ``sizes``.

    ``levels`` is the side being *consumed*, best first, and ``direction`` is the direction
    of the market order -- so a buy is handed the asks.  Passing the wrong side is the
    mistake this signature exists to make visible: without ``direction`` the cost would be
    written ``abs(value / size - mid)``, which on the worked example returns 1 tick for a buy
    of 100 costed against the bids and 1 tick for the correct buy of 120.  The two are
    indistinguishable, and on a crossed book the absolute value also reports a gain as a cost.

    ``sizes`` must be ascending.  The walk accumulates once and answers every size on the way
    past, the cumulative fills nesting as the imbalance windows do in
    :meth:`AggregateBook.queue_imbalance_profile`, so a further size costs an accumulation
    rather than another walk.  Which of the two dominates depends on how many sizes are
    asked for; ``notebooks/the-cost-of-the-statistics.ipynb`` measures it.

    None where the levels do not hold the size, and None where ``mid`` is undefined -- the
    sweep itself is perfectly well defined on a one-sided book, it is the *benchmark* that is
    missing.  The two cases are different: the first says the order cannot be filled at any
    price, the second that there is nothing to price it against.
    """
    costs: list[float | None] = []
    filled = value = 0
    level = consumed = 0
    for size in sizes:
        if size < 1:
            raise ValueError(f"a sweep is for a positive number of shares, got {size}")
        while filled < size and level < len(levels):
            price, resting = levels[level]
            taken = min(size - filled, resting - consumed)
            filled += taken
            value += taken * price
            consumed += taken
            if consumed == resting:
                level += 1
                consumed = 0
        if filled < size or mid is None:
            costs.append(None)
            continue
        cost = direction * (value / size - mid)
        # Licensed by the book not crossing, which is a consequence of the matching rule.
        # A crossed book would make a sweep profitable, and the assertion says so rather
        # than letting a negative cost travel into a column named for a cost.  It can only
        # mean that now, the size having been screened above.
        assert cost >= 0, f"negative sweep cost {cost}: the book is crossed"
        costs.append(cost)
    return costs


@dataclass(frozen=True, slots=True)
class SubmitResult:
    """What one submission did: the trades it printed and the levels it moved."""

    fills: list[Fill] = field(default_factory=list)
    deltas: list[LevelDelta] = field(default_factory=list)
    unfilled: int = 0
    """Shares that neither executed nor rested, and so left the book entirely.

    Non-zero only for a market order that found nothing to trade against: having named
    no price of its own, and no price to inherit, its remainder is unfillable interest
    returned to the sender rather than an order.  Named rather than dropped, so that
    shares leaving the book are accounted for.
    """

    @property
    def market_order_size(self) -> int:
        """``q_M``: the executed part of the incoming order.

        By section 6 this is exactly the market-order component of the decomposition,
        and a trade is a market order with ``q_M > 0``.
        """
        return sum(fill.size for fill in self.fills)

    @property
    def walked_the_book(self) -> bool:
        """True when the order consumed more than one price level."""
        return len({fill.price for fill in self.fills}) > 1


@dataclass(frozen=True, slots=True)
class SideStatistics:
    """What a session records about one side, read in a single pass over it.

    The individual methods below each walk the side again; a fold that records every
    statistic after every message pays that walk once per statistic.  This type is the
    batched form, and :meth:`AggregateBook.side_statistics` is where the walk is spent
    once instead.

    The two distances are None when the side has no gap: there is no position to name,
    and zero would name the touch, which is always occupied.  None rather than NaN, for
    the reason :meth:`AggregateBook.best_price` returns None -- undefined is not a float
    -- and because NaN would make two equal readings compare unequal.  The frame turns
    it into NaN at the boundary, where a column has to hold something.
    """

    levels: list[tuple[int, int]]
    """``(price, size)``, best first, at most ``reported_depth`` of them."""

    occupied: int
    grid_span: int
    gap_count: int
    largest_gap: int
    first_gap_distance: int | None
    first_gap_size: int
    largest_gap_distance: int | None


class AggregateBook:
    """The ``{price: size}`` book: rungs L0 to L3 of the ladder.

    Prices are integer tick counts.  The two sides are plain dicts, and the best
    prices are found by scanning their keys: the baseline, O(number of occupied levels)
    per lookup.  Every faster variant in this module keeps this class's matching logic
    and overrides only the best-price lookup, so the ladder measures one thing -- the
    cost of finding the best price.

    Parameters
    ----------
    strict
        When True, a withdrawal for more than is resting raises.  When False
        (the default) it removes what is there and carries on, which is what replaying
        a real feed needs, since a feed's early messages often reference orders posted
        before the file began.
    """

    def __init__(self, strict: bool = False):
        self.bids: dict[int, int] = {}
        self.asks: dict[int, int] = {}
        self.strict = strict
        self.last_fill_count = 0
        self.last_traded_size = 0
        self.last_traded_value = 0

    # ---- storage: the four operations every book must provide ---------------------
    #
    # Matching, the derived quantities and the housekeeping below are written against
    # these and nothing else, so a book that keeps its sizes somewhere other than two
    # dicts inherits all of it.  Here they are the obvious thing: the dicts are the
    # storage, and `levels_map` hands one back rather than building it.

    def levels_map(self, direction: int) -> dict[int, int]:
        """Every occupied level on a side, as ``{price: size}``.

        Read-only from the caller's point of view.  The baseline's storage *is* this
        map, so it is returned; a book that stores sizes elsewhere builds one here,
        and writing to what it returns would change nothing.
        """
        return self.bids if direction == BUY else self.asks

    def size_at(self, direction: int, price: int) -> int:
        """Resting size at an absolute price.  Zero where no level rests."""
        return self.levels_map(direction).get(price, 0)

    def set_size(self, direction: int, price: int, size: int) -> None:
        """Set the resting size at a price.

        Zero **removes** the level: a price whose queue empties is gone from the book,
        not a level holding nothing.  Every write goes through here, so that invariant
        is stated once, and so a variant keeping an index of occupied prices can
        maintain it by overriding this one method rather than the matching loop.
        """
        levels = self.levels_map(direction)
        if size > 0:
            levels[price] = size
        else:
            levels.pop(price, None)

    # ---- section 3: the configuration -------------------------------------------

    def best_price(self, direction: int) -> int | None:
        """Best price on the given side: highest bid, or lowest ask.

        This is the one method the performance ladder replaces.  Here it is a full scan
        of the dict keys: O(number of occupied levels), and correct on inspection.  Every
        faster variant overrides this method and inherits the matching logic unchanged,
        so the ladder concerns finding the best price and not matching.
        """
        levels = self.levels_map(direction)
        if not levels:
            return None
        return max(levels) if direction == BUY else min(levels)

    @property
    def best_bid_price(self) -> int | None:
        """``P^b``, the highest price with buy offers.  None when the side is empty."""
        return self.best_price(BUY)

    @property
    def best_ask_price(self) -> int | None:
        """``P^a``, the lowest price with sell offers.  None when the side is empty."""
        return self.best_price(SELL)

    def bid_price(self, level: int) -> int | None:
        """``P^{b,i} = P^b - (i-1) tau``, in ticks.  Levels are 1-indexed.

        This is a position on the price *grid*, so it is defined whether or not any
        size rests there -- section 3 is explicit that intermediate levels may be
        empty, and case B of the worked example has two of them.
        """
        best = self.best_bid_price
        return None if best is None else best - (level - 1)

    def ask_price(self, level: int) -> int | None:
        """``P^{a,i} = P^a + (i-1) tau``, in ticks.  Levels are 1-indexed."""
        best = self.best_ask_price
        return None if best is None else best + (level - 1)

    def bid_size_at(self, price: int) -> int:
        """``S^b_t(p)``: resting buy size at an absolute price."""
        return self.size_at(BUY, price)

    def ask_size_at(self, price: int) -> int:
        """``S^a_t(p)``: resting sell size at an absolute price."""
        return self.size_at(SELL, price)

    def bid_size(self, level: int) -> int:
        """``S^{b,i}``, size at the ``i``-th bid level.  Zero for ``i <= 0``."""
        price = self.bid_price(level)
        return 0 if price is None or level <= 0 else self.size_at(BUY, price)

    def ask_size(self, level: int) -> int:
        """``S^{a,i}``, size at the ``i``-th ask level.  Zero for ``i <= 0``."""
        price = self.ask_price(level)
        return 0 if price is None or level <= 0 else self.size_at(SELL, price)

    @property
    def best_bid_size(self) -> int:
        """``S^b``, size at the best bid."""
        return self.bid_size(1)

    @property
    def best_ask_size(self) -> int:
        """``S^a``, size at the best ask."""
        return self.ask_size(1)

    def levels(self, direction: int, depth: int) -> list[tuple[int, int]]:
        """The first ``depth`` grid positions on a side, as ``(price, size)``.

        Includes empty positions, so the result always has length ``depth`` when the
        side is non-empty.  That is what makes it comparable with a feed's fixed-width
        snapshot.
        """
        price_of = self.bid_price if direction == BUY else self.ask_price
        size_of = self.bid_size if direction == BUY else self.ask_size
        if self.best_price(direction) is None:
            return []
        return [(price_of(i), size_of(i)) for i in range(1, depth + 1)]

    # ---- section 4: derived quantities -------------------------------------------

    @property
    def spread(self) -> int | None:
        """``phi = P^a - P^b`` in ticks.  None when either side is empty."""
        bid, ask = self.best_bid_price, self.best_ask_price
        return None if bid is None or ask is None else ask - bid

    @property
    def mid_price(self) -> float | None:
        """``P^m = (P^a + P^b)/2`` in ticks.  None when either side is empty."""
        bid, ask = self.best_bid_price, self.best_ask_price
        return None if bid is None or ask is None else (ask + bid) / 2

    def queue_imbalance(self, n: GridDepth) -> float:
        """``I^n``: bid minus ask over the total, over the first ``n`` **grid** levels.

        ``n`` counts positions on the price grid, not occupied levels, so ``I^n`` is the
        size resting within ``n - 1`` ticks of each touch.  On a book with holes that is
        not the same as the size in the first ``n`` queues; see
        ``documentation/grid-levels-and-lobster-levels.md``.

        Lies in ``[-1, +1]`` and is **positive when the book is bid-heavy**.  Inverting this
        sign silently inverts every signal built on it, which is why it is stated here
        rather than left to the reader.  For ``n >= 1`` with both sides non-empty the value
        is *strictly* interior, because ``set_size`` removes a level whose queue empties
        and so ``S^{b,1}`` and ``S^{a,1}`` are both positive; it is ``+-1`` exactly when one
        side is empty, and NaN when both are.
        """
        if n <= 0:
            raise ValueError(f"n counts grid levels from the touch and must be >= 1, got {n}")
        bid_total = sum(self.bid_size(i) for i in range(1, n + 1))
        ask_total = sum(self.ask_size(i) for i in range(1, n + 1))
        total = bid_total + ask_total
        if total == 0:
            return float("nan")
        return (bid_total - ask_total) / total

    def queue_imbalance_profile(
        self, imbalance_levels: tuple[GridDepth, ...]
    ) -> list[float]:
        """``I^n`` for every ``n`` in ``imbalance_levels``, from one walk of each side.

        The windows nest -- the first ``n`` grid positions contain the first ``n - 1`` --
        so the deepest walk carries every shallower answer in its running total.  A fold
        recording a profile after every message therefore walks each side once instead of
        once per level, and finds each best price once instead of twice per level.

        :meth:`queue_imbalance` is where the quantity is *defined*, sign convention and
        all; this is the same numbers read in bulk, and a test holds the two together.
        """
        deepest = max(imbalance_levels)
        if deepest <= 0:
            raise ValueError(
                f"n counts grid levels from the touch and must be >= 1, got {deepest}"
            )
        running: dict[int, list[int]] = {}
        for direction in (BUY, SELL):
            best = self.best_price(direction)
            total = 0
            totals: list[int] = []
            for step in range(deepest):
                # best - step * d walks down the bids and up the asks, which is the same
                # expression the rest of the module uses to be generic in the side.
                if best is not None:
                    total += self.size_at(direction, best - step * direction)
                totals.append(total)
            running[direction] = totals
        profile = []
        for n in imbalance_levels:
            bid_total, ask_total = running[BUY][n - 1], running[SELL][n - 1]
            total = bid_total + ask_total
            profile.append(
                float("nan") if total == 0 else (bid_total - ask_total) / total
            )
        return profile

    @property
    def micro_price(self) -> float | None:
        """``P^mu``, the imbalance-weighted mid.  None when either side is empty.

        Written as ``P^m + (phi/2) I^1``, which is exactly the crossed-weighted average
        ``(P^a S^b + P^b S^a) / (S^a + S^b)`` -- the ask price carries the *bid* size.
        So it sits toward the **thin** side: a bid-heavy book pushes it up toward the ask.
        """
        spread, mid = self.spread, self.mid_price
        if spread is None or mid is None:
            return None
        return mid + spread * self.queue_imbalance(GridDepth(1)) / 2

    def sweep_cost(
        self, direction: int, size: SweepSize, reported_depth: ReportedDepth
    ) -> float | None:
        """``sc(Q, d)``: per-share cost, in ticks, of a market order for ``size`` shares.

        ``direction`` is the direction of the *market order*, so ``BUY`` walks the asks.
        Measured against the mid, which is what makes it ``phi/2`` exactly while the order
        does not walk and what ties it to the half-spread term of section 7 -- that term
        assumes no walking, and this is the same quantity without the assumption.  Beyond
        the touch each share additionally pays its own distance from it, a distance on the
        price *grid*: one tick per level only where the consumed side is occupied at every
        tick.

        Restricted to ``reported_depth`` occupied levels, as the gap statistics are, so that
        a book and the frame it produces answer the same question.  None where those levels
        do not hold ``size``, and None where the mid is undefined.

        This reads **visible** depth, so it overstates what an order would really pay:
        hidden liquidity rests at or inside the touch and fills better than the ladder says.
        """
        return _sweep_cost(
            self.occupied_levels(-direction, reported_depth),
            self.mid_price,
            (size,),
            direction,
        )[0]

    # ---- occupied levels: the other indexing ---------------------------------------
    #
    # `levels` above walks the price grid.  These walk the prices that actually carry
    # size, which is what a LOBSTER file reports and what the gap statistics measure.
    # Written against `best_price` and `size_at` so every variant's index applies;
    # reaching for `levels_map` would bypass the cache and the heap, and would make
    # TickArrayBook build a whole dict per call.

    def occupied_levels(
        self, direction: int, reported_depth: ReportedDepth
    ) -> list[tuple[int, int]]:
        """The first ``reported_depth`` prices carrying size, best first."""
        if reported_depth <= 0:
            raise ValueError(f"reported_depth must be >= 1, got {reported_depth}")
        best = self.best_price(direction)
        if best is None:
            return []
        if reported_depth == 1:
            return [(best, self.size_at(direction, best))]
        levels = self.levels_map(direction)
        pick = heapq.nlargest if direction == BUY else heapq.nsmallest
        return [(price, levels[price]) for price in pick(reported_depth, levels)]

    def occupied_level_count(self, direction: int, reported_depth: ReportedDepth) -> int:
        """How many of the first ``reported_depth`` levels exist at all."""
        return len(self.occupied_levels(direction, reported_depth))

    def grid_span(self, direction: int, reported_depth: ReportedDepth) -> int:
        """Grid positions spanned by those levels, inclusive of both ends.

        The bridge between the two indexings, and the reason a frame of a given reported
        depth can answer some ``I^n`` and not others: everything in the grid window is
        known when ``n <= grid_span``.
        """
        levels = self.occupied_levels(direction, reported_depth)
        if not levels:
            return 0
        return abs(levels[-1][0] - levels[0][0]) + 1

    def empty_grid_positions(
        self, direction: int, reported_depth: ReportedDepth
    ) -> list[int]:
        """Grid indices, 1-based from the touch, that hold nothing but lie between levels
        that do."""
        levels = self.occupied_levels(direction, reported_depth)
        if len(levels) < 2:
            return []
        best = levels[0][0]
        filled = {abs(price - best) + 1 for price, _ in levels}
        return [i for i in range(1, self.grid_span(direction, reported_depth) + 1)
                if i not in filled]

    def gap_count(self, direction: int, reported_depth: ReportedDepth) -> int:
        """Number of maximal runs of empty positions.  Not the length of
        :meth:`empty_grid_positions`, which counts positions rather than runs."""
        return len(_runs(self.empty_grid_positions(direction, reported_depth)))

    def largest_gap_size_between_non_empty_levels(
        self, direction: int, reported_depth: ReportedDepth
    ) -> int:
        """Length of the longest such run.  Zero when the levels are contiguous."""
        runs = _runs(self.empty_grid_positions(direction, reported_depth))
        return max((length for _, length in runs), default=0)

    def first_gap_distance(
        self, direction: int, reported_depth: ReportedDepth
    ) -> int | None:
        """Ticks from the touch to the shallowest empty position of the nearest gap.

        Grid position ``i`` lies ``i - 1`` ticks from the touch, so a gap opening at
        position 2 is one tick away.  None when the side has no gap.
        """
        runs = _runs(self.empty_grid_positions(direction, reported_depth))
        return runs[0][0] - 1 if runs else None

    def first_gap_size(self, direction: int, reported_depth: ReportedDepth) -> int:
        """Levels in the gap nearest the touch.  Zero when there is no gap."""
        runs = _runs(self.empty_grid_positions(direction, reported_depth))
        return runs[0][1] if runs else 0

    def largest_gap_distance(
        self, direction: int, reported_depth: ReportedDepth
    ) -> int | None:
        """Ticks from the touch to the largest gap, the nearest of them if two tie.

        ``max`` returns the first of equal elements and the runs come off the touch in
        order, so the tie-break costs nothing to state and nothing to compute.
        """
        runs = _runs(self.empty_grid_positions(direction, reported_depth))
        if not runs:
            return None
        return max(runs, key=lambda run: run[1])[0] - 1

    def side_statistics(
        self, direction: int, reported_depth: ReportedDepth
    ) -> SideStatistics:
        """Every statistic above, from one walk of the side.

        Each of them agrees with its own method; a test asserts that on every rung.

        The gaps are read off the *differences between consecutive occupied prices*
        rather than off the occupancy bitmap.  Two prices `reported_depth` apart bound
        exactly one maximal run of empty positions, so the whole gap structure is a
        by-product of the walk that produced ``levels`` -- and no rung has to enumerate
        the positions, mask an integer or count bits to get at it.
        """
        levels = self.occupied_levels(direction, reported_depth)
        if not levels:
            return SideStatistics([], 0, 0, 0, 0, None, 0, None)
        best = levels[0][0]
        count = largest = largest_at = first_at = first_size = 0
        previous = best
        for price, _ in levels[1:]:
            hole = abs(price - previous) - 1
            if hole:
                start = abs(previous - best) + 1
                count += 1
                if count == 1:
                    first_at, first_size = start, hole
                if hole > largest:
                    largest, largest_at = hole, start
            previous = price
        return SideStatistics(
            levels=levels,
            occupied=len(levels),
            grid_span=abs(levels[-1][0] - best) + 1,
            gap_count=count,
            largest_gap=largest,
            first_gap_distance=first_at if count else None,
            first_gap_size=first_size,
            largest_gap_distance=largest_at if count else None,
        )

    # ---- the LOBSTER row: the book as one line of a file ---------------------------

    def to_lobster_row(self, price_unit: int, reported_depth: ReportedDepth) -> list[int]:
        """The top ``reported_depth`` **occupied** levels, in file units.

        ``price_unit`` is the number of LOBSTER price units in one tick -- 100 for a
        penny, since LOBSTER quotes dollars times 10000.  It is an integer, unlike
        :class:`~unito26.lob.messages.TickGrid`'s currency ``tick_size``.
        """
        asks = self.occupied_levels(SELL, reported_depth)
        bids = self.occupied_levels(BUY, reported_depth)
        row: list[int] = []
        for level in range(reported_depth):
            ask = asks[level] if level < len(asks) else (None, 0)
            bid = bids[level] if level < len(bids) else (None, 0)
            row += [
                ASK_PADDING if ask[0] is None else ask[0] * price_unit, ask[1],
                BID_PADDING if bid[0] is None else bid[0] * price_unit, bid[1],
            ]
        return row

    def write_lobster_row(
        self, out: np.ndarray, row: int, price_unit: int, reported_depth: ReportedDepth
    ) -> None:
        """The same row, written in place into row ``row`` of a preallocated array.

        The fold records thousands of these, so the row is written where it will live
        rather than built as a list and copied.
        """
        out[row] = self.to_lobster_row(price_unit, reported_depth)

    @classmethod
    def from_lobster_row(
        cls, row, price_unit: int, reported_depth: ReportedDepth
    ) -> "AggregateBook":
        """Inverse of :meth:`to_lobster_row`, for any rung of the ladder.

        A padded level carries a sentinel price and a size of zero, and is skipped: a
        level of zero size does not exist, and :meth:`set_size` would remove it again.
        """
        levels: dict[int, dict[int, int]] = {BUY: {}, SELL: {}}
        for level in range(1, reported_depth + 1):
            for direction, side, padding in (
                (SELL, "Ask", ASK_PADDING), (BUY, "Bid", BID_PADDING)
            ):
                price = int(row[f"{side}Price{level}"])
                size = int(row[f"{side}Size{level}"])
                if price == padding or size == 0:
                    continue
                if price % price_unit:
                    raise ValueError(f"price {price} is not a multiple of {price_unit}")
                levels[direction][price // price_unit] = size
        return cls.from_levels(levels[BUY], levels[SELL])

    # ---- sections 2 and 6: the update ---------------------------------------------

    def apply(self, message: Message, record: bool) -> SubmitResult | None:
        """Apply any message.  The stream driver's single entry point.

        ``record`` governs whether the trades and level changes are collected and
        returned.  A fold that only wants the book's evolution passes False and gets
        ``None`` back, which costs no allocation and turns a later read of ``.fills``
        into an ``AttributeError`` rather than an empty list.  It has no default,
        because it decides what this method returns.

        The three ``last_*`` counters are written by whichever of the two runs, so a read of
        them after any message -- through here or by calling :meth:`submit` and
        :meth:`withdraw` directly, as the tests do -- describes that message and no earlier
        one.
        """
        if message.kind is MessageType.SUBMIT:
            return self.submit(message, record)
        return self.withdraw(message, record)

    def submit(self, message: Message, record: bool) -> SubmitResult | None:
        """Process an incoming order: consume the opposite side, then rest the rest.

        One code path, not two.  By the decomposition of section 6 an incoming order is
        equivalent to a market order of size ``q_M`` followed by a resting order of
        size ``q - q_M``, so there is no separate branch for "marketable" orders --
        the loop simply does not execute when nothing matches.

        See :meth:`apply` for ``record``.  The one thing the market-order part needs from
        the fills is the price of the last of them, which :meth:`resting_price` inherits,
        so that is tracked whether or not the fills themselves are kept.  The three
        ``last_*`` counters are tracked on the same terms, for the same reason: a fold
        computing VWAP needs the volume and the value of what traded, and recovering them
        from the fills would mean recording, which allocates several objects per message
        on a path that otherwise allocates none.  Two integer additions do not.
        """
        remaining = message.size
        direction = message.direction
        limit_price = message.price
        fills: list[Fill] = [] if record else None
        deltas: list[LevelDelta] = [] if record else None
        last_fill_price = None
        fill_count = traded_size = traded_value = 0

        # 1. The market-order part: consume while the price constraint permits.
        while remaining > 0:
            best = self.best_price(-direction)
            # pi*d <= p*d handles both sides in one expression: for a buy this is
            # "the best ask is not above my limit", for a sell "the best bid is not
            # below it".  An empty side stops the loop for the same reason a price
            # that fails the test does -- there is nothing eligible left.
            if best is None or best * direction > limit_price * direction:
                break
            resting = self.size_at(-direction, best)
            traded = min(remaining, resting)
            remaining -= traded
            self.set_size(-direction, best, resting - traded)
            # A fill trades at the RESTING order's price, never the incoming one.
            last_fill_price = best
            fill_count += 1
            traded_size += traded
            traded_value += traded * best
            if record:
                fills.append(Fill(price=best, size=traded, aggressor=direction))
                deltas.append(LevelDelta(side=-direction, price=best, resting=resting - traded))

        self.last_fill_count = fill_count
        self.last_traded_size = traded_size
        self.last_traded_value = traded_value

        # 2. The resting part.
        rest_price = self.resting_price(limit_price, last_fill_price)
        if remaining > 0 and rest_price is not None:
            resting = self.size_at(direction, rest_price) + remaining
            self.set_size(direction, rest_price, resting)
            if record:
                deltas.append(LevelDelta(side=direction, price=rest_price, resting=resting))
            remaining = 0

        if not record:
            return None
        return SubmitResult(fills=fills, deltas=deltas, unfilled=remaining)

    @staticmethod
    def resting_price(limit_price: int, last_fill_price: int | None) -> int | None:
        """Where an unexecuted remainder rests, or None when it cannot rest at all.

        An order that named a price rests at it.  A market order named none -- its
        sentinel is a price specification guaranteeing execution, not a point on the
        grid -- so its remainder rests at the price it last executed against.  This is
        the **market-to-limit** rule, and it is what venues that accept market orders
        do with the part that does not trade.

        A market order that executed nothing has no such price to inherit, and that is
        the one case where a remainder genuinely cannot rest.  It can only arise when
        the opposite side was empty on arrival, so nothing is lost by refusing: there
        was no liquidity to take at any price.

        A residual must never rest at the sentinel itself.  A fill trades at the
        *resting* order\'s price, so a residual sitting at ``MARKET_BUY_PRICE`` would
        print later fills at ``sys.maxsize``, and one at ``MARKET_SELL_PRICE`` -- which
        is 0, and so indistinguishable from a real price -- would give every subsequent
        buyer free shares.
        """
        if not is_market_price(limit_price):
            return limit_price
        return last_fill_price

    def withdraw(self, message: Message, record: bool) -> SubmitResult | None:
        """Remove resting size at ``(price, direction)``, addressed by quantity.

        A quantity-addressed withdrawal is one more signed
        delta on the aggregate state, so the state does not grow.  What changes is that
        level sizes stop being monotone, the best price can now move in both
        directions, and the book can empty entirely.

        See :meth:`apply` for ``record``.  A withdrawal trades nothing, so it zeroes the
        counters rather than leaving the previous submission's totals behind them.
        """
        self.last_fill_count = 0
        self.last_traded_size = 0
        self.last_traded_value = 0
        resting = self.size_at(message.direction, message.price)
        if message.size > resting and self.strict:
            raise ValueError(
                f"cannot withdraw {message.size} at price {message.price}: only "
                f"{resting} resting"
            )
        removed = min(message.size, resting)
        if removed == 0:
            return SubmitResult() if record else None
        left = resting - removed
        self.set_size(message.direction, message.price, left)
        if not record:
            return None
        return SubmitResult(
            deltas=[LevelDelta(side=message.direction, price=message.price, resting=left)]
        )

    # ---- housekeeping ---------------------------------------------------------------

    def copy(self) -> "AggregateBook":
        """An independent copy of the current state.

        Anything recording a series of states needs this: storing the book itself stores
        the same mutable object every time, so every recorded state ends up equal to the
        final one.
        """
        clone = self._empty_like()
        for direction in (BUY, SELL):
            for price, size in self.levels_map(direction).items():
                clone.set_size(direction, price, size)
        return clone

    @classmethod
    def from_levels(
        cls, bids: dict[int, int], asks: dict[int, int], strict: bool = False
    ) -> "AggregateBook":
        """Build a book from ``{price: size}`` maps on each side.

        Goes through :meth:`set_size` for every level, so a variant that keeps an
        index is correctly initialised.  Assigning to ``book.bids`` directly would leave
        that index empty and the book quietly wrong -- precisely the class of bug a
        cache invites.
        """
        book = cls.for_prices(list(bids) + list(asks), strict)
        for direction, levels in ((BUY, bids), (SELL, asks)):
            for price, size in levels.items():
                if size <= 0:
                    raise ValueError(f"level at {price} must hold positive size")
                book.set_size(direction, price, size)
        book.check_invariants()
        return book

    @classmethod
    def for_prices(
        cls, prices: Iterable[int], strict: bool = False
    ) -> "AggregateBook":
        """A book sized for a known range of prices.

        The dict-backed books ignore the range -- they grow as prices arrive, which is
        exactly why they need no band.  A book indexed by tick cannot, and overriding
        this is where that requirement becomes visible instead of being smuggled into
        whoever constructs one.

        ``prices`` may be taken straight off a message stream: every variant sizes itself
        through :func:`grid_prices`, so the market-order sentinels contribute no range.
        A genuine level at ``MARKET_SELL_PRICE`` is therefore not sizeable, which is the
        price of the sentinel being an ordinary integer.
        """
        return cls(strict)

    #: Ticks of headroom left on each side of the observed range by :meth:`for_prices`.
    BAND_MARGIN = 64

    def _empty_like(self) -> "AggregateBook":
        """A new, empty book with the same configuration.  Subclasses with extra
        constructor arguments override this rather than :meth:`copy`."""
        return type(self)(self.strict)

    def check_invariants(self) -> None:
        """Assert what must be true of any book, at any time.

        The book never crossing is a *consequence* of the matching rule, not an extra
        assumption, so a crossed book is a bug rather than a market state.
        """
        bid, ask = self.best_bid_price, self.best_ask_price
        if bid is not None and ask is not None and bid >= ask:
            raise AssertionError(f"crossed book: best bid {bid} >= best ask {ask}")
        for name, direction in (("bid", BUY), ("ask", SELL)):
            for price, size in self.levels_map(direction).items():
                if size <= 0:
                    raise AssertionError(
                        f"{name} level at {price} holds {size}: a price whose queue "
                        "empties must be removed, not kept at zero"
                    )

    def __repr__(self) -> str:
        bid, ask = self.best_bid_price, self.best_ask_price
        return (
            f"{type(self).__name__}(bid={bid}x{self.best_bid_size}, "
            f"ask={ask}x{self.best_ask_size}, "
            f"levels={len(self.levels_map(BUY))}/{len(self.levels_map(SELL))})"
        )

# ---------------------------------------------------------------------------------
# Axis B: the performance ladder.
#
# Matching is identical in every class below; what differs is how the best price is
# found.  The first three keep the dicts as storage and add an index beside them, and
# override `best_price` plus the `set_size` that keeps that index in step.  Varying
# one factor is what lets a timing difference have a single cause.
#
# The last one stops varying one factor on purpose.  A real low-latency book *fuses*
# storage and index -- the sizes live in the tick-indexed array itself -- and
# TickArrayBook is that book, so the step from BitmapBook to it measures exactly the
# fusion and nothing else.
# ---------------------------------------------------------------------------------


class CachedBestBook(AggregateBook):
    """Step 2: remember the best price, and repair it when that level empties.

    The best price is read at least once by every incoming order and changes far less
    often than it is read, so cache it.  Invalidation is the whole difficulty and it has
    exactly three cases, which :meth:`_best_after` enumerates.

    The cache is derived state: ``_cached`` is recoverable from the levels at any
    moment, which :meth:`check_cache_is_consistent` asserts.  Repairing it at write time
    rather than at read time leaves :meth:`best_price` a lookup with no side effects; a
    lazy variant that marked the cache stale and rescanned on the next read measures the
    same to within 1%, so the simpler shape is kept.

    ``_cached`` is keyed by direction rather than held as two attributes because the
    code around it is generic in ``d``.  Timing the alternatives is a notebook exercise:
    they are within a few nanoseconds of each other, so this is a choice about uniformity
    rather than speed.
    """

    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self._cached: dict[int, int | None] = {BUY: None, SELL: None}

    def set_size(self, direction: int, price: int, size: int) -> None:
        super().set_size(direction, price, size)
        self._cached[direction] = self._best_after(direction, price, size)

    def _best_after(self, direction: int, price: int, size: int) -> int | None:
        """What the best price becomes once this level holds ``size``.

        Total in the three cases, so there is no fourth to forget.
        """
        best = self._cached[direction]
        # price * direction > best * direction: "better" for whichever side.
        if size > 0 and (best is None or price * direction > best * direction):
            return price
        if size == 0 and price == best:
            # The cached price no longer names a level and nothing local says what
            # replaces it, so this is the one case that pays for a rescan.
            return self._rescan(direction)
        # Any other change is at a price no better than the best, or leaves size
        # resting there: either way the best price cannot have moved.
        return best

    def _rescan(self, direction: int) -> int | None:
        levels = self.levels_map(direction)
        if not levels:
            return None
        return max(levels) if direction == BUY else min(levels)

    def best_price(self, direction: int) -> int | None:
        return self._cached[direction]

    def check_cache_is_consistent(self) -> None:
        """Check the cache against a full rescan.  For tests and debug runs.

        Raises rather than returning a verdict, for the same reason
        :meth:`check_invariants` does: a check whose result can be discarded is a check
        that will be.
        """
        for direction in (BUY, SELL):
            expected = self._rescan(direction)
            if self._cached[direction] != expected:
                raise AssertionError(
                    f"cached best price on side {direction} is "
                    f"{self._cached[direction]}, rescan says {expected}"
                )


class HeapBook(AggregateBook):
    """Step 3: a heap of candidate prices, with lazy deletion.

    ``heapq`` is a min-heap only, so the bid side stores negated prices.  Removing a
    price from the middle of a heap is not supported, so entries are left behind and
    discarded when they reach the top and name an empty level: the top of the heap may
    be stale, and is popped until it is not.

    The cost of lazy deletion is that the heap grows with every level ever created, so a
    long run needs periodic compaction.  :meth:`compact` does that, and its necessity is
    part of the cost of the technique.
    """

    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self._heaps: dict[int, list[int]] = {BUY: [], SELL: []}

    def set_size(self, direction: int, price: int, size: int) -> None:
        super().set_size(direction, price, size)
        if size > 0:
            # Negate on the bid side so that "largest price" becomes "smallest key".
            heapq.heappush(self._heaps[direction], -price if direction == BUY else price)

    def best_price(self, direction: int) -> int | None:
        heap = self._heaps[direction]
        levels = self.levels_map(direction)
        while heap:
            price = -heap[0] if direction == BUY else heap[0]
            if price in levels:
                return price
            heapq.heappop(heap)  # stale entry: the level is gone
        return None

    def compact(self) -> None:
        """Rebuild both heaps from the live levels, discarding stale entries."""
        for direction in (BUY, SELL):
            live = [-p if direction == BUY else p for p in self.levels_map(direction)]
            heapq.heapify(live)
            self._heaps[direction] = live

    def heap_overhead(self) -> dict[int, int]:
        """Stale entries currently carried on each side.  For the notebook."""
        return {
            direction: len(self._heaps[direction]) - len(self.levels_map(direction))
            for direction in (BUY, SELL)
        }


class BitmapBook(AggregateBook):
    """Step 4b: occupancy as a single arbitrary-precision integer.

    In C++ the next active level is found with a hierarchy of 64-bit words and a
    count-trailing-zeros instruction.  Python has arbitrary-precision integers, so the
    whole band is *one* integer used as a bitset and the two searches are one
    expression each:

    * highest set bit -- ``bits.bit_length() - 1``;
    * lowest set bit  -- ``(bits & -bits).bit_length() - 1``.

    Both identities, and the reason the second costs O(span) where the first is O(1),
    are derived in ``documentation/integers-in-binary.md``.

    ``origin`` only keeps the integer narrow.  Unlike an array there is no upper edge to
    fall off: the bitmap grows as prices arrive, so its span tracks the market rather
    than a declared band.
    """

    def __init__(self, origin: int, strict: bool = False):
        super().__init__(strict)
        self.origin = origin
        self._bits: dict[int, int] = {BUY: 0, SELL: 0}

    @classmethod
    def for_prices(cls, prices: "Iterable[int]", strict: bool = False) -> "BitmapBook":
        # Only to keep the integer narrow: the bitmap has no upper edge to fall off.
        prices = grid_prices(prices)
        origin = min(prices) - cls.BAND_MARGIN if prices else 0
        return cls(origin=origin, strict=strict)

    def _empty_like(self) -> "BitmapBook":
        return type(self)(origin=self.origin, strict=self.strict)

    def set_size(self, direction: int, price: int, size: int) -> None:
        super().set_size(direction, price, size)
        bit = 1 << (price - self.origin)
        if size > 0:
            self._bits[direction] |= bit
        else:
            self._bits[direction] &= ~bit

    def best_price(self, direction: int) -> int | None:
        bits = self._bits[direction]
        if not bits:
            return None
        if direction == BUY:
            return self.origin + bits.bit_length() - 1
        return self.origin + (bits & -bits).bit_length() - 1

    def span_bits(self, direction: int, reported_depth: ReportedDepth) -> int:
        return _span_bits(
            self._bits[direction], self.origin,
            self.occupied_levels(direction, reported_depth),
        )

    def gap_count(self, direction: int, reported_depth: ReportedDepth) -> int:
        return count_binary_gaps(self.span_bits(direction, reported_depth))

    def largest_gap_size_between_non_empty_levels(
        self, direction: int, reported_depth: ReportedDepth
    ) -> int:
        return measure_largest_binary_gap(self.span_bits(direction, reported_depth))


class TickArrayBook(AggregateBook):
    """Step 5: storage and index fused -- the shape of a real low-latency book.

    Every class above keeps the sizes in a dict and puts an index beside it.  A
    production book does not: prices already live on an integer grid, so the tick *is*
    the array subscript, and the size is read where the occupancy bit is set.  There
    is no dict here at all, and :meth:`levels_map` builds one only when something asks
    to inspect the book.

    What that buys is one indirection instead of two, and contiguous memory.  In C the
    second is the larger effect; in CPython it is a claim to measure rather than assume,
    since the interpreter's own overhead may exceed the difference.

    What it costs is stated in the constructor: a band, fixed in advance, occupied or
    not.  A lookup table costs the whole table, and a real venue either shifts the band
    as the price drifts or falls back to a sorted map for a range too wide and too
    sparse to index.  Neither is worth building before the simple version is measured.

    Having a band buys something the rung below cannot have.  ``bit_length`` finds the
    *highest* set bit in constant time and the lowest only by scanning, so the ask side
    of a single bitmap pays for the whole span at every lookup.  Here the sell side is
    indexed **downward from the ceiling** -- bit ``ceiling - price`` rather than
    ``price - origin`` -- and the best price on either side is the highest set bit.
    :class:`BitmapBook` cannot do this: it has no upper edge to count down from.

    The sizes stay indexed by ``price - origin`` on both sides; only the occupancy
    bitmap is reversed.  The consequence is that the band's *upper* edge is now
    load-bearing on the ask side, where before only the lower one was, so the
    band-shifting this docstring anticipates would have to move the ask bitmap rather
    than merely extend the array.

    Deliberately a plain ``list`` and not a numpy array: this access pattern is one
    element at a time, which is where numpy is *slower* than a list, and the trade it
    offers here is space rather than speed.
    """

    def __init__(self, origin: int, width: int, strict: bool = False):
        super().__init__(strict)
        self.origin = origin
        self.width = width
        #: Highest price the band holds.  The ask bitmap counts down from it, so this is
        #: part of the encoding and not a derived convenience: a copy that changed the
        #: width would decode every ask bit to the wrong price.
        self.ceiling = origin + width - 1
        self._sizes: dict[int, list[int]] = {
            BUY: [0] * width,
            SELL: [0] * width,
        }
        self._bits: dict[int, int] = {BUY: 0, SELL: 0}
        # There is no dict storage here, so the inherited attributes would be two empty
        # maps quietly claiming the book is empty.  Removing them turns any code that
        # reaches past the primitives into an AttributeError instead of a wrong answer.
        del self.bids, self.asks

    @classmethod
    def for_prices(cls, prices: Iterable[int], strict: bool = False) -> "TickArrayBook":
        prices = grid_prices(prices)
        low, high = (min(prices), max(prices)) if prices else (0, 0)
        return cls(
            origin=low - cls.BAND_MARGIN,
            width=high - low + 2 * cls.BAND_MARGIN,
            strict=strict,
        )

    def _empty_like(self) -> "TickArrayBook":
        return type(self)(origin=self.origin, width=self.width, strict=self.strict)

    def size_at(self, direction: int, price: int) -> int:
        """Zero outside the band, rather than an error.

        Reads run off the edge in ordinary use -- ``levels(SELL, 10)`` walks ten grid
        positions up from the best ask whether or not the band reaches that far -- and
        a grid position outside the band holds nothing, which is a true answer.  Writes
        are the other case, and they raise.
        """
        index = price - self.origin
        if not 0 <= index < self.width:
            return 0
        return self._sizes[direction][index]

    def set_size(self, direction: int, price: int, size: int) -> None:
        index = price - self.origin
        if not 0 <= index < self.width:
            raise ValueError(
                f"price {price} is outside the band "
                f"[{self.origin}, {self.origin + self.width}); a real book would shift "
                "the band or fall back to a sorted map"
            )
        self._sizes[direction][index] = size
        bit = 1 << (index if direction == BUY else self.ceiling - price)
        if size > 0:
            self._bits[direction] |= bit
        else:
            self._bits[direction] &= ~bit

    def best_price(self, direction: int) -> int | None:
        bits = self._bits[direction]
        if not bits:
            return None
        index = bits.bit_length() - 1
        return self.origin + index if direction == BUY else self.ceiling - index

    def levels_map(self, direction: int) -> dict[int, int]:
        """Built on demand, by walking the occupancy bits from the bottom up.

        Nothing on the hot path calls this -- matching reads single sizes and the
        best price -- so the cost lands only where a caller genuinely wants the whole
        book, which is inspection, comparison and drawing.
        """
        sizes = self._sizes[direction]
        bits = self._bits[direction]
        origin, ceiling = self.origin, self.ceiling
        buying = direction == BUY
        levels: dict[int, int] = {}
        while bits:
            index = bits.bit_length() - 1
            price = origin + index if buying else ceiling - index
            levels[price] = sizes[price - origin]
            bits ^= 1 << index
        return levels

    def occupied_levels(
        self, direction: int, reported_depth: ReportedDepth
    ) -> list[tuple[int, int]]:
        """Walk the occupancy bits from the touch.

        The inherited version reaches for :meth:`levels_map`, which here builds a whole
        dict; this reads only the levels asked for.
        """
        if reported_depth <= 0:
            raise ValueError(f"reported_depth must be >= 1, got {reported_depth}")
        bits = self._bits[direction]
        sizes = self._sizes[direction]
        origin, ceiling = self.origin, self.ceiling
        buying = direction == BUY
        found: list[tuple[int, int]] = []
        while bits and len(found) < reported_depth:
            index = bits.bit_length() - 1
            price = origin + index if buying else ceiling - index
            found.append((price, sizes[price - origin]))
            bits ^= 1 << index
        return found

    def span_bits(self, direction: int, reported_depth: ReportedDepth) -> int:
        """The occupancy window, cut in this book's own bit order.

        The ask bits count down from the ceiling, so the window is measured from there;
        taking ``price - origin`` on both sides would mask the wrong end of the integer
        and read the gaps of a book reflected in the band.
        """
        levels = self.occupied_levels(direction, reported_depth)
        if len(levels) < 2:
            return 0
        base = self.origin if direction == BUY else self.ceiling
        first, last = abs(levels[0][0] - base), abs(levels[-1][0] - base)
        low, high = (first, last) if first < last else (last, first)
        return (self._bits[direction] & (((1 << (high - low + 1)) - 1) << low)) >> low

    def gap_count(self, direction: int, reported_depth: ReportedDepth) -> int:
        return count_binary_gaps(self.span_bits(direction, reported_depth))

    def largest_gap_size_between_non_empty_levels(
        self, direction: int, reported_depth: ReportedDepth
    ) -> int:
        return measure_largest_binary_gap(self.span_bits(direction, reported_depth))

    def queue_imbalance(self, n: GridDepth) -> float:
        """Read the grid window straight out of the size array.

        The inherited version walks ``bid_size(i)``, each of which re-derives the best
        price; here the band *is* the grid, so the window is a slice of it.
        """
        if n <= 0:
            raise ValueError(f"n counts grid levels from the touch and must be >= 1, got {n}")
        totals = []
        for direction in (BUY, SELL):
            best = self.best_price(direction)
            if best is None:
                totals.append(0)
                continue
            sizes = self._sizes[direction]
            start = best - self.origin
            indices = range(start, start - n, -1) if direction == BUY else range(start, start + n)
            totals.append(sum(sizes[i] for i in indices if 0 <= i < self.width))
        total = totals[0] + totals[1]
        if total == 0:
            return float("nan")
        return (totals[0] - totals[1]) / total

    def queue_imbalance_profile(
        self, imbalance_levels: tuple[GridDepth, ...]
    ) -> list[float]:
        """The nested windows as one slice of the size array per side.

        The band *is* the grid, so the running totals are ``itertools.accumulate`` over a
        slice and never enter Python.  Where the window runs off the band the slice comes
        back short, and the total stops growing: a position outside the band holds
        nothing, which :meth:`size_at` already gives as a true answer.
        """
        deepest = max(imbalance_levels)
        if deepest <= 0:
            raise ValueError(
                f"n counts grid levels from the touch and must be >= 1, got {deepest}"
            )
        running: dict[int, list[int]] = {}
        for direction in (BUY, SELL):
            best = self.best_price(direction)
            if best is None:
                running[direction] = [0] * deepest
                continue
            sizes = self._sizes[direction]
            start = best - self.origin
            window = (
                sizes[max(0, start - deepest + 1):start + 1][::-1] if direction == BUY
                else sizes[start:start + deepest]
            )
            totals = list(accumulate(window))
            totals += [totals[-1]] * (deepest - len(totals))
            running[direction] = totals
        profile = []
        for n in imbalance_levels:
            bid_total, ask_total = running[BUY][n - 1], running[SELL][n - 1]
            total = bid_total + ask_total
            profile.append(
                float("nan") if total == 0 else (bid_total - ask_total) / total
            )
        return profile

    def copy(self) -> "TickArrayBook":
        clone = self._empty_like()
        clone._sizes = {
            direction: sizes.copy() for direction, sizes in self._sizes.items()
        }
        clone._bits = dict(self._bits)
        return clone


#: The ladder in order, for benchmarks and for the notebook.
AXIS_B_VARIANTS = (
    AggregateBook,
    CachedBestBook,
    HeapBook,
    BitmapBook,
    TickArrayBook,
)
