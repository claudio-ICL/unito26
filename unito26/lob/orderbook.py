"""Both representations of a limit order book, deliberately in one file.

The organising result of this strand is that they are *different*, and the difference
is legible only when they sit side by side:

**The aggregate book is a sufficient statistic for the public book.**  With the state
held as ``{price: volume}`` on each side, the transition

    (aggregate book, incoming order) -> (new aggregate book, fills as [(pi, size)])

is well defined on that state alone, because matching consumes level ``pi`` in FIFO
order and the total consumed there is ``min(remaining q, V[pi])`` -- *independent of
how V[pi] decomposes into individual orders*.  The queue inside a level therefore
never has to be represented at all.

**Aggregation fails the moment a question concerns a named order.**  Not "what is the
book" but "what about *this* order": how much volume is ahead of mine, will it be
filled, whose fill was that, what is account X's PnL.  Those need identity, and
identity is what the order-level book buys -- at a cost this file also makes visible.

Both books are **mutable fold accumulators**: they hold one state, the current one.
They have no notion of history and no time index.  The time series of states is the
business of :mod:`unito26.lob.replay`, which folds a stream through a book and taps
whatever the caller asked to record.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import numpy as np

from unito26.lob.messages import (
    BUY,
    SELL,
    Fill,
    LevelDelta,
    Message,
    MessageType,
    is_market_price,
)

__all__ = [
    "SubmitResult",
    "AggregateBook",
    "CachedBestBook",
    "HeapBook",
    "BandBook",
    "BitmapBook",
    "AXIS_B_VARIANTS",
]


@dataclass(frozen=True, slots=True)
class SubmitResult:
    """What one submission did: the trades it printed and the levels it moved."""

    fills: list[Fill] = field(default_factory=list)
    deltas: list[LevelDelta] = field(default_factory=list)

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


class AggregateBook:
    """The ``{price: volume}`` book: rungs L0 to L3 of the ladder.

    Prices are integer tick counts.  The two sides are plain dicts, and the best
    prices are found by scanning their keys -- the honest baseline, O(number of
    occupied levels) per lookup.  Every faster variant in this module keeps this
    class's matching logic and overrides only the best-price lookup, which is the
    point: the performance ladder is *entirely* about finding the best price.

    Parameters
    ----------
    strict
        When True, a withdrawal for more volume than is resting raises.  When False
        (the default) it removes what is there and carries on, which is what replaying
        a real feed needs, since a feed's early messages often reference orders posted
        before the file began.
    """

    def __init__(self, *, strict: bool = False):
        self.bids: dict[int, int] = {}
        self.asks: dict[int, int] = {}
        self.strict = strict

    # ---- section 3: the configuration -------------------------------------------

    def side(self, direction: int) -> dict[int, int]:
        """The level map on the given side.  ``+1`` is the bid side, ``-1`` the ask."""
        return self.bids if direction == BUY else self.asks

    def best_price(self, direction: int) -> int | None:
        """Best price on the given side: highest bid, or lowest ask.

        **This is the one method the performance ladder replaces.**  Here it is a full
        scan of the dict keys -- O(number of occupied levels), correct, and obviously
        so.  Every faster variant in this module overrides exactly this method and
        inherits the matching logic unchanged, which is the point: the ladder is
        entirely about finding the best price, not about matching.
        """
        levels = self.side(direction)
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
        volume rests there -- section 3 is explicit that intermediate levels may be
        empty, and case B of the worked example has two of them.
        """
        best = self.best_bid_price
        return None if best is None else best - (level - 1)

    def ask_price(self, level: int) -> int | None:
        """``P^{a,i} = P^a + (i-1) tau``, in ticks.  Levels are 1-indexed."""
        best = self.best_ask_price
        return None if best is None else best + (level - 1)

    def bid_volume_at(self, price: int) -> int:
        """``V^b_t(p)``: resting buy volume at an absolute price."""
        return self.bids.get(price, 0)

    def ask_volume_at(self, price: int) -> int:
        """``V^a_t(p)``: resting sell volume at an absolute price."""
        return self.asks.get(price, 0)

    def bid_volume(self, level: int) -> int:
        """``V^{b,i}``, volume at the ``i``-th bid level.  Zero for ``i <= 0``."""
        price = self.bid_price(level)
        return 0 if price is None or level <= 0 else self.bids.get(price, 0)

    def ask_volume(self, level: int) -> int:
        """``V^{a,i}``, volume at the ``i``-th ask level.  Zero for ``i <= 0``."""
        price = self.ask_price(level)
        return 0 if price is None or level <= 0 else self.asks.get(price, 0)

    @property
    def best_bid_volume(self) -> int:
        """``V^b``, volume at the best bid."""
        return self.bid_volume(1)

    @property
    def best_ask_volume(self) -> int:
        """``V^a``, volume at the best ask."""
        return self.ask_volume(1)

    def levels(self, direction: int, depth: int) -> list[tuple[int, int]]:
        """The first ``depth`` grid positions on a side, as ``(price, volume)``.

        Includes empty positions, so the result always has length ``depth`` when the
        side is non-empty.  That is what makes it comparable with a feed's fixed-width
        snapshot.
        """
        price_of = self.bid_price if direction == BUY else self.ask_price
        volume_of = self.bid_volume if direction == BUY else self.ask_volume
        if self.best_price(direction) is None:
            return []
        return [(price_of(i), volume_of(i)) for i in range(1, depth + 1)]

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

    def queue_imbalance(self, depth: int = 1) -> float:
        """``I^n``: bid minus ask over the total, over the first ``depth`` levels.

        Lies in ``[-1, +1]`` and is **positive when the book is bid-heavy**.  Inverting
        this sign silently inverts every signal built on it, which is why it is stated
        here rather than left to the reader.

        Raises when both sides are empty over the requested depth: that is ``0/0``, and
        asserting the precondition is more honest than returning a number.
        """
        bid_total = sum(self.bid_volume(i) for i in range(1, depth + 1))
        ask_total = sum(self.ask_volume(i) for i in range(1, depth + 1))
        total = bid_total + ask_total
        if total == 0:
            raise ValueError(
                f"queue imbalance is undefined: no volume within {depth} level(s) of "
                "either best price"
            )
        return (bid_total - ask_total) / total

    # ---- sections 2 and 6: the update ---------------------------------------------

    def apply(self, message: Message) -> SubmitResult:
        """Apply any message.  The stream driver's single entry point."""
        if message.kind is MessageType.SUBMIT:
            return self.submit(message)
        return self.withdraw(message)

    def submit(self, message: Message) -> SubmitResult:
        """Process an incoming order: consume the opposite side, then rest the rest.

        One code path, not two.  By the decomposition of section 6 an incoming order is
        equivalent to a market order of size ``q_M`` followed by a resting order of
        size ``q - q_M``, so there is no separate branch for "marketable" orders --
        the loop simply does not execute when nothing matches.
        """
        remaining = message.size
        direction = message.direction
        limit_price = message.price
        opposite = self.side(-direction)
        fills: list[Fill] = []
        deltas: list[LevelDelta] = []

        # 1. The market-order part: consume while the price constraint permits.
        while remaining > 0 and opposite:
            best = self.best_price(-direction)
            # pi*d <= p*d handles both sides in one expression: for a buy this is
            # "the best ask is not above my limit", for a sell "the best bid is not
            # below it".  Stop as soon as it fails.
            if best * direction > limit_price * direction:
                break
            traded = min(remaining, opposite[best])
            remaining -= traded
            left_at_level = opposite[best] - traded
            if left_at_level:
                opposite[best] = left_at_level
            else:
                del opposite[best]
            self._level_changed(-direction, best, left_at_level)
            # A fill trades at the RESTING order's price, never the incoming one.
            fills.append(Fill(price=best, size=traded, aggressor=direction))
            deltas.append(LevelDelta(side=-direction, price=best, volume=left_at_level))

        # 2. The resting part.  A genuine market order must never rest: without this
        # guard an oversized market sell would rest at price 0 and match every buy
        # that followed, silently corrupting the book from that point on.
        if remaining > 0 and not is_market_price(limit_price):
            own = self.side(direction)
            own[limit_price] = own.get(limit_price, 0) + remaining
            self._level_changed(direction, limit_price, own[limit_price])
            deltas.append(
                LevelDelta(side=direction, price=limit_price, volume=own[limit_price])
            )

        return SubmitResult(fills=fills, deltas=deltas)

    def withdraw(self, message: Message) -> SubmitResult:
        """Remove resting volume at ``(price, direction)``, addressed by quantity.

        This is the rung-L3 "near miss": it *looks* as though naming an order should be
        necessary, and it is not.  A quantity-addressed withdrawal is one more signed
        delta on the aggregate state, so the state does not grow.  What changes is that
        level volumes stop being monotone, the best price can now move in both
        directions, and the book can empty entirely.
        """
        own = self.side(message.direction)
        resting = own.get(message.price, 0)
        if message.size > resting and self.strict:
            raise ValueError(
                f"cannot withdraw {message.size} at price {message.price}: only "
                f"{resting} resting"
            )
        removed = min(message.size, resting)
        if removed == 0:
            return SubmitResult()
        left = resting - removed
        if left:
            own[message.price] = left
        else:
            del own[message.price]
        self._level_changed(message.direction, message.price, left)
        return SubmitResult(
            deltas=[LevelDelta(side=message.direction, price=message.price, volume=left)]
        )

    def _level_changed(self, direction: int, price: int, volume: int) -> None:
        """Hook: a level on ``direction`` now holds ``volume`` (``0`` meaning gone).

        A no-op here, because a book that scans for its best price has no index to keep
        in step.  It exists so that the faster variants can maintain one without
        reimplementing the matching loop -- the loop is written once, in this class.
        """

    # ---- housekeeping ---------------------------------------------------------------

    def copy(self) -> "AggregateBook":
        """An independent copy of the current state.

        A snapshot tap that stores the book itself stores *the same mutable object*
        every time, so every recorded snapshot ends up equal to the final state.  This
        method exists so that the tap has something correct to call.
        """
        clone = self._empty_like()
        for direction, levels in ((BUY, self.bids), (SELL, self.asks)):
            for price, volume in levels.items():
                clone.side(direction)[price] = volume
                clone._level_changed(direction, price, volume)
        return clone

    @classmethod
    def from_levels(
        cls, bids: dict[int, int], asks: dict[int, int], **kwargs
    ) -> "AggregateBook":
        """Build a book from ``{price: volume}`` maps on each side.

        Goes through :meth:`_level_changed` for every level, so the variants that keep
        an index are correctly initialised.  Assigning to ``book.bids`` directly would
        leave those indices empty and the book quietly wrong -- which is precisely the
        class of bug a cache invites.
        """
        book = cls(**kwargs)
        for direction, levels in ((BUY, bids), (SELL, asks)):
            for price, volume in levels.items():
                if volume <= 0:
                    raise ValueError(f"level at {price} must hold positive volume")
                book.side(direction)[price] = volume
                book._level_changed(direction, price, volume)
        book.check_invariants()
        return book

    def _empty_like(self) -> "AggregateBook":
        """A new, empty book with the same configuration.  Subclasses with extra
        constructor arguments override this rather than :meth:`copy`."""
        return type(self)(strict=self.strict)

    def check_invariants(self) -> None:
        """Assert what must be true of any book, at any time.

        The book never crossing is a *consequence* of the matching rule, not an extra
        assumption, so a crossed book is a bug rather than a market state.
        """
        bid, ask = self.best_bid_price, self.best_ask_price
        if bid is not None and ask is not None and bid >= ask:
            raise AssertionError(f"crossed book: best bid {bid} >= best ask {ask}")
        for name, levels in (("bid", self.bids), ("ask", self.asks)):
            for price, volume in levels.items():
                if volume <= 0:
                    raise AssertionError(
                        f"{name} level at {price} holds {volume}: a price whose queue "
                        "empties must be removed, not kept at zero"
                    )

    def __repr__(self) -> str:
        bid, ask = self.best_bid_price, self.best_ask_price
        return (
            f"{type(self).__name__}(bid={bid}x{self.best_bid_volume}, "
            f"ask={ask}x{self.best_ask_volume}, levels={len(self.bids)}/{len(self.asks)})"
        )


