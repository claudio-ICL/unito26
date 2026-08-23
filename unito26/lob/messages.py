"""The order tuple, the message stream, and the tick grid.

Notation follows ``documentation/order-driven-markets-notation.md``: an order is the
4-tuple ``(t, q, p, d)`` -- time, size, price, direction -- *in that order*, with
``d = +1`` for a buy and ``d = -1`` for a sell.  ``d`` is an ``int``, never a string
and never a bool, because the single expression ``p * d`` collapses both sides of the
book into one comparison and that is the trick the whole matching engine rests on.

Prices are **integer counts of ticks** everywhere inside the package.  Conversion to
and from currency happens once, at the boundary, in :class:`TickGrid`.  Floats on a
tick grid produce prices that are not multiples of the tick and levels that fail to
compare equal, which is a bug that hides for a long time before it surfaces.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntEnum

__all__ = [
    "BUY",
    "SELL",
    "MARKET_BUY_PRICE",
    "MARKET_SELL_PRICE",
    "MessageType",
    "Message",
    "Fill",
    "LevelDelta",
    "TickGrid",
    "is_market_price",
    "market_order",
    "limit_order",
    "withdrawal",
]

BUY = 1
SELL = -1

#: Sentinel prices for genuine market orders, following section 6 of the notation:
#: a sell at ``p = 0`` and a buy at ``p = infinity`` are the price specifications that
#: guarantee immediate execution.  Since prices are integers here, "infinity" is the
#: largest representable one.  Neither is a tradeable price, and the engine must never
#: let an unfilled remainder rest at either.
MARKET_SELL_PRICE = 0
MARKET_BUY_PRICE = sys.maxsize


def is_market_price(price: int) -> bool:
    """True for the two sentinel prices that mark a genuine market order."""
    return price == MARKET_SELL_PRICE or price == MARKET_BUY_PRICE


class MessageType(IntEnum):
    """What a message asks the book to do.

    There are deliberately only two.  A marketable limit order is *not* a third kind:
    by the decomposition of section 6, every incoming order is processed as
    market-part-then-resting-part along one code path, so "aggressive" and "passive"
    are outcomes rather than categories.
    """

    SUBMIT = 1
    """A new limit order, possibly marketable, possibly a market order by sentinel."""

    WITHDRAW = 2
    """Remove resting volume, addressed by ``(price, size, direction)``.

    This is the *quantity-addressed* form: it names an amount at a price, not an
    order, so the aggregate book can apply it as one signed delta.  Withdrawal
    addressed by order identity belongs to the order-level book instead.
    """


@dataclass(frozen=True, slots=True)
class Message:
    """One element of the order stream: the tuple ``(t, q, p, d)`` plus what to do.

    Immutable and slotted.  Immutability matters because the stream is replayed, often
    more than once, and a mutable message that the engine edited in passing would make
    the second replay differ from the first.
    """

    time: float
    size: int
    price: int
    direction: int
    kind: MessageType = MessageType.SUBMIT

    def __post_init__(self) -> None:
        if self.direction not in (BUY, SELL):
            raise ValueError(f"direction must be +1 (buy) or -1 (sell), got {self.direction!r}")
        if self.size < 0:
            raise ValueError(f"size must be non-negative, got {self.size}")
        if self.price < 0:
            raise ValueError(f"price must be non-negative, got {self.price}")


@dataclass(frozen=True, slots=True)
class Fill:
    """One trade: ``size`` shares at the **resting** order's price.

    A fill never prints at the incoming order's limit price.  Getting this wrong
    flatters every execution backtest ever written, which is why it has its own type
    rather than being a bare tuple.
    """

    price: int
    size: int
    aggressor: int
    """Direction of the *incoming* order.  The resting side is ``-aggressor``."""


@dataclass(frozen=True, slots=True)
class LevelDelta:
    """A change to one price level: the book's own incremental update.

    ``volume`` is the **new absolute volume** at that price, not a signed change, and
    ``0`` means the level is now gone.  Absolute volumes are idempotent: a lost or
    duplicated update is corrected by the next update at the same price, whereas a
    signed change needs a perfect gapless sequence to stay correct.  Real feeds send
    absolute size per level for exactly this reason.

    Keyed by ``price``, never by level index -- an index-based delta breaks the instant
    the best price moves, because every index shifts.
    """

    side: int
    price: int
    volume: int


@dataclass(frozen=True, slots=True)
class TickGrid:
    """Conversion between currency prices and integer tick counts.

    The only place in the package where a price is a float.  Everything inward of this
    boundary counts ticks.
    """

    tick_size: float

    def __post_init__(self) -> None:
        if self.tick_size <= 0:
            raise ValueError(f"tick_size must be positive, got {self.tick_size}")

    def to_ticks(self, price: float, *, tolerance: float = 1e-9) -> int:
        """Currency price to tick count, refusing prices off the grid.

        ``round`` rather than ``int`` because ``10.02 / 0.01`` is ``1001.9999...`` in
        binary floating point; truncating would silently lose a tick.  The tolerance
        check is what turns a rounding convenience into a boundary that rejects bad
        input instead of quietly relocating it.
        """
        exact = price / self.tick_size
        ticks = round(exact)
        if abs(exact - ticks) > tolerance:
            raise ValueError(
                f"price {price!r} is not a multiple of tick size {self.tick_size!r}"
            )
        return int(ticks)

    def to_price(self, ticks: int) -> float:
        """Tick count back to a currency price, for display and PnL."""
        return ticks * self.tick_size


def limit_order(time: float, size: int, price: int, direction: int) -> Message:
    """A limit order ``(t, q, p, d)`` with ``p`` in ticks."""
    return Message(time, size, price, direction, MessageType.SUBMIT)


def market_order(time: float, size: int, direction: int) -> Message:
    """A genuine market order: the limit order carrying the sentinel price of section 6."""
    price = MARKET_BUY_PRICE if direction == BUY else MARKET_SELL_PRICE
    return Message(time, size, price, direction, MessageType.SUBMIT)


def withdrawal(time: float, size: int, price: int, direction: int) -> Message:
    """Remove ``size`` shares of resting volume at ``price`` on side ``direction``."""
    return Message(time, size, price, direction, MessageType.WITHDRAW)
