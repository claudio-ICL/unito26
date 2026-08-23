"""The aggregate book, and the ladder of faster ways to find its best price.

The state is ``{price: volume}`` on each side, in tick counts.  ``prop.lobUpdate`` is
stated entirely on that state, which is the whole content of holding it: the aggregate
book is closed under the arrival of an order, so the queue inside a level never has to
be represented.  What it cannot do is answer a question about a *named* order -- how
much volume is ahead of mine, whose fill was that -- and that is the order-level book,
which lives elsewhere.

Every class here is a **mutable fold accumulator**: one state, the current one, with no
history and no time index.  The time series is the business of :mod:`unito26.lob.replay`.

The faster variants change *only* how the best price is found; the matching logic is
written once, in :class:`AggregateBook`, and inherited unchanged.  That isolation is
what makes the benchmark measure one thing.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable
from dataclasses import dataclass, field


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
    "BitmapBook",
    "TickArrayBook",
    "AXIS_B_VARIANTS",
]


@dataclass(frozen=True, slots=True)
class SubmitResult:
    """What one submission did: the trades it printed and the levels it moved."""

    fills: list[Fill] = field(default_factory=list)
    deltas: list[LevelDelta] = field(default_factory=list)
    unfilled: int = 0
    """Shares that neither executed nor rested, and so left the book entirely.

    Non-zero only for a market order that found nothing to trade against: having named
    no price of its own, and no price to inherit, its remainder is unfillable interest
    returned to the sender rather than an order.  Named rather than dropped, because
    shares that vanish silently are the kind of bug a test never catches.
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

    def __init__(self, strict: bool = False):
        self.bids: dict[int, int] = {}
        self.asks: dict[int, int] = {}
        self.strict = strict

    # ---- storage: the four operations every book must provide ---------------------
    #
    # Matching, the derived quantities and the housekeeping below are written against
    # these and nothing else, so a book that keeps its volumes somewhere other than two
    # dicts inherits all of it.  Here they are the obvious thing: the dicts are the
    # storage, and `levels_map` hands one back rather than building it.

    def levels_map(self, direction: int) -> dict[int, int]:
        """Every occupied level on a side, as ``{price: volume}``.

        Read-only from the caller's point of view.  The baseline's storage *is* this
        map, so it is returned; a book that stores volumes elsewhere builds one here,
        and writing to what it returns would change nothing.
        """
        return self.bids if direction == BUY else self.asks

    def volume_at(self, direction: int, price: int) -> int:
        """Resting volume at an absolute price.  Zero where no level rests."""
        return self.levels_map(direction).get(price, 0)

    def set_volume(self, direction: int, price: int, volume: int) -> None:
        """Set the resting volume at a price.

        Zero **removes** the level: a price whose queue empties is gone from the book,
        not a level holding nothing.  Every write goes through here, so that invariant
        is stated once, and so a variant keeping an index of occupied prices can
        maintain it by overriding this one method rather than the matching loop.
        """
        levels = self.levels_map(direction)
        if volume > 0:
            levels[price] = volume
        else:
            levels.pop(price, None)

    # ---- section 3: the configuration -------------------------------------------

    def best_price(self, direction: int) -> int | None:
        """Best price on the given side: highest bid, or lowest ask.

        **This is the one method the performance ladder replaces.**  Here it is a full
        scan of the dict keys -- O(number of occupied levels), correct, and obviously
        so.  Every faster variant in this module overrides exactly this method and
        inherits the matching logic unchanged, which is the point: the ladder is
        entirely about finding the best price, not about matching.
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
        return self.volume_at(BUY, price)

    def ask_volume_at(self, price: int) -> int:
        """``V^a_t(p)``: resting sell volume at an absolute price."""
        return self.volume_at(SELL, price)

    def bid_volume(self, level: int) -> int:
        """``V^{b,i}``, volume at the ``i``-th bid level.  Zero for ``i <= 0``."""
        price = self.bid_price(level)
        return 0 if price is None or level <= 0 else self.volume_at(BUY, price)

    def ask_volume(self, level: int) -> int:
        """``V^{a,i}``, volume at the ``i``-th ask level.  Zero for ``i <= 0``."""
        price = self.ask_price(level)
        return 0 if price is None or level <= 0 else self.volume_at(SELL, price)

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
        fills: list[Fill] = []
        deltas: list[LevelDelta] = []

        # 1. The market-order part: consume while the price constraint permits.
        while remaining > 0:
            best = self.best_price(-direction)
            # pi*d <= p*d handles both sides in one expression: for a buy this is
            # "the best ask is not above my limit", for a sell "the best bid is not
            # below it".  An empty side stops the loop for the same reason a price
            # that fails the test does -- there is nothing eligible left.
            if best is None or best * direction > limit_price * direction:
                break
            resting = self.volume_at(-direction, best)
            traded = min(remaining, resting)
            remaining -= traded
            self.set_volume(-direction, best, resting - traded)
            # A fill trades at the RESTING order's price, never the incoming one.
            fills.append(Fill(price=best, size=traded, aggressor=direction))
            deltas.append(LevelDelta(side=-direction, price=best, volume=resting - traded))

        # 2. The resting part.
        rest_price = self.resting_price(limit_price, fills)
        if remaining > 0 and rest_price is not None:
            resting = self.volume_at(direction, rest_price) + remaining
            self.set_volume(direction, rest_price, resting)
            deltas.append(
                LevelDelta(side=direction, price=rest_price, volume=resting)
            )
            remaining = 0

        return SubmitResult(fills=fills, deltas=deltas, unfilled=remaining)

    @staticmethod
    def resting_price(limit_price: int, fills: list[Fill]) -> int | None:
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

        Resting at the sentinel itself is what must never happen.  A fill trades at the
        *resting* order\'s price, so a residual sitting at ``MARKET_BUY_PRICE`` would
        print later fills at ``sys.maxsize``, and one at ``MARKET_SELL_PRICE`` -- which
        is 0, indistinguishable from a real price -- would give every subsequent buyer
        free shares.
        """
        if not is_market_price(limit_price):
            return limit_price
        return fills[-1].price if fills else None

    def withdraw(self, message: Message) -> SubmitResult:
        """Remove resting volume at ``(price, direction)``, addressed by quantity.

        A quantity-addressed withdrawal is one more signed
        delta on the aggregate state, so the state does not grow.  What changes is that
        level volumes stop being monotone, the best price can now move in both
        directions, and the book can empty entirely.
        """
        resting = self.volume_at(message.direction, message.price)
        if message.size > resting and self.strict:
            raise ValueError(
                f"cannot withdraw {message.size} at price {message.price}: only "
                f"{resting} resting"
            )
        removed = min(message.size, resting)
        if removed == 0:
            return SubmitResult()
        left = resting - removed
        self.set_volume(message.direction, message.price, left)
        return SubmitResult(
            deltas=[LevelDelta(side=message.direction, price=message.price, volume=left)]
        )

    # ---- housekeeping ---------------------------------------------------------------

    def copy(self) -> "AggregateBook":
        """An independent copy of the current state.

        A snapshot tap that stores the book itself stores *the same mutable object*
        every time, so every recorded snapshot ends up equal to the final state.  This
        method exists so that the tap has something correct to call.
        """
        clone = self._empty_like()
        for direction in (BUY, SELL):
            for price, volume in self.levels_map(direction).items():
                clone.set_volume(direction, price, volume)
        return clone

    @classmethod
    def from_levels(
        cls, bids: dict[int, int], asks: dict[int, int]
    ) -> "AggregateBook":
        """Build a book from ``{price: volume}`` maps on each side.

        Goes through :meth:`set_volume` for every level, so a variant that keeps an
        index is correctly initialised.  Assigning to ``book.bids`` directly would leave
        that index empty and the book quietly wrong -- precisely the class of bug a
        cache invites.
        """
        book = cls()
        for direction, levels in ((BUY, bids), (SELL, asks)):
            for price, volume in levels.items():
                if volume <= 0:
                    raise ValueError(f"level at {price} must hold positive volume")
                book.set_volume(direction, price, volume)
        book.check_invariants()
        return book

    @classmethod
    def for_prices(
        cls, prices: "Iterable[int]", strict: bool = False
    ) -> "AggregateBook":
        """A book sized for a known range of prices.

        The dict-backed books ignore the range -- they grow as prices arrive, which is
        exactly why they need no band.  A book indexed by tick cannot, and overriding
        this is where that requirement becomes visible instead of being smuggled into
        whoever constructs one.
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
            for price, volume in self.levels_map(direction).items():
                if volume <= 0:
                    raise AssertionError(
                        f"{name} level at {price} holds {volume}: a price whose queue "
                        "empties must be removed, not kept at zero"
                    )

    def __repr__(self) -> str:
        bid, ask = self.best_bid_price, self.best_ask_price
        return (
            f"{type(self).__name__}(bid={bid}x{self.best_bid_volume}, "
            f"ask={ask}x{self.best_ask_volume}, "
            f"levels={len(self.levels_map(BUY))}/{len(self.levels_map(SELL))})"
        )


# ---------------------------------------------------------------------------------
# Axis B: the performance ladder.
#
# Matching is identical in every class below; what differs is how the best price is
# found.  The first three keep the dicts as storage and add an index beside them, and
# override `best_price` plus the `set_volume` that keeps that index in step.  Varying
# one factor is what lets a timing difference have a single cause.
#
# The last one stops varying one factor on purpose.  A real low-latency book *fuses*
# storage and index -- the volumes live in the tick-indexed array itself -- and
# TickArrayBook is that book, so the step from BitmapBook to it measures exactly the
# fusion and nothing else.
# ---------------------------------------------------------------------------------


class CachedBestBook(AggregateBook):
    """Step 2: remember the best price, and repair it when that level empties.

    The best price is read at least once by every incoming order and changes far less
    often than it is read, so cache it.  Invalidation is the whole difficulty and it has
    exactly three cases, which :meth:`_best_after` enumerates.

    The cache is **derived state**: ``_cached`` is recoverable from the levels at any
    moment, which is what :meth:`check_cache_is_consistent` asserts, and that
    recoverability is the only thing that makes a cache defensible.  Keeping it repaired
    at write time rather than at read time is what leaves :meth:`best_price` a pure
    lookup with no side effects -- a lazy variant that marked the cache stale and
    rescanned on the next read measures the same to within 1%, so the simpler shape wins.

    ``_cached`` is keyed by direction rather than held as two attributes because the
    code around it is generic in ``d``.  Timing the alternatives is a notebook exercise;
    the honest summary is that they are within a few nanoseconds of each other, so this
    is a choice about uniformity and not about speed.
    """

    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self._cached: dict[int, int | None] = {BUY: None, SELL: None}

    def set_volume(self, direction: int, price: int, volume: int) -> None:
        super().set_volume(direction, price, volume)
        self._cached[direction] = self._best_after(direction, price, volume)

    def _best_after(self, direction: int, price: int, volume: int) -> int | None:
        """What the best price becomes once this level holds ``volume``.

        Total in the three cases, so there is no fourth to forget.
        """
        best = self._cached[direction]
        # price * direction > best * direction: "better" for whichever side.
        if volume > 0 and (best is None or price * direction > best * direction):
            return price
        if volume == 0 and price == best:
            # The cached price no longer names a level and nothing local says what
            # replaces it, so this is the one case that pays for a rescan.
            return self._rescan(direction)
        # Any other change is at a price no better than the best, or leaves volume
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

    ``heapq`` is a min-heap only, so the bid side stores negated prices -- the standard
    trick, and worth meeting once.  Removing a price from the middle of a heap is not
    supported, so we do not try: entries are left behind and discarded when they reach
    the top and turn out to name an empty level.  **The top of the heap may be stale;
    pop until it is not.**

    The cost of lazy deletion is that the heap grows with every level that is ever
    created, so a long run wants periodic compaction.  :meth:`compact` does that, and
    the fact that it is needed at all is the honest half of the technique.
    """

    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self._heaps: dict[int, list[int]] = {BUY: [], SELL: []}

    def set_volume(self, direction: int, price: int, volume: int) -> None:
        super().set_volume(direction, price, volume)
        if volume > 0:
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

    def __init__(self, origin: int = 0, strict: bool = False):
        super().__init__(strict)
        self.origin = origin
        self._bits: dict[int, int] = {BUY: 0, SELL: 0}

    @classmethod
    def for_prices(cls, prices: "Iterable[int]", strict: bool = False) -> "BitmapBook":
        # Only to keep the integer narrow: the bitmap has no upper edge to fall off.
        return cls(origin=min(prices) - cls.BAND_MARGIN, strict=strict)

    def _empty_like(self) -> "BitmapBook":
        return type(self)(origin=self.origin, strict=self.strict)

    def set_volume(self, direction: int, price: int, volume: int) -> None:
        super().set_volume(direction, price, volume)
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


