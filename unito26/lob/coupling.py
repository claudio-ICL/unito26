"""The CKS placement and the geometric placement of one order flow, on the same events.

Example ``example.idealisedPlacement`` and Definition ``def.geometricPlacement`` of the
notes turn the events of a six-type Hawkes process into messages in two ways.  The first,
CKS after the stylised book of Cont, Kukanov and Stoikov, sends orders of one share to the
touches and keeps Assumption ``assumption.idealisedBook`` true, so that the identity of the
order flow imbalance is exact; the second is the flow the package simulates.  Three flows
are read on one recorded path, from one opening book:

* CKS;
* haw-1, the geometric placement with orders of one share;
* haw-q, the geometric placement with sizes of mean ``mbar``, on the opening book with
  every size multiplied by ``mbar``.

Sizes are read in units of ``mbar``, the :data:`SizeUnit`, so that haw-1 is haw-q at zero
size variance.  The object is ``chi``, the first event after which the mid-prices of CKS
and of a Hawkes flow differ, and from it the discrepancy
``D_t = P^{m,CKS}_t - P^{m,haw}_t``.  The marks are drawn independently of the path, so
the variance of ``D_t`` across paths and marks is the variance of its mean given the path
plus the mean of its variance given the path: :func:`variance_split`.

The notes assume that no side of either book empties over the horizon.  The folds here
detect the event that would empty one and stop before it.

The last section is what the notes predict of the pair, each prediction a function of the
specification and of the opening book: the touch walks of CKS and its first move, the fluid
touch of haw-1 and the time it empties, the two timescales of the parting, and the closed
form of the variance, with the two statistics of the Hawkes book it reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator, NewType

import numpy as np
import pandas as pd

from unito26.lob.hawkes import Clock, HawkesParams
from unito26.lob.idealised import AssumptionBreach, IdealisedFlow, UniformDepth, idealised_book
from unito26.lob.messages import BUY, SELL, GridDepth, Message
from unito26.lob.orderbook import AggregateBook, SubmitResult
from unito26.lob.simulate import EventType, MarkParams, OrderFlowSimulator

__all__ = [
    "SizeUnit",
    "OpeningTouch",
    "RecordedEvents",
    "Replay",
    "Mover",
    "Parting",
    "FirstMoves",
    "CoupledFlows",
    "first_price_discrepancy",
    "first_price_moves",
    "touch_walks",
    "cks_mids",
    "hawkes_mids",
    "variance_split",
    "distance_terms",
    "side_vector",
    "cks_touch_walks",
    "cks_first_move",
    "fluid_touch",
    "fluid_emptying_time",
    "diffusive_scale",
    "second_regime_rate",
    "PlacementStatistics",
    "VarianceRates",
    "closed_form_rates",
]

#: ``mbar``, the shares in one unit of size: the mean order size of a Hawkes flow, and the
#: factor by which its opening book multiplies the CKS one.  A ``NewType`` because it is a
#: count of shares standing beside ``Sbar``, a count of units.
SizeUnit = NewType("SizeUnit", int)

#: ``r(0)``, the size at the opening touch of a side over ``Sbar``, in ``(0, 1]``: where the
#: fluid touch starts.  A ``NewType`` so that it is not swapped with the scaled time.
OpeningTouch = NewType("OpeningTouch", float)


@dataclass(frozen=True, slots=True, eq=False)
class RecordedEvents:
    """A path of a Hawkes process on ``(0, horizon]``, drawn once: every event in it, in order.

    The path is data and is read by :meth:`replay`, which gives each reader a cursor of its
    own.  A cursor on the path itself would be shared, and two placements reading it would
    each receive part of the events.
    """

    times: np.ndarray
    types: np.ndarray
    params: HawkesParams
    horizon: float

    @classmethod
    def drawn(cls, process, horizon: float) -> "RecordedEvents":
        """The events of ``process`` up to ``horizon``, which is absolute as it is for the
        process.  ``process`` is anything with ``params`` and ``events(horizon)``."""
        events = list(process.events(horizon))
        return cls(
            np.array([time for time, _ in events], dtype=float),
            np.array([event for _, event in events], dtype=int),
            process.params,
            float(horizon),
        )

    def __len__(self) -> int:
        return len(self.times)

    def head(self, count: int) -> "RecordedEvents":
        """The first ``count`` events, as the path on ``(0, T_count]``."""
        horizon = float(self.times[count - 1]) if count > 0 else 0.0
        return RecordedEvents(self.times[:count], self.types[:count], self.params, horizon)

    def after(self, time: float) -> "RecordedEvents":
        """The events in ``(time, horizon]``, with the clock moved to zero at ``time``.

        The cut path continues from the state :meth:`state_after` reads at ``time``.
        """
        kept = self.times > time
        return RecordedEvents(
            self.times[kept] - time, self.types[kept], self.params, self.horizon - time
        )

    def state_after(self, time: float) -> np.ndarray:
        """``Z(time+)``, for a path drawn from the empty state."""
        past = self.times <= time
        decayed = np.exp(-self.params.decay * (time - self.times[past]))
        return np.bincount(self.types[past], decayed, minlength=self.params.dimension)

    def replay(self) -> "Replay":
        return Replay(self)


class Replay:
    """A cursor on a recorded path, read as a Hawkes process is read.

    ``events(horizon)`` takes an absolute horizon and continues where the previous call
    stopped, as ``_HawkesState.events`` does, so a warm-up followed by a run yields every
    event once.  A horizon past the recorded one is refused: the path says nothing there,
    and replaying it as silence would read a truncated path as a quiet one.
    """

    def __init__(self, recorded: RecordedEvents):
        self.recorded = recorded
        self.params = recorded.params
        self._next = 0

    def events(self, horizon: float) -> Iterator[tuple[float, int]]:
        if horizon > self.recorded.horizon:
            raise ValueError(
                f"the path is recorded to {self.recorded.horizon}, not to {horizon}"
            )
        times, types = self.recorded.times, self.recorded.types
        while self._next < len(times) and times[self._next] <= horizon:
            index = self._next
            self._next += 1
            yield float(times[index]), int(types[index])


# ---- one book and its placement ------------------------------------------------------


class _Fold:
    """A book and the stream of messages its placement sends it.

    Iterating applies each message and yields it with what :meth:`AggregateBook.apply`
    returned, so that between two steps the book holds the result of the last.
    """

    def __init__(
        self, name: str, book: AggregateBook, stream: Iterator[Message], record: bool
    ):
        self.name = name
        self.book = book
        self._stream = stream
        self._record = record

    def __iter__(self) -> Iterator[tuple[Message, SubmitResult | None]]:
        for message in self._stream:
            yield message, self.book.apply(message, self._record)

    def occupied(self) -> Iterator[tuple[Message, SubmitResult | None]]:
        """The same steps, stopped by an :class:`AssumptionBreach` naming the book at the
        first message that would leave a side of it empty.  The CKS placement refuses to
        send that message; a geometric one is applied, and not yielded."""
        try:
            for message, result in self:
                for direction, side in ((BUY, "bid"), (SELL, "ask")):
                    if not self.book.levels_map(direction):
                        raise AssumptionBreach(
                            f"at {message.time:.6f} s the {side} side empties"
                        )
                yield message, result
        except AssumptionBreach as breach:
            raise AssumptionBreach(f"{self.name} book: {breach}") from None


def _hawkes_opening(
    size_unit: SizeUnit,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
) -> AggregateBook:
    """``idealised_book(uniform_depth, touches, levels)``, every size times ``size_unit``."""
    book = idealised_book(uniform_depth, touches, levels)
    bids, asks = (
        {price: size * size_unit for price, size in book.levels_map(direction).items()}
        for direction in (BUY, SELL)
    )
    return AggregateBook.from_levels(bids, asks)


def _cks_fold(
    events: RecordedEvents,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    record: bool,
) -> _Fold:
    book = idealised_book(uniform_depth, touches, levels)
    stream = IdealisedFlow(events.replay(), uniform_depth).stream(book, events.horizon, None)
    return _Fold("CKS", book, stream, record)


def _hawkes_fold(
    events: RecordedEvents,
    marks: MarkParams,
    size_unit: SizeUnit,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    rng: np.random.Generator | int | None,
    record: bool,
) -> _Fold:
    """The geometric placement of ``events``; its reference price, read only while a side is
    empty, is the opening bid."""
    book = _hawkes_opening(size_unit, uniform_depth, touches, levels)
    simulator = OrderFlowSimulator.driven_by(events.replay(), marks, touches[BUY][0], rng)
    return _Fold("Hawkes", book, simulator.stream(book, events.horizon, None), record)


def _prices(book: AggregateBook) -> tuple[int, int]:
    return book.best_bid_price, book.best_ask_price


def _touch(book: AggregateBook) -> tuple[int, int, int, int]:
    """``(P^b, S^b, P^a, S^a)``, of a book with both sides occupied."""
    bid, ask = book.best_bid_price, book.best_ask_price
    return bid, book.size_at(BUY, bid), ask, book.size_at(SELL, ask)


# ---- the parting ----------------------------------------------------------------------


class Mover(Enum):
    """The book whose best price moved at the parting, or both, to different prices."""

    CKS = "CKS"
    HAWKES = "Haw"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class Parting:
    """``chi``: the event after which the mids of the CKS and the Hawkes book first differ.

    Before it the two books have the same best prices.  An event moves at most one best
    price of each book, and the same one when it moves both, so at ``chi`` exactly one best
    price differs: the one on ``side``.  ``moved`` says which book moved it.
    """

    event: int
    time: float
    event_type: EventType
    moved: Mover
    side: int


def _parting(
    events: RecordedEvents,
    event: int,
    before: tuple[int, int],
    cks: tuple[int, int],
    hawkes: tuple[int, int],
) -> Parting:
    """The parting at ``event``, from the best prices ``(P^b, P^a)`` the books shared before
    it and those of each after it."""
    side = BUY if cks[0] != hawkes[0] else SELL
    k = 0 if side == BUY else 1
    moved = {
        (True, False): Mover.CKS,
        (False, True): Mover.HAWKES,
        (True, True): Mover.BOTH,
    }[(cks[k] != before[k], hawkes[k] != before[k])]
    return Parting(
        event, float(events.times[event]), EventType(int(events.types[event])), moved, side
    )


# ---- the pair -------------------------------------------------------------------------


def _contributions(bid, bid_size, ask, ask_size) -> np.ndarray:
    """``e_n`` by (``eq.orderFlowContribution``), each row of the touches against the one
    before it."""
    return (
        (bid[1:] >= bid[:-1]) * bid_size[1:] - (bid[1:] <= bid[:-1]) * bid_size[:-1]
        - (ask[1:] <= ask[:-1]) * ask_size[1:] + (ask[1:] >= ask[:-1]) * ask_size[:-1]
    )


def _book_columns(prefix: str, touches: np.ndarray, unit: int) -> dict[str, np.ndarray]:
    """The columns of one book, the sizes read in units of ``unit`` shares, from
    ``(P^b, S^b, P^a, S^a)`` at the opening and after each event."""
    bid, ask = touches[:, 0], touches[:, 2]
    bid_size, ask_size = touches[:, 1] / unit, touches[:, 3] / unit
    return {
        f"{prefix}MidPrice": (bid[1:] + ask[1:]) / 2,
        f"{prefix}BidPrice1": bid[1:],
        f"{prefix}AskPrice1": ask[1:],
        f"{prefix}BidSize1": bid_size[1:],
        f"{prefix}AskSize1": ask_size[1:],
        f"{prefix}OrderFlowContribution": _contributions(bid, bid_size, ask, ask_size),
    }


def _signed_levels(book: AggregateBook, unit: int) -> dict[int, float]:
    """The whole book in units, ``+S`` at a bid price and ``-S`` at an ask price.  The book
    never crosses, so no price carries both signs."""
    asks = {price: -size / unit for price, size in book.levels_map(SELL).items()}
    return {price: size / unit for price, size in book.levels_map(BUY).items()} | asks


def _depth_frame(
    opening: dict[int, float], changes: list[tuple[int, int, float]], rows: int
) -> pd.DataFrame:
    """The whole book after each of ``rows`` events, from the opening and the signed size
    each event left at each price it changed: a row per event, a column per price."""
    prices = sorted(set(opening) | {price for _, price, _ in changes})
    column = {price: k for k, price in enumerate(prices)}
    depth = np.full((rows + 1, len(prices)), np.nan)
    depth[0] = [opening.get(price, 0.0) for price in prices]
    for event, price, size in changes:
        depth[event + 1, column[price]] = size
    frame = pd.DataFrame(depth, columns=pd.Index(prices, name="Price")).ffill().iloc[1:]
    frame.index = pd.RangeIndex(rows, name="Event")
    return frame


@dataclass(frozen=True, eq=False)
class CoupledFlows:
    """The CKS book and one Hawkes book of a path of events, folded from one opening.

    The Hawkes book opens from the CKS one with every size times ``size_unit``.  ``frame``
    has a row per event, indexed by ``Event``: ``TimeStamp`` and ``EventType``, then for
    each book after the event, under the prefixes ``CKS`` and ``Haw``, ``MidPrice``,
    ``BidPrice1`` and ``AskPrice1`` in ticks, ``BidSize1`` and ``AskSize1`` in units, and
    ``OrderFlowContribution``, ``e_n`` in units, read against the opening on the first row;
    and ``MidsDiffer``.  ``cks_depth`` and ``hawkes_depth`` are the whole books, a row per
    event and a column per price in ticks, holding the size in units at a bid price and
    minus the size at an ask price.

    The pair stops before the first event that would empty a side of either book, and
    ``breach`` holds the :class:`AssumptionBreach` naming it; it is None for a pair that
    reached the horizon.  ``events`` are the events read.
    """

    events: RecordedEvents
    size_unit: SizeUnit
    uniform_depth: UniformDepth
    touches: dict[int, tuple[int, int]]
    frame: pd.DataFrame
    cks_depth: pd.DataFrame
    hawkes_depth: pd.DataFrame
    breach: AssumptionBreach | None

    @classmethod
    def on(
        cls,
        events: RecordedEvents,
        marks: MarkParams,
        size_unit: SizeUnit,
        uniform_depth: UniformDepth,
        touches: dict[int, tuple[int, int]],
        levels: GridDepth,
        rng: np.random.Generator | int | None = None,
    ) -> "CoupledFlows":
        """Both books of ``events``, from ``idealised_book(uniform_depth, touches, levels)``.

        ``rng`` draws the marks of the Hawkes book, the CKS one drawing nothing.
        """
        folds = {
            "CKS": _cks_fold(events, uniform_depth, touches, levels, True),
            "Haw": _hawkes_fold(
                events, marks, size_unit, uniform_depth, touches, levels, rng, True
            ),
        }
        units = {"CKS": 1, "Haw": size_unit}
        touch = {prefix: [_touch(fold.book)] for prefix, fold in folds.items()}
        opening = {
            prefix: _signed_levels(fold.book, units[prefix]) for prefix, fold in folds.items()
        }
        changes = {prefix: [] for prefix in folds}
        breach = None
        try:
            for event, steps in enumerate(zip(*(fold.occupied() for fold in folds.values()))):
                for (prefix, fold), (_, result) in zip(folds.items(), steps):
                    touch[prefix].append(_touch(fold.book))
                    changes[prefix].extend(
                        (event, delta.price, delta.side * delta.resting / units[prefix])
                        for delta in result.deltas
                    )
        except AssumptionBreach as caught:
            breach = caught

        read = len(touch["CKS"]) - 1
        seen = events.head(read) if breach else events
        columns = {"TimeStamp": seen.times, "EventType": seen.types}
        for prefix in folds:
            columns |= _book_columns(
                prefix, np.array(touch[prefix], dtype=np.int64), units[prefix]
            )
        frame = pd.DataFrame(columns, index=pd.RangeIndex(read, name="Event"))
        frame["MidsDiffer"] = frame["CKSMidPrice"] != frame["HawMidPrice"]
        cks_depth, hawkes_depth = (
            _depth_frame(opening[prefix], changes[prefix], read) for prefix in folds
        )
        return cls(
            seen, size_unit, uniform_depth, touches, frame, cks_depth, hawkes_depth, breach
        )

    @property
    def first_price_discrepancy(self) -> int | None:
        """``chi``, the first event after which the mids differ, None if they do not by the
        stop."""
        differ = self.frame["MidsDiffer"].to_numpy()
        return int(np.argmax(differ)) if differ.any() else None

    @property
    def first_price_discrepancy_time(self) -> float | None:
        first = self.first_price_discrepancy
        return None if first is None else float(self.frame["TimeStamp"].iloc[first])

    @property
    def parting(self) -> Parting | None:
        """The :class:`Parting` at ``chi``, None if the mids do not differ by the stop."""
        first = self.first_price_discrepancy
        if first is None:
            return None
        prices = self.frame[
            ["CKSBidPrice1", "CKSAskPrice1", "HawBidPrice1", "HawAskPrice1"]
        ].to_numpy()
        before = (
            tuple(prices[first - 1, :2]) if first > 0
            else (self.touches[BUY][0], self.touches[SELL][0])
        )
        return _parting(
            self.events, first, before, tuple(prices[first, :2]), tuple(prices[first, 2:])
        )


# ---- folds for fans: the books alone --------------------------------------------------


def first_price_discrepancy(
    events: RecordedEvents,
    marks: MarkParams,
    size_unit: SizeUnit,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    rng: np.random.Generator | int | None = None,
) -> Parting | None:
    """``CoupledFlows.on(...).parting``, folding the two books alone and stopping at it.

    An event that would empty a side of either book before the parting raises
    :class:`AssumptionBreach`, where the pair would record it.
    """
    cks = _cks_fold(events, uniform_depth, touches, levels, False)
    hawkes = _hawkes_fold(events, marks, size_unit, uniform_depth, touches, levels, rng, False)
    before = _prices(cks.book)
    for event, _ in enumerate(zip(cks.occupied(), hawkes.occupied())):
        now, other = _prices(cks.book), _prices(hawkes.book)
        if sum(now) != sum(other):
            return _parting(events, event, before, now, other)
        before = now
    return None


def _walk(fold: _Fold, unit: int) -> tuple[list[tuple[float, float]], int | None]:
    """``(S^b, S^a)`` in units at the opening and after each event before the first that
    moves a best price, and that event, None if there is none."""
    book = fold.book
    opening = _prices(book)
    sizes = [(book.best_bid_size / unit, book.best_ask_size / unit)]
    for event, _ in enumerate(fold.occupied()):
        if _prices(book) != opening:
            return sizes, event
        sizes.append((book.best_bid_size / unit, book.best_ask_size / unit))
    return sizes, None


@dataclass(frozen=True, slots=True)
class FirstMoves:
    """``psi^CKS`` and ``psi^haw``: the first event at which each book moves a best price,
    and its time, None for a book that does not by the horizon."""

    cks: int | None
    hawkes: int | None
    cks_time: float | None
    hawkes_time: float | None


def first_price_moves(
    events: RecordedEvents,
    marks: MarkParams,
    size_unit: SizeUnit,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    rng: np.random.Generator | int | None = None,
) -> FirstMoves:
    """Each book folded alone to its first move.  The CKS placement draws nothing, so
    ``psi^CKS`` is a function of the path.  An event that would empty a side of a book
    before its move raises :class:`AssumptionBreach`."""
    _, cks = _walk(_cks_fold(events, uniform_depth, touches, levels, False), 1)
    _, hawkes = _walk(
        _hawkes_fold(events, marks, size_unit, uniform_depth, touches, levels, rng, False),
        size_unit,
    )

    def time(event: int | None) -> float | None:
        return None if event is None else float(events.times[event])

    return FirstMoves(cks, hawkes, time(cks), time(hawkes))


def touch_walks(
    events: RecordedEvents,
    marks: MarkParams,
    size_unit: SizeUnit,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    rng: np.random.Generator | int | None = None,
) -> pd.DataFrame:
    """The touch sizes of both books, in units, from the opening to the first move of each.

    Indexed by ``TimeStamp``, the opening at zero and then each event up to the later of the
    two first moves: ``CKSBidSize1``, ``CKSAskSize1``, ``HawBidSize1``, ``HawAskSize1``, NaN
    in the columns of a book from its first move on.  A book that does not move holds its
    sizes to the horizon.
    """
    walks = {
        "CKS": _walk(_cks_fold(events, uniform_depth, touches, levels, False), 1),
        "Haw": _walk(
            _hawkes_fold(events, marks, size_unit, uniform_depth, touches, levels, rng, False),
            size_unit,
        ),
    }
    rows = max(len(sizes) + (move is not None) for sizes, move in walks.values())
    columns = {}
    for prefix, (sizes, _) in walks.items():
        padded = np.full((rows, 2), np.nan)
        padded[: len(sizes)] = sizes
        columns[f"{prefix}BidSize1"], columns[f"{prefix}AskSize1"] = padded.T
    index = pd.Index(np.r_[0.0, events.times[: rows - 1]], name="TimeStamp")
    return pd.DataFrame(columns, index=index)


def _mid(book: AggregateBook) -> float:
    mid = book.mid_price
    return np.nan if mid is None else mid


def _on_clock(
    times: np.ndarray, opening: float, mids: list[float], clock: Clock
) -> np.ndarray:
    """The mid after the last of ``times`` at or before each time of ``clock``, ``opening``
    before the first of them."""
    return np.r_[opening, mids][np.searchsorted(times, clock, side="right")]


def cks_mids(
    events: RecordedEvents,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    clock: Clock,
) -> np.ndarray:
    """``P^{m,CKS}`` after the last event at or before each time of ``clock``.  It is NaN
    from the first event that would empty a side, where the CKS book stops."""
    fold = _cks_fold(events, uniform_depth, touches, levels, False)
    opening, mids = _mid(fold.book), []
    try:
        for _ in fold.occupied():
            mids.append(_mid(fold.book))
    except AssumptionBreach:
        mids.append(np.nan)
    return _on_clock(events.times[: len(mids)], opening, mids, clock)


def hawkes_mids(
    events: RecordedEvents,
    marks: MarkParams,
    size_unit: SizeUnit,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    clock: Clock,
    rng: np.random.Generator | int | None = None,
) -> np.ndarray:
    """``P^{m,haw}`` after the last event at or before each time of ``clock``, NaN while a
    side is empty.

    The fold runs on past an empty side, as the simulator does: a withdrawal from it is
    dropped, and a limit order facing it is priced against the opening bid.
    """
    fold = _hawkes_fold(events, marks, size_unit, uniform_depth, touches, levels, rng, False)
    opening, times, mids = _mid(fold.book), [], []
    for message, _ in fold:
        times.append(message.time)
        mids.append(_mid(fold.book))
    return _on_clock(np.array(times), opening, mids, clock)


def variance_split(discrepancies: np.ndarray) -> pd.DataFrame:
    """The mean of ``D_t`` and the split of its variance, at each time.

    ``discrepancies`` has shape ``(paths, mark seeds, times)``, with at least two of each:
    every path is drawn independently, and its books are placed once per mark seed.  A row
    per time:

    * ``Mean`` and its ``StandardError``, the spread of the path means over the square root
      of their number, since the paths are independent and the seeds of one path are not;
    * ``PlacementPart``, the mean across paths of the variance over seeds, which estimates
      ``E Var[D_t | path]``;
    * ``FlowPart``, the variance across paths of the mean over seeds, less ``PlacementPart``
      over the number of seeds, which estimates ``Var E[D_t | path]``;
    * ``Total``, their sum, which estimates ``Var D_t``.

    The variances divide by one less than their counts, and the mean over ``n`` seeds
    carries ``1/n`` of the placement variance, which ``FlowPart`` takes back; so the three
    estimates are unbiased.  ``FlowPart`` can come out negative on a small sample.
    """
    sample = np.asarray(discrepancies, dtype=float)
    paths, seeds = sample.shape[:2]
    means = sample.mean(axis=1)
    placement = sample.var(axis=1, ddof=1).mean(axis=0)
    flow = means.var(axis=0, ddof=1) - placement / seeds
    return pd.DataFrame(
        {
            "Mean": means.mean(axis=0),
            "StandardError": means.std(axis=0, ddof=1) / np.sqrt(paths),
            "Total": flow + placement,
            "FlowPart": flow,
            "PlacementPart": placement,
        }
    )


def _touch_rows(pair: CoupledFlows, prefix: str) -> np.ndarray:
    """``(P^b, S^b, P^a, S^a)`` of one book of ``pair``, in units, the opening first."""
    opening = np.array([[*pair.touches[BUY], *pair.touches[SELL]]], dtype=float)
    columns = [f"{prefix}{name}" for name in ("BidPrice1", "BidSize1", "AskPrice1", "AskSize1")]
    return np.vstack([opening, pair.frame[columns].to_numpy(dtype=float)])


def _moves(touches: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Per event, from ``(P^b, S^b, P^a, S^a)`` with the opening first: the signed ticks the
    best bid moved and the size at the outer of its two values, then the same of the best
    ask.  The outer value is the one further from the other side, and a price that did not
    move has an outer size of zero."""
    bid, bid_size, ask, ask_size = touches.T
    move_bid, move_ask = np.diff(bid), np.diff(ask)
    outer_bid = np.where(move_bid > 0, bid_size[:-1], np.where(move_bid < 0, bid_size[1:], 0.0))
    outer_ask = np.where(move_ask > 0, ask_size[1:], np.where(move_ask < 0, ask_size[:-1], 0.0))
    return move_bid, outer_bid, move_ask, outer_ask


