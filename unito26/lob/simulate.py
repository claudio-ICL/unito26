"""Synthetic order flow: from Hawkes event types to actual orders.

:mod:`unito26.lob.hawkes` decides *when* something happens and *what kind* of thing it
is.  This module decides *what order* that is -- the ``(q, p, d)`` completing the
``(t, q, p, d)`` of section 1 -- and it needs the book to do so, because a price is
quoted relative to the touch and a withdrawal must name size that actually rests.

The two layers are kept apart.  The Hawkes layer is a point process and is tested as
such; the mark layer is where the book enters.  One consequence: because a withdrawal on
an empty side is dropped, the realised withdrawal process is not exactly Hawkes but a
state-dependent thinning of one.  The extension that removes the caveat -- an intensity
proportional to resting size, after Cont, Stoikov and Talreja -- also removes the
separation, which is why it is not the starting point.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob.frames import FrameSerializable
from unito26.lob.hawkes import ExponentialHawkes, HawkesParams
from unito26.lob.messages import BUY, SELL, Message, limit_order, market_order, withdrawal
from unito26.lob.orderbook import AggregateBook

__all__ = ["EventType", "MarkParams", "OrderFlowSimulator"]


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


@dataclass(frozen=True, slots=True)
class MarkParams(FrameSerializable):
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
        and a simulator without that produces smoother queues than a market shows.
    """

    depth_decay: float
    mean_log_size: float
    sigma_log_size: float
    lot: int

    @classmethod
    def schema(cls) -> pa.DataFrameSchema:
        """One row.  ``DepthDecay`` is a geometric parameter, so ``1`` is admissible and
        means every order at the touch; ``0`` is not."""
        return pa.DataFrameSchema(
            {
                "DepthDecay": pa.Column(
                    float, pa.Check.in_range(0.0, 1.0, include_min=False), coerce=True
                ),
                "MeanLogSize": pa.Column(float, coerce=True),
                "SigmaLogSize": pa.Column(float, pa.Check.gt(0.0), coerce=True),
                "Lot": pa.Column("Int64", pa.Check.ge(1), coerce=True),
            },
            strict=True,
        )

    def to_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame(
            {
                "DepthDecay": [float(self.depth_decay)],
                "MeanLogSize": [float(self.mean_log_size)],
                "SigmaLogSize": [float(self.sigma_log_size)],
                "Lot": [self.lot],
            }
        )
        return self.schema().validate(frame)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "MarkParams":
        frame = cls.schema().validate(frame)
        if len(frame) != 1:
            raise ValueError(f"mark parameters are one row, got {len(frame)}")
        row = frame.iloc[0]
        return cls(
            depth_decay=float(row["DepthDecay"]),
            mean_log_size=float(row["MeanLogSize"]),
            sigma_log_size=float(row["SigmaLogSize"]),
            lot=int(row["Lot"]),
        )


class OrderFlowSimulator:
    """Turns Hawkes events into messages against a live book.

    Usage is a fold, and the coupling is deliberate::

        book = AggregateBook()
        for message in simulator.stream(book, horizon=60.0):
            book.apply(message, record=False)

    The generator computes each message *after* the driver applied the previous one, so
    it always reads the current book.  That is what makes prices relative to the touch
    and withdrawals able to name size that is really there.
    """

    def __init__(
        self,
        params: HawkesParams,
        marks: MarkParams,
        reference_price: int,
        rng: np.random.Generator | int | None = None,
    ):
        self.params = params
        self.marks = marks
        self.reference_price = reference_price
        self.rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        self._hawkes = ExponentialHawkes(self.params, rng=self.rng)

    # ---- marks ---------------------------------------------------------------

    def _size(self) -> int:
        raw = self.rng.lognormal(self.marks.mean_log_size, self.marks.sigma_log_size)
        return max(self.marks.lot, int(round(raw / self.marks.lot)) * self.marks.lot)

    def _offset(self) -> int:
        """Ticks behind the reference, geometrically distributed and peaked at zero."""
        return int(self.rng.geometric(self.marks.depth_decay) - 1)

    def _limit_price(self, book: AggregateBook, direction: int) -> int:
        """Quote relative to the opposite touch, so orders may improve the spread.

        An offset of zero prices one tick inside the opposite best, which is how a
        spread narrows.  With the opposite side empty there is no touch to quote against,
        so the simulator falls back to its own reference price; that is a modelling
        decision rather than a consequence of the notation.
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
        levels = book.levels_map(direction)
        if not levels:
            return None
        prices = list(levels)
        weights = np.array([levels[price] for price in prices], dtype=float)
        price = prices[int(self.rng.choice(len(prices), p=weights / weights.sum()))]
        size = min(self._size(), levels[price])
        return withdrawal(time, size, price, direction)

    # ---- the stream ----------------------------------------------------------

    def stream(self, book: AggregateBook, horizon: float) -> Iterator[Message]:
        """Yield messages until ``horizon``, reading ``book`` as it currently stands."""
        for time, index in self._hawkes.events(horizon):
            event = EventType(index)
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
            book.apply(message, record=False)
        return book