# ---------------------------------------------------------------------------------
# Axis B: the performance ladder.
#
# Every class below inherits the matching logic of AggregateBook untouched and
# overrides only best_price, plus the _level_changed hook needed to keep its index in
# step.  That isolation is deliberate: it makes the benchmark measure one thing.
#
# A caveat to state plainly, because it is the one place we depart from the production
# design.  A real low-latency book fuses *storage* and *index* -- volumes live in the
# tick-indexed array itself.  Here the dicts remain the storage and the array or bitmap
# is only an occupancy index alongside them.  That costs some of the cache locality the
# real design is chasing, and it is the right trade for a course: it varies one factor
# instead of two, so a timing difference has a single cause.
# ---------------------------------------------------------------------------------


class CachedBestBook(AggregateBook):
    """Step 2: remember the best price, and repair it only when that level empties.

    The observation is that the best price changes rarely compared with how often it is
    read: every incoming order reads it at least once, while only an order that clears
    a level, or one that improves on it, moves it.  So cache it.

    Invalidation is the whole difficulty, and it has exactly two cases.  A level
    appearing at a *better* price updates the cache immediately.  The *best* level
    disappearing marks the cache stale, and the next read pays for one rescan.  Any
    other change cannot affect the best price and is ignored.
    """

    def __init__(self, *, strict: bool = False):
        super().__init__(strict=strict)
        self._cached: dict[int, int | None] = {BUY: None, SELL: None}
        self._stale: dict[int, bool] = {BUY: False, SELL: False}

    def _level_changed(self, direction: int, price: int, volume: int) -> None:
        if volume > 0:
            best = self._cached[direction]
            # price * direction > best * direction: "better" for whichever side.
            if best is None or price * direction > best * direction:
                self._cached[direction] = price
                self._stale[direction] = False
        elif self._cached[direction] == price:
            self._stale[direction] = True

    def best_price(self, direction: int) -> int | None:
        if self._stale[direction]:
            levels = self.side(direction)
            if levels:
                self._cached[direction] = max(levels) if direction == BUY else min(levels)
            else:
                self._cached[direction] = None
            self._stale[direction] = False
        return self._cached[direction]

    def verify_cache(self) -> None:
        """Check the cache against a full rescan.  For tests and debug runs only.

        A cache is a claim about state held somewhere else, and the only honest way to
        keep one is to be able to check it.  This is also the property test.
        """
        for direction in (BUY, SELL):
            levels = self.side(direction)
            expected = (max(levels) if direction == BUY else min(levels)) if levels else None
            if self.best_price(direction) != expected:
                raise AssertionError(
                    f"cached best price on side {direction} is "
                    f"{self.best_price(direction)}, rescan says {expected}"
                )


