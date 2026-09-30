"""The idealised book of section 1.4, made real.

Under Assumption ``assumption.idealisedBook`` of the notes, every event acts at the touch
of its side, no order reaches past the quote it acts on, every queue behind a touch holds
``Sbar`` and a touch holds at most ``Sbar``.  Then the change of the mid-price over a
window is ``tau / (2 Sbar)`` times the order flow imbalance, plus a residual of at most a
tick.

:class:`IdealisedFlow` turns the events of a six-type Hawkes process into orders that keep
the assumption true after every message, and leaves the matching to the ordinary book.  So
the statistics a session records of it -- ``e_n``, the imbalance, the mid-price -- are the
package's own, and the identity of the notes can be checked on them to the last digit.
"""

from __future__ import annotations

from typing import Iterator, NewType

from unito26.lob.hawkes import ExponentialHawkes
from unito26.lob.messages import BUY, SELL, GridDepth, Message, limit_order, withdrawal
from unito26.lob.orderbook import AggregateBook
from unito26.lob.simulate import EventJournal, EventType

__all__ = ["UniformDepth", "AssumptionBreach", "idealised_book", "IdealisedFlow"]

#: ``Sbar``: the size of every queue behind a touch, and the most a touch may hold.  A
#: ``NewType`` because it is a count of shares standing beside a count of levels.
UniformDepth = NewType("UniformDepth", int)


class AssumptionBreach(RuntimeError):
    """The next event cannot be placed without breaking the assumption."""


def idealised_book(
    uniform_depth: UniformDepth, touches: dict[int, tuple[int, int]], levels: GridDepth
) -> AggregateBook:
    """A book satisfying the assumption, from its two touches.

    ``touches`` maps each direction to the price of its touch and the size resting there,
    between 1 and ``uniform_depth``.  Each side holds ``levels`` levels, the touch the
    first of them, one on every tick with no gap, and every level behind the touch holds
    ``uniform_depth``.
    """
    (bid, bid_size), (ask, ask_size) = touches[BUY], touches[SELL]
    if bid >= ask:
        raise ValueError(f"the best bid {bid} must lie below the best ask {ask}")
    if levels < 1:
        raise ValueError(f"a side holds at least its touch, got {levels} levels")
    if not (1 <= bid_size <= uniform_depth and 1 <= ask_size <= uniform_depth):
        raise ValueError(
            f"a touch holds between 1 and {uniform_depth} shares, "
            f"got {bid_size} and {ask_size}"
        )
    bids = {bid: bid_size} | {bid - k: uniform_depth for k in range(1, levels)}
    asks = {ask: ask_size} | {ask + k: uniform_depth for k in range(1, levels)}
    return AggregateBook.from_levels(bids, asks)


class IdealisedFlow:
    """Hawkes events of the six types, placed as orders of one share at the touches.

    * a market order is a submission of one share at the opposite touch;
    * a limit order joins its touch, or opens one tick inside it when the touch holds
      ``Sbar``;
    * a withdrawal takes one share from its touch.

    Sizes are units because part *ii.* of the assumption needs them: an order of two
    shares can overshoot the cap, or reach past a touch that holds one.  Nothing is drawn
    beyond the events themselves.

    An event that cannot be placed raises :class:`AssumptionBreach` rather than being
    moved or dropped: a limit order that would open inside a spread of one tick, and a
    market order or a withdrawal that would empty a side.  The assumption cannot hold for
    ever -- a flow that leans one way closes the spread or empties a side in the end -- so
    a stream runs from a wide spread, over a horizon short against the time that takes.
    Usage is the fold of :class:`unito26.lob.simulate.OrderFlowSimulator`::

        for message in flow.stream(book, horizon, journal=None):
            book.apply(message, record=False)
    """

    def __init__(self, hawkes: ExponentialHawkes, uniform_depth: UniformDepth):
        if hawkes.params.dimension != len(EventType):
            raise ValueError(
                f"the flow has {len(EventType)} types and the process "
                f"{hawkes.params.dimension}"
            )
        self.hawkes = hawkes
        self.uniform_depth = uniform_depth

    def stream(
        self, book: AggregateBook, horizon: float, journal: EventJournal | None
    ) -> Iterator[Message]:
        """Yield messages until ``horizon``, reading ``book`` as it currently stands.

        ``horizon`` is absolute, as it is for the Hawkes process behind the flow.  Every
        event becomes a message, so a journal records none as dropped.  The book is
        checked against the assumption before the first message, since the flow keeps it
        true but cannot make it so.
        """
        self._check(book)
        for time, index in self.hawkes.events(horizon):
            message = self._place(book, EventType(index), time)
            if journal is not None:
                journal.times.append(time)
                journal.types.append(int(index))
                journal.emitted.append(True)
            yield message

    def _place(self, book: AggregateBook, event: EventType, time: float) -> Message:
        direction = event.direction
        if event in (EventType.MARKET_BUY, EventType.MARKET_SELL):
            opposite = self._consumable_touch(book, -direction, time)
            return limit_order(time, 1, opposite, direction)
        if event in (EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL):
            own = self._consumable_touch(book, direction, time)
            return withdrawal(time, 1, own, direction)
        touch = book.best_price(direction)
        if book.size_at(direction, touch) < self.uniform_depth:
            return limit_order(time, 1, touch, direction)
        inside = touch + direction
        if inside == book.best_price(-direction):
            raise AssumptionBreach(
                f"at {time:.6f} s a limit order would open inside a spread of one tick"
            )
        return limit_order(time, 1, inside, direction)

    def _check(self, book: AggregateBook) -> None:
        for direction, side in ((BUY, "bid"), (SELL, "ask")):
            levels = book.levels_map(direction)
            if not levels:
                raise AssumptionBreach(f"the {side} side is empty")
            prices = sorted(levels, reverse=direction == BUY)
            touch, behind = prices[0], prices[1:]
            if not 1 <= levels[touch] <= self.uniform_depth:
                raise AssumptionBreach(
                    f"the {side} touch holds {levels[touch]}, "
                    f"outside 1 to {self.uniform_depth}"
                )
            contiguous = behind == [touch - direction * k for k in range(1, len(prices))]
            if not contiguous or any(levels[price] != self.uniform_depth for price in behind):
                raise AssumptionBreach(
                    f"the {side} side is not {self.uniform_depth} on every tick behind "
                    "its touch"
                )

    @staticmethod
    def _consumable_touch(book: AggregateBook, direction: int, time: float) -> int:
        """The touch of ``direction``, provided taking a share from it leaves a touch.

        Behind a touch the queues are contiguous, so a side is about to empty exactly when
        its touch holds one share and the tick behind it holds none.
        """
        touch = book.best_price(direction)
        behind = book.size_at(direction, touch - direction)
        if book.size_at(direction, touch) == 1 and behind == 0:
            side = "bid" if direction == BUY else "ask"
            raise AssumptionBreach(f"at {time:.6f} s the {side} side would empty")
        return touch