def _depth_mismatch(touches: np.ndarray, uniform_depth: UniformDepth) -> np.ndarray:
    """Per event, the outer size of each best price that moved, less ``Sbar`` per tick
    moved, signed by the move."""
    move_bid, outer_bid, move_ask, outer_ask = _moves(touches)
    return (
        np.sign(move_bid) * (outer_bid - uniform_depth * np.abs(move_bid))
        + np.sign(move_ask) * (outer_ask - uniform_depth * np.abs(move_ask))
    )


def distance_terms(pair: CoupledFlows) -> pd.DataFrame:
    """``2 Sbar D`` after each event, in units times ticks, and its three terms.

    For any book with both sides occupied, ``e_n`` is the change of ``S^b - S^a``, plus
    ``2 Sbar`` times the change of the mid, plus, for each best price that moved, the size
    at the outer of its two values less ``Sbar`` per tick moved, signed by the move.  Summed
    from the opening and differenced across the two books, which open alike in units,

        ``Distance = ImbalanceMismatch - TouchSizeMismatch - DepthMismatch``,

    each term CKS less Hawkes: ``ImbalanceMismatch`` of the order flow imbalance since the
    opening, ``TouchSizeMismatch`` of ``S^b - S^a``, and ``DepthMismatch`` of the sums of the
    last term.  ``CKSDepthMismatch`` is the CKS sum alone.  Every move of a CKS best price is
    one tick onto or off a queue of ``Sbar``, so it is zero; that is Proposition
    ``prop.idealisedUpdate``.
    """
    frame = pair.frame
    imbalance, sizes, depth = {}, {}, {}
    for prefix in ("CKS", "Haw"):
        touches = _touch_rows(pair, prefix)
        imbalance[prefix] = np.cumsum(frame[f"{prefix}OrderFlowContribution"].to_numpy())
        sizes[prefix] = touches[1:, 1] - touches[1:, 3]
        depth[prefix] = np.cumsum(_depth_mismatch(touches, pair.uniform_depth))
    return pd.DataFrame(
        {
            "TimeStamp": frame["TimeStamp"].to_numpy(),
            "Distance": 2 * pair.uniform_depth * (
                frame["CKSMidPrice"] - frame["HawMidPrice"]
            ).to_numpy(),
            "ImbalanceMismatch": imbalance["CKS"] - imbalance["Haw"],
            "TouchSizeMismatch": sizes["CKS"] - sizes["Haw"],
            "DepthMismatch": depth["CKS"] - depth["Haw"],
            "CKSDepthMismatch": depth["CKS"],
        },
        index=frame.index,
    )