class HeapBook(AggregateBook):
    """Step 3: a heap of candidate prices, with lazy deletion.

    ``heapq`` is a min-heap only, so the bid side stores negated prices -- the standard
    trick, and worth meeting once.  Removing a price from the middle of a heap is not
    supported, so we do not try: entries are left behind and discarded when they reach
    the top and turn out to name an empty level.  **The top of the heap may be stale;
    pop until it is not.**

    The cost of lazy deletion is that the heap grows with every level that is ever
    created, so a long run wants periodic compaction.  :meth:`compact` does that, and
    the fact that it is needed at all is the honest half of the technique.
    """

    def __init__(self, *, strict: bool = False):
        super().__init__(strict=strict)
        self._heaps: dict[int, list[int]] = {BUY: [], SELL: []}

    def _level_changed(self, direction: int, price: int, volume: int) -> None:
        if volume > 0:
            # Negate on the bid side so that "largest price" becomes "smallest key".
            heapq.heappush(self._heaps[direction], -price if direction == BUY else price)

    def best_price(self, direction: int) -> int | None:
        heap = self._heaps[direction]
        levels = self.side(direction)
        while heap:
            price = -heap[0] if direction == BUY else heap[0]
            if price in levels:
                return price
            heapq.heappop(heap)  # stale entry: the level is gone
        return None

    def compact(self) -> None:
        """Rebuild both heaps from the live levels, discarding stale entries."""
        for direction in (BUY, SELL):
            live = [-p if direction == BUY else p for p in self.side(direction)]
            heapq.heapify(live)
            self._heaps[direction] = live

    def heap_overhead(self) -> dict[int, int]:
        """Stale entries currently carried on each side.  For the notebook."""
        return {
            direction: len(self._heaps[direction]) - len(self.side(direction))
            for direction in (BUY, SELL)
        }


