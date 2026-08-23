"""Synthetic order flow: from Hawkes event types to actual orders.

:mod:`unito26.lob.hawkes` decides *when* something happens and *what kind* of thing it
is.  This module decides *what order* that is -- the ``(q, p, d)`` completing the
``(t, q, p, d)`` of section 1 -- and it needs the book to do so, because a price is
quoted relative to the touch and a withdrawal must name volume that actually rests.

The two layers are kept apart on purpose.  The Hawkes layer is pure point process and
is tested as such; the mark layer is where the book enters.  One honest consequence,
which belongs in the notes rather than buried here: because a withdrawal on an empty
side is dropped, the *realised* withdrawal process is no longer exactly Hawkes.  It is
a state-dependent thinning of one.  The extension that removes the caveat -- an
intensity proportional to resting volume, after Cont, Stoikov and Talreja -- also
destroys the clean separation, which is why it is not the starting point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator

import numpy as np

from unito26.lob.hawkes import ExponentialHawkes, HawkesParams
from unito26.lob.messages import BUY, SELL, Message, limit_order, market_order, withdrawal
from unito26.lob.orderbook import AggregateBook

__all__ = ["EventType", "MarkParams", "default_flow_params", "OrderFlowSimulator"]


class EventType(IntEnum):
    """The six types of order-book event, and the Hawkes coordinate of each."""

    MARKET_BUY = 0
    MARKET_SELL = 1
    LIMIT_BUY = 2
    LIMIT_SELL = 3
    WITHDRAW_BUY = 4
    WITHDRAW_SELL = 5

    @property
    def direction(self) -> int:
        return BUY if self % 2 == 0 else SELL


#: The submission-only restriction, for rungs L1 and L2 of the ladder.
SUBMISSION_TYPES = (
    EventType.MARKET_BUY,
    EventType.MARKET_SELL,
    EventType.LIMIT_BUY,
    EventType.LIMIT_SELL,
)


@dataclass(frozen=True, slots=True)
class MarkParams:
    """How an event type becomes an order.

    Attributes
    ----------
    depth_decay
        Parameter of the geometric distribution of price offsets.  Higher means orders
        cluster more tightly at the touch.
    mean_log_size, sigma_log_size
        Lognormal order size before rounding.
    lot
        Sizes are rounded to a multiple of this.  Real order sizes clump at round lots,
        and a simulator without that produces unrealistically smooth queues.
    round_lot_probability
        Probability that a size is instead drawn from ``round_lots``.
    round_lots
        The sizes traders actually type.
    """

    depth_decay: float = 0.45
    mean_log_size: float = 4.0
    sigma_log_size: float = 0.8
    lot: int = 10
    round_lot_probability: float = 0.35
    round_lots: tuple[int, ...] = (100, 200, 500, 1000)


def default_flow_params(
    decay: float = 60.0, target_branching_ratio: float = 0.8
) -> HawkesParams:
    """A six-type flow with the empirically documented asymmetry.

    ``excitation[i, j]`` is "type *j* excites type *i*".  The structure encodes three
    things that calibrations on real data agree about:

    * **market orders excite the limit-order flow heavily** (rows for LIMIT_*, columns
      for MARKET_*), as liquidity providers replenish what was just consumed;
    * **limit orders barely excite the market-order flow** (rows for MARKET_*, columns
      for LIMIT_*) -- the relation is strikingly one-way;
    * **market buys excite sell-side withdrawals**, which is liquidity being pulled
      ahead of an informed buyer.  That is the mechanism behind the adverse-selection
      term of section 7, and simulating it is what lets students *see* it.

    Self-excitation on every diagonal carries the order-splitting story: a large parent
    order arrives as a burst of children.

    The matrix is written by hand for its *shape* and then rescaled to hit
    ``target_branching_ratio``.  That works because the spectral radius is homogeneous
    of degree one in the excitation: doubling every entry doubles it.  So the shape and
    the overall endogeneity are independent choices, and the default of 0.8 sits inside
    the 0.7-0.9 range that calibrations on exchange data report.
    """
    order = [
        EventType.MARKET_BUY,
        EventType.MARKET_SELL,
        EventType.LIMIT_BUY,
        EventType.LIMIT_SELL,
        EventType.WITHDRAW_BUY,
        EventType.WITHDRAW_SELL,
    ]
    baseline = np.array([0.3, 0.3, 2.0, 2.0, 1.2, 1.2])

    excitation = np.zeros((6, 6))
    for i, row in enumerate(order):
        for j, column in enumerate(order):
            same_side = row.direction == column.direction
            if row == column:
                excitation[i, j] = 18.0  # self-excitation: order splitting
            elif {row, column} <= {EventType.MARKET_BUY, EventType.MARKET_SELL}:
                excitation[i, j] = 4.0  # market orders beget market orders
            elif row in (EventType.LIMIT_BUY, EventType.LIMIT_SELL) and column in (
                EventType.MARKET_BUY,
                EventType.MARKET_SELL,
            ):
                excitation[i, j] = 20.0 if same_side else 14.0  # replenishment: strong
            elif row in (EventType.MARKET_BUY, EventType.MARKET_SELL) and column in (
                EventType.LIMIT_BUY,
                EventType.LIMIT_SELL,
            ):
                excitation[i, j] = 1.0  # the reverse direction: weak, on purpose
            elif row in (EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL) and column in (
                EventType.MARKET_BUY,
                EventType.MARKET_SELL,
            ):
                # A buy sweep makes sellers pull their quotes: adverse selection.
                excitation[i, j] = 16.0 if not same_side else 6.0
            else:
                excitation[i, j] = 2.0

    unscaled = excitation / decay
    radius = float(np.max(np.abs(np.linalg.eigvals(unscaled))))
    excitation *= target_branching_ratio / radius
    return HawkesParams(baseline=baseline, excitation=excitation, decay=decay)


class OrderFlowSimulator:
    """Turns Hawkes events into messages against a live book.

    Usage is a fold, and the coupling is deliberate::

        book = AggregateBook()
        for message in simulator.stream(book, horizon=60.0):
            book.apply(message)

    The generator computes each message *after* the driver applied the previous one, so
    it always reads the current book.  That is what makes prices relative to the touch
    and withdrawals able to name volume that is really there.
    """

    def __init__(
        self,
        params: HawkesParams | None = None,
        marks: MarkParams | None = None,
        *,
        reference_price: int = 10_000,
        rng: np.random.Generator | int | None = None,
        submissions_only: bool = False,
    ):
        self.params = params if params is not None else default_flow_params()
        self.marks = marks if marks is not None else MarkParams()
        self.reference_price = reference_price
        self.rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        self.submissions_only = submissions_only
        self._hawkes = ExponentialHawkes(self.params, rng=self.rng)

    # ---- marks ---------------------------------------------------------------

    def _size(self) -> int:
        if self.rng.random() < self.marks.round_lot_probability:
            return int(self.rng.choice(self.marks.round_lots))
        raw = self.rng.lognormal(self.marks.mean_log_size, self.marks.sigma_log_size)
        return max(self.marks.lot, int(round(raw / self.marks.lot)) * self.marks.lot)

    def _offset(self) -> int:
        """Ticks behind the reference, geometrically distributed and peaked at zero."""
        return int(self.rng.geometric(self.marks.depth_decay) - 1)

    def _limit_price(self, book: AggregateBook, direction: int) -> int:
        """Quote relative to the opposite touch, so orders may improve the spread.

        An offset of zero prices one tick inside the opposite best, which is how a
        spread narrows.  With the opposite side empty there is no touch to quote
        against, so the simulator falls back to its own reference price -- a modelling
        decision, and one worth naming rather than hiding.
        """
        opposite_best = book.best_price(-direction)
        if opposite_best is None:
            opposite_best = self.reference_price + direction
        price = opposite_best - direction * (1 + self._offset())
        return max(1, price)

    def _withdrawal(self, book: AggregateBook, direction: int, time: float) -> Message | None:
        """Pick a resting level, size-weighted, and take some of it away.

        Returns None when the side is empty: the event is dropped.  This is the
        state-dependent thinning noted in the module docstring.
        """
        levels = book.side(direction)
        if not levels:
            return None
        prices = list(levels)
        volumes = np.array([levels[price] for price in prices], dtype=float)
        price = prices[int(self.rng.choice(len(prices), p=volumes / volumes.sum()))]
        size = min(self._size(), levels[price])
        return withdrawal(time, size, price, direction)

    # ---- the stream ----------------------------------------------------------

    def stream(self, book: AggregateBook, horizon: float) -> Iterator[Message]:
        """Yield messages until ``horizon``, reading ``book`` as it currently stands."""
        for time, index in self._hawkes.events(horizon):
            event = EventType(index)
            if self.submissions_only and event not in SUBMISSION_TYPES:
                continue
            direction = event.direction

            if event in (EventType.MARKET_BUY, EventType.MARKET_SELL):
                yield market_order(time, self._size(), direction)
            elif event in (EventType.LIMIT_BUY, EventType.LIMIT_SELL):
                yield limit_order(time, self._size(), self._limit_price(book, direction), direction)
            else:
                message = self._withdrawal(book, direction, time)
                if message is not None:
                    yield message

    def warm_up(self, book: AggregateBook, horizon: float) -> AggregateBook:
        """Run the stream into the book, discarding the messages.

        A book that starts empty is unrepresentative for a while: the first orders have
        nothing to trade against.  Benchmarks and studies should start from a book that
        has been running.
        """
        for message in self.stream(book, horizon):
            book.apply(message)
        return book