# ---- what the notes predict -----------------------------------------------------------

_SIDE_CHANGES = {
    BUY: {EventType.LIMIT_BUY: 1.0, EventType.MARKET_SELL: -1.0, EventType.WITHDRAW_BUY: -1.0},
    SELL: {EventType.LIMIT_SELL: 1.0, EventType.MARKET_BUY: -1.0, EventType.WITHDRAW_SELL: -1.0},
}


def side_vector(direction: int) -> np.ndarray:
    """``varpi^b`` for ``BUY``, ``varpi^a`` for ``SELL``: by type, the shares an event of one
    share adds to the side, if it rests there in full, or takes from it.

    A limit order of the side adds one; a market order of the other direction and a
    withdrawal from the side take one.  ``varpi^b - varpi^a`` is the pressure ``varpi``.
    """
    vector = np.zeros(len(EventType))
    for event, change in _SIDE_CHANGES[direction].items():
        vector[event] = change
    return vector


def _pressure() -> np.ndarray:
    return np.array([event.pressure for event in EventType], dtype=float)


def _side_rates(params: HawkesParams) -> tuple[float, float, float]:
    """``(lambda*_2, lambda*_3, lambda*_5)``, the types counted from one as in the notes: the
    stationary rates of the market orders that take from the bid, of the limit orders that
    join it, and of the withdrawals from it.  Under direction symmetry the ask's are the
    same."""
    stationary = params.stationary_intensity()
    return (
        float(stationary[EventType.MARKET_SELL]),
        float(stationary[EventType.LIMIT_BUY]),
        float(stationary[EventType.WITHDRAW_BUY]),
    )


