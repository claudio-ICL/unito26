"""The order tuple, the message stream, and the tick grid.

Notation follows ``documentation/order-driven-markets-notation.md``: an order is the
4-tuple ``(t, q, p, d)`` -- time, size, price, direction -- *in that order*, with
``d = +1`` for a buy and ``d = -1`` for a sell.  ``d`` is an ``int``, never a string
and never a bool, because the expression ``p * d`` collapses both sides of the book into
one comparison, on which the matching engine rests.

Prices are **integer counts of ticks** everywhere inside the package.  Conversion to
and from currency happens once, at the boundary, in :class:`TickGrid`.  Floats on a
tick grid produce prices that are not multiples of the tick and levels that fail to
compare equal, which is a bug that hides for a long time before it surfaces.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntEnum
from typing import NewType

__all__ = [
    "BUY",
    "SELL",
    "GridDepth",
    "ReportedDepth",
    "SweepSize",
    "PriceUnit",
    "Window",
    "Horizon",
    "Decay",
    "BranchingRatio",
    "TICK_TOLERANCE",
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

#: A count of *grid* positions from a touch, in the sense of section 3: level ``i`` is at
#: ``P^b - (i-1) tau`` whether or not anything rests there.  This is the ``n`` of ``I^n``.
GridDepth = NewType("GridDepth", int)

#: A count of *occupied* levels, in the sense LOBSTER means: level ``i`` is the ``i``-th
#: price carrying size, however far from the touch it sits.
#:
#: The two coincide only on a book with no holes.  They are separate types because the
#: alternative is three adjacent ``int`` arguments and a silent swap.
ReportedDepth = NewType("ReportedDepth", int)

#: A number of shares a hypothetical market order asks for, in the sense of the sweep cost
#: of section 4.  Counts shares where the two above count levels, so it sits beside them
#: rather than among them.
#:
#: Like them it is a ``NewType``: it separates a share count from a level count for a type
#: checker and enforces nothing at run time.  A size that is not a positive number of shares
#: is refused where the walk begins, in ``unito26.lob.orderbook``.
SweepSize = NewType("SweepSize", int)

#: How many of a market-data file's price units make one tick.  LOBSTER quotes dollars
#: times 10000, so a one-cent tick is 100 of them.
#:
#: A fourth ``NewType`` beside the three above, and for the same reason: it is an ``int``
#: that sits next to other ``int``s in a signature and means something else entirely.
#: Getting it wrong does not fail -- it rescales every price the session reports.
PriceUnit = NewType("PriceUnit", int)

#: The lookback of a backward statistic and the reach of a forward one, both in seconds.
#: They are the ``w`` and the ``h`` of ``OFI_{t,w}`` and of ``P^m_{t+h} - P^m_t``.
#:
#: Two floats appearing together in one signature is exactly the swap the ``NewType``s
#: above exist to prevent, and the house rule forbids forcing keywords instead.
Window = NewType("Window", float)
Horizon = NewType("Horizon", float)

#: The two scalars of an exponential-kernel Hawkes specification: the common decay rate
#: ``beta``, in inverse seconds, and the spectral radius ``rho`` of ``Gamma = A / beta``.
#:
#: A construction that rescales a shape to a target branching ratio takes both, and they
#: are floats of very different meaning: one is a rate, the other a dimensionless number
#: that must lie below 1.
Decay = NewType("Decay", float)
BranchingRatio = NewType("BranchingRatio", float)

#: How far off the grid a currency price may sit before :meth:`TickGrid.to_ticks` rejects
#: it.  A property of binary floating point, not a per-call choice.
TICK_TOLERANCE = 1e-9

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

    There are two.  A marketable limit order is not a third kind: by the decomposition
    of section 6, every incoming order is processed as market-part-then-resting-part
    along one code path, so "aggressive" and "passive" are outcomes rather than
    categories.
    """

    SUBMIT = 1
    """A new limit order, possibly marketable, possibly a market order by sentinel."""

    WITHDRAW = 2
    """Remove resting size, addressed by ``(price, size, direction)``.

    This is the *quantity-addressed* form: it names an amount at a price, not an
    order, so the aggregate book can apply it as one signed delta.  Withdrawal
    addressed by order identity belongs to the order-level book instead.
    """


@dataclass(frozen=True, slots=True)
class Message:
    """One element of the order stream: the tuple ``(t, q, p, d)`` plus what to do.

    Immutable and slotted.  The stream is replayed, often more than once, and a mutable
    message edited in passing would make the second replay differ from the first.
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

    A fill never prints at the incoming order's limit price.  Using the incoming price
    overstates the quality of every execution measured against it, which is why this has
    its own type rather than being a bare tuple.
    """

    price: int
    size: int
    aggressor: int
    """Direction of the *incoming* order.  The resting side is ``-aggressor``."""


@dataclass(frozen=True, slots=True)
class LevelDelta:
    """A change to one price level: the book's own incremental update.

    ``resting`` is the **new absolute size** at that price, not a signed change, and
    ``0`` means the level is now gone.  Absolute sizes are idempotent: a lost or
    duplicated update is corrected by the next update at the same price, whereas a
    signed change needs a perfect gapless sequence to stay correct.  Real feeds send
    absolute size per level for exactly this reason.

    Keyed by ``price``, never by level index -- an index-based delta breaks the instant
    the best price moves, because every index shifts.
    """

    side: int
    price: int
    resting: int


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

    def to_ticks(self, price: float) -> int:
        """Currency price to tick count, refusing prices off the grid.

        ``round`` rather than ``int`` because ``10.02 / 0.01`` is ``1001.9999...`` in
        binary floating point, and truncating would lose a tick.  The tolerance check
        rejects a price genuinely off the grid rather than relocating it to the nearest
        one.
        """
        exact = price / self.tick_size
        ticks = round(exact)
        if abs(exact - ticks) > TICK_TOLERANCE:
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
    """Remove ``size`` shares of resting size at ``price`` on side ``direction``."""
    return Message(time, size, price, direction, MessageType.WITHDRAW)