class BandBook(AggregateBook):
    """Step 4: an occupancy array over a band of ticks, walked with a cursor.

    Prices live on a fixed grid, so a tick can index an array directly:
    ``occupied[p - origin]``.  Each side keeps its own array and a **cursor** at the
    last known best index.  The cursor is what makes this design fast in C: when the
    best level is consumed, the next one is almost always a tick or two away, so the
    search is a couple of steps rather than a scan.  Only when the near neighbourhood
    is empty does it fall back to a vectorised search over the rest of the band.

    Out-of-band prices raise.  Production shifts the band, or falls back to a sorted
    map for wide and sparse ranges; both are worth knowing about, and neither is worth
    implementing before the simple version has been measured.
    """

    #: How far to walk in Python before handing over to a vectorised search.  The
    #: near-neighbour case is the common one, and it is the one worth not paying numpy
    #: call overhead for.
    LOCAL_SCAN = 32

    def __init__(self, *, origin: int, width: int, strict: bool = False):
        super().__init__(strict=strict)
        self.origin = origin
        self.width = width
        self._occupied = {
            BUY: np.zeros(width, dtype=bool),
            SELL: np.zeros(width, dtype=bool),
        }
        self._cursor: dict[int, int | None] = {BUY: None, SELL: None}
        self._stale: dict[int, bool] = {BUY: False, SELL: False}

    def _empty_like(self) -> "BandBook":
        return type(self)(origin=self.origin, width=self.width, strict=self.strict)

    def _level_changed(self, direction: int, price: int, volume: int) -> None:
        index = price - self.origin
        if not 0 <= index < self.width:
            raise ValueError(
                f"price {price} is outside the band "
                f"[{self.origin}, {self.origin + self.width}); a real book would shift "
                "the band or fall back to a sorted map"
            )
        occupied = self._occupied[direction]
        if volume > 0:
            occupied[index] = True
            cursor = self._cursor[direction]
            # ">=" and not ">": if the stale cursor's own price is refilled, the cursor
            # is valid again.  With ">" it would stay stale and the search below would
            # start one step past it, walking straight over the true best price.
            if cursor is None or index * direction >= cursor * direction:
                self._cursor[direction] = index
                self._stale[direction] = False
        else:
            occupied[index] = False
            if self._cursor[direction] == index:
                self._stale[direction] = True

    def best_price(self, direction: int) -> int | None:
        if not self._stale[direction]:
            cursor = self._cursor[direction]
            return None if cursor is None else self.origin + cursor
        index = self._search(direction)
        self._cursor[direction] = index
        self._stale[direction] = False
        return None if index is None else self.origin + index

    def _search(self, direction: int) -> int | None:
        """Walk away from the stale cursor towards worse prices, then vectorise."""
        occupied = self._occupied[direction]
        start = self._cursor[direction]
        step = -direction  # towards worse prices: down for bids, up for asks

        index = start
        for _ in range(self.LOCAL_SCAN):
            index += step
            if not 0 <= index < self.width:
                return None
            if occupied[index]:
                return index

        # The near neighbourhood was empty; fall back to a search over the remainder.
        remainder = occupied[:index] if direction == BUY else occupied[index + 1 :]
        hits = np.flatnonzero(remainder)
        if hits.size == 0:
            return None
        return int(hits[-1]) if direction == BUY else index + 1 + int(hits[0])