def _cks_walks(
    events: RecordedEvents, uniform_depth: UniformDepth, touches: dict[int, tuple[int, int]]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``Upsilon^b``, ``Upsilon^a`` and their running maximum floored at ``Sbar``, at the
    opening and after each event."""
    walks = [
        touches[direction][1] + np.r_[0.0, np.cumsum(side_vector(direction)[events.types])]
        for direction in (BUY, SELL)
    ]
    maximum = np.maximum(uniform_depth, np.maximum.accumulate(np.maximum(*walks)))
    return walks[0], walks[1], maximum


def cks_touch_walks(
    events: RecordedEvents, uniform_depth: UniformDepth, touches: dict[int, tuple[int, int]]
) -> pd.DataFrame:
    """The touch walks of the CKS book, and the touches they give before its first move.

    ``Upsilon^b = S^b_0 + (varpi^b)' N`` and ``Upsilon^a = S^a_0 + (varpi^a)' N`` count what
    arrives at each touch of the opening book, whose sizes ``touches`` gives.  A limit order
    at a full touch trades a share at the opposite one instead of joining its own, and the
    number of those is the running maximum of the two walks, floored at ``Sbar``, less
    ``Sbar``.  So before the first move each CKS touch is its walk less that number
    (Proposition ``prop.cksTouchWalks``): the cap couples the two sides.

    Indexed by ``TimeStamp``, the opening at zero and then each event up to ``psi^CKS``
    included, or to the horizon: ``BidTouchWalk``, ``AskTouchWalk``, ``RunningMaximum``,
    ``CKSBidSize1`` and ``CKSAskSize1``.  On the row of ``psi^CKS`` one touch reads zero.
    """
    bid, ask, maximum = _cks_walks(events, uniform_depth, touches)
    move = cks_first_move(events, uniform_depth, touches)
    rows = len(bid) if move is None else move + 2
    frame = pd.DataFrame(
        {
            "BidTouchWalk": bid,
            "AskTouchWalk": ask,
            "RunningMaximum": maximum,
            "CKSBidSize1": bid - (maximum - uniform_depth),
            "CKSAskSize1": ask - (maximum - uniform_depth),
        },
        index=pd.Index(np.r_[0.0, events.times], name="TimeStamp"),
    )
    return frame.iloc[:rows]


def cks_first_move(
    events: RecordedEvents, uniform_depth: UniformDepth, touches: dict[int, tuple[int, int]]
) -> int | None:
    """``psi^CKS`` from the counts alone: the first event after which one touch walk lies
    ``Sbar`` below the running maximum of both, None if none does by the horizon.

    It is the first event at which the CKS book, opened from ``touches``, moves a best
    price, and it is computed without folding a book.
    """
    bid, ask, maximum = _cks_walks(events, uniform_depth, touches)
    emptied = maximum - np.minimum(bid, ask) >= uniform_depth
    return int(np.argmax(emptied)) - 1 if emptied.any() else None


def fluid_touch(
    params: HawkesParams,
    marks: MarkParams,
    levels: GridDepth,
    opening: OpeningTouch,
    scaled_time: np.ndarray,
) -> np.ndarray:
    """``r(s)``, the fluid touch of haw-1: the size at the touch of either side at time
    ``Sbar s``, over ``Sbar``, in the limit of a large ``Sbar`` in which that side's opening
    touch over ``Sbar`` tends to ``opening`` (Proposition ``prop.fluidTouch``).

    At a spread of one tick a limit order joins the touch with probability ``eta`` and goes
    behind it otherwise, a market order takes a share from it, and a withdrawal draws it in
    proportion to its size, the side holding ``(L - 1 + r(0)) Sbar`` to first order.  So,
    with ``L_x = L - 1 + r(0)``,

        ``r' = eta lambda*_3 - lambda*_2 - (lambda*_5 / L_x) r``,  ``r(0) = opening``,

    with ``L`` the ``levels`` of a side of the opening book and ``eta`` the depth decay of
    ``marks``.  The solution relaxes to
    ``r_inf = L_x (eta lambda*_3 - lambda*_2) / lambda*_5``.
    """
    market, limit, withdrawal = _side_rates(params)
    side_size = levels - 1 + opening
    settled = side_size * (marks.depth_decay * limit - market) / withdrawal
    decay = np.exp(-withdrawal * np.asarray(scaled_time) / side_size)
    return settled + (opening - settled) * decay


def fluid_emptying_time(
    params: HawkesParams, marks: MarkParams, levels: GridDepth, opening: OpeningTouch
) -> float:
    """``s*``, the time at which the fluid touch from ``opening`` reaches zero, in units of
    ``Sbar``:

        ``s* = (L_x / lambda*_5) log(1 + lambda*_5 r(0) / (L_x (lambda*_2 - eta lambda*_3)))``,

    with ``L_x = L - 1 + r(0)``.  In the first regime, ``eta lambda*_3 < lambda*_2``,
    ``chi / Sbar`` tends to the smaller of the two sides' emptying times (Corollary
    ``corol.twoRegimes``).  Otherwise the fluid touch stays above zero, and ``s*`` is
    infinite.
    """
    market, limit, withdrawal = _side_rates(params)
    drain = market - marks.depth_decay * limit
    if drain <= 0:
        return np.inf
    side_size = levels - 1 + opening
    return float(side_size / withdrawal * np.log1p(withdrawal * opening / (side_size * drain)))


def diffusive_scale(params: HawkesParams, uniform_depth: UniformDepth) -> float:
    """``Sbar^2 / (varpi^b)' D varpi^b``, in seconds: the time over which the standard
    deviation of a touch walk reaches ``Sbar``.  In the second regime ``psi^CKS``, and with
    it ``chi``, is of this order (Approximation ``approx.secondRegime``); a side of the
    opening book, which holds about ``L Sbar``, lasts of the order of ``L^2`` times as
    long."""
    bid = side_vector(BUY)
    return float(uniform_depth**2 / (bid @ params.count_covariance_rate() @ bid))


def second_regime_rate(params: HawkesParams, uniform_depth: UniformDepth) -> float:
    """``varpi' D varpi / (2 Sbar)^2``, in ticks squared a second: the rate of ``Var D_t``
    while no best price of the Hawkes book moves (Approximation
    ``approx.secondRegimeVariance``).  ``D_t`` is then the CKS mid less the opening one, a
    function of the path, and the whole rate is its flow part."""
    pressure = _pressure()
    return float(pressure @ params.count_covariance_rate() @ pressure / (2 * uniform_depth) ** 2)


def _imbalance_and_move(pair: CoupledFlows) -> tuple[float, float]:
    """``OFI^haw_{T,T}``, in units, and ``Pi_T = 2 (P^m_T - P^m_0)`` in ticks, of the Hawkes
    book of ``pair`` at its last event."""
    imbalance = pair.frame["HawOrderFlowContribution"].sum()
    touches = _touch_rows(pair, "Haw")
    move = touches[-1, 0] + touches[-1, 2] - touches[0, 0] - touches[0, 2]
    return float(imbalance), float(move)


@dataclass(frozen=True, slots=True, eq=False)
class PlacementStatistics:
    """``alpha`` and ``S~``: what Approximation ``approx.firstRegimeVariance`` reads of the
    books of a Hawkes flow, under its hypotheses H1 and H2.

    * ``behind_probability`` is ``alpha_e``, by type: the fraction of the events of the type
      that the book places behind the touch of their side, the set ``ℋ`` of Lemma
      ``lemma.unitContribution``.  Those are the limit orders and withdrawals with
      ``e_n = 0``; a market order, which always acts at a touch, has none.  It is NaN for a
      type with no event.
    * ``effective_depth`` is ``S~``, in units: by ``eq.effectiveDepth``, the slope of the
      regression of the order flow imbalance of the book since the opening on
      ``Pi_T = 2 (P^m_T - P^m_0) / tau``, across runs to one horizon.  It is infinite when
      no best price moves.  The mean outer size per tick crossed at the moves is a
      different statistic.
    """

    behind_probability: np.ndarray
    effective_depth: float

    @classmethod
    def of(cls, pairs: list[CoupledFlows]) -> "PlacementStatistics":
        """The two statistics of the Hawkes books of ``pairs``, runs to one horizon:
        ``alpha`` pooled over their events, ``S~`` regressed across them."""
        frames = [pair.frame for pair in pairs]
        types = np.concatenate([frame["EventType"].to_numpy() for frame in frames])
        behind = np.concatenate(
            [frame["HawOrderFlowContribution"].to_numpy() == 0 for frame in frames]
        )
        dimension = len(EventType)
        counts = np.bincount(types, minlength=dimension)
        placed_behind = np.bincount(types, weights=behind, minlength=dimension)
        behind_probability = np.divide(
            placed_behind, counts, out=np.full(dimension, np.nan), where=counts > 0
        )
        imbalance, move = np.array([_imbalance_and_move(pair) for pair in pairs]).T
        if not move.any():
            return cls(behind_probability, np.inf)
        slope = np.cov(imbalance, move)[0, 1] / np.var(move, ddof=1)
        return cls(behind_probability, float(slope))


@dataclass(frozen=True, slots=True)
class VarianceRates:
    """The rates, in ticks squared a second, at which the flow part and the placement part
    of ``Var D_t`` grow."""

    flow_part: float
    placement_part: float

    @property
    def total(self) -> float:
        return self.flow_part + self.placement_part


def closed_form_rates(
    params: HawkesParams,
    uniform_depth: UniformDepth,
    statistics: PlacementStatistics,
    size_variance: float,
) -> VarianceRates:
    """The two rates of ``Var D_t`` in the first regime, by Approximation
    ``approx.firstRegimeVariance``.

    ``c_e = 1 / (2 Sbar) - (1 - alpha_e) / (2 S~)`` is the impact of one event of type ``e``
    on the CKS mid less its mean impact on the Hawkes one, and the flow part is
    ``(varpi o c)' D (varpi o c)``.  The placement part is
    ``sum_e alpha_e (1 - alpha_e) lambda*_e / (2 S~)^2``, whether an event lands behind its
    touch.  With an infinite ``S~`` the mid of the Hawkes book does not move, and the rates
    are those of :func:`second_regime_rate`.

    ``size_variance`` is ``Var xi`` of the sizes in units, zero for haw-1.  Otherwise each
    event enters the placement part with the variance ``eq.sizePlacementVariance``,
    ``alpha_e (1 - alpha_e) + (1 - alpha_e) Var xi``, which adds
    ``Var xi sum_e (1 - alpha_e) lambda*_e / (2 S~)^2``.  By Remark
    ``remark.whatTheSizesAdd`` that term, the truncation at the touch being set aside, is
    neither the whole of what the sizes add nor a bound on it, and for haw-q the rates are
    not a closed form of the variance.
    """
    alpha = statistics.behind_probability
    depth = 2 * statistics.effective_depth
    impact = _pressure() * (1 / (2 * uniform_depth) - (1 - alpha) / depth)
    noise = alpha * (1 - alpha) + (1 - alpha) * size_variance
    return VarianceRates(
        float(impact @ params.count_covariance_rate() @ impact),
        float(noise @ params.stationary_intensity() / depth**2),
    )