class TickArrayBook(AggregateBook):
    """Step 5: storage and index fused -- the shape of a real low-latency book.

    Every class above keeps the volumes in a dict and puts an index beside it.  A
    production book does not: prices already live on an integer grid, so the tick *is*
    the array subscript, and the volume is read where the occupancy bit is set.  There
    is no dict here at all, and :meth:`levels_map` builds one only when something asks
    to inspect the book.

    What that buys is one indirection instead of two, and contiguous memory -- which in
    C is the whole point, and in CPython is a claim to measure rather than believe,
    since the interpreter's own overhead may be larger than the difference.

    What it costs is stated in the constructor: a band, fixed in advance, occupied or
    not.  A lookup table costs the whole table, and a real venue either shifts the band
    as the price drifts or falls back to a sorted map for a range too wide and too
    sparse to index.  Neither is worth building before the simple version is measured.

    Deliberately a plain ``list`` and not a numpy array: this access pattern is one
    element at a time, which is where numpy is *slower* than a list, and the trade it
    offers here is space rather than speed.
    """

    def __init__(self, origin: int = 0, width: int = 4096, strict: bool = False):
        super().__init__(strict)
        self.origin = origin
        self.width = width
        self._volumes: dict[int, list[int]] = {
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
        low, high = min(prices), max(prices)
        return cls(
            origin=low - cls.BAND_MARGIN,
            width=high - low + 2 * cls.BAND_MARGIN,
            strict=strict,
        )

    def _empty_like(self) -> "TickArrayBook":
        return type(self)(origin=self.origin, width=self.width, strict=self.strict)

    def volume_at(self, direction: int, price: int) -> int:
        """Zero outside the band, rather than an error.

        Reads run off the edge in ordinary use -- ``levels(SELL, 10)`` walks ten grid
        positions up from the best ask whether or not the band reaches that far -- and
        a grid position outside the band holds nothing, which is a true answer.  Writes
        are the other case, and they raise.
        """
        index = price - self.origin
        if not 0 <= index < self.width:
            return 0
        return self._volumes[direction][index]

    def set_volume(self, direction: int, price: int, volume: int) -> None:
        index = price - self.origin
        if not 0 <= index < self.width:
            raise ValueError(
                f"price {price} is outside the band "
                f"[{self.origin}, {self.origin + self.width}); a real book would shift "
                "the band or fall back to a sorted map"
            )
        self._volumes[direction][index] = volume
        bit = 1 << index
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

    def levels_map(self, direction: int) -> dict[int, int]:
        """Built on demand, by walking the occupancy bits from the bottom up.

        Nothing on the hot path calls this -- matching reads single volumes and the
        best price -- so the cost lands only where a caller genuinely wants the whole
        book, which is inspection, comparison and drawing.
        """
        volumes = self._volumes[direction]
        bits = self._bits[direction]
        levels: dict[int, int] = {}
        while bits:
            lowest = bits & -bits
            index = lowest.bit_length() - 1
            levels[self.origin + index] = volumes[index]
            bits ^= lowest
        return levels

    def copy(self) -> "TickArrayBook":
        clone = self._empty_like()
        clone._volumes = {
            direction: volumes.copy() for direction, volumes in self._volumes.items()
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