class BitmapBook(AggregateBook):
    """Step 4b: occupancy as a single arbitrary-precision integer.

    In C++ the next active level is found with a hierarchy of 64-bit words and a
    count-trailing-zeros instruction.  Python has arbitrary-precision integers, so the
    whole band is *one* integer used as a bitset and the two searches are one
    expression each:

    * highest set bit -- ``bits.bit_length() - 1``;
    * lowest set bit  -- ``(bits & -bits).bit_length() - 1``, since ``bits & -bits``
      isolates the lowest set bit by two's complement.

    This is a rare case where Python states a genuine low-latency trick *more* clearly
    than C++ does, which is why it earns a place in the course.  The honest caveat: a
    big-integer operation is O(width of the band), not O(1), so a wide band erases the
    advantage.  That is a claim to measure, not to believe.
    """

    def __init__(self, *, origin: int = 0, strict: bool = False):
        super().__init__(strict=strict)
        self.origin = origin
        self._bits: dict[int, int] = {BUY: 0, SELL: 0}

    def _empty_like(self) -> "BitmapBook":
        return type(self)(origin=self.origin, strict=self.strict)

    def _level_changed(self, direction: int, price: int, volume: int) -> None:
        bit = 1 << (price - self.origin)
        if volume > 0:
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


#: The ladder in order, for benchmarks and for the notebook.
AXIS_B_VARIANTS = (AggregateBook, CachedBestBook, HeapBook, BandBook, BitmapBook)
