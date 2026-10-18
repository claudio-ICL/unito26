"""The idealised and the geometric placement of one order flow, on the same events.

Example ``example.idealisedPlacement`` and Definition ``def.geometricPlacement`` of the
notes turn the events of a six-type Hawkes process into messages in two ways.  The first
keeps Assumption ``assumption.idealisedBook`` true, so that the identity of the order flow
imbalance is exact; the second is the flow the package simulates.  Drawn on one path of
events and folded from one opening book, the two books are equal until the placements turn
an event into different orders, and :class:`CoupledPlacements` records both
sessions, aligned on the event, and the first event after which they differ.

With orders of one share and ``DepthDecay`` one, the geometric placement sends a limit order
one tick from the opposite touch, and a market order takes one share from the opposite
touch under both.  A limit order is the same order exactly when the idealised placement
sends it to that price too: at a spread of one tick, to a touch holding less than ``Sbar``, and at a spread
of two, from a touch holding ``Sbar``.  A withdrawal differs whenever the geometric
placement draws a level behind the touch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd

from unito26.lob import frames
from unito26.lob.hawkes import HawkesParams
from unito26.lob.idealised import AssumptionBreach, IdealisedFlow, UniformDepth, idealised_book
from unito26.lob.messages import BUY, SELL, GridDepth, Message, PriceUnit, ReportedDepth
from unito26.lob.orderbook import AggregateBook
from unito26.lob.session import MarketSession
from unito26.lob.simulate import EventJournal, EventType, MarkParams, OrderFlowSimulator
from unito26.lob.statistics import SessionStatistics

__all__ = [
    "RecordedEvents",
    "Replay",
    "CoupledPlacements",
    "first_discrepancy",
    "target_offsets",
    "agreement_probability",
    "touch_shares",
    "conditional_survival",
    "limit_event_outcomes",
    "agreement_by_case",
    "idealised_readings",
    "geometric_readings",
    "geometric_mid_moves",
    "distance_terms",
    "touch_walk_exit",
]

STATISTICS = SessionStatistics((GridDepth(1),), (), (1,))


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


def _signed_levels(book: AggregateBook) -> dict[int, int]:
    """The whole book as one map, ``+S`` at a bid price and ``-S`` at an ask price.

    The book never crosses, so no price carries both signs, and two books are equal exactly
    when their maps are.
    """
    asks = {price: -size for price, size in book.levels_map(SELL).items()}
    return dict(book.levels_map(BUY)) | asks


def _until_breach(stream: Iterator[Message], breaches: list) -> Iterator[Message]:
    try:
        yield from stream
    except AssumptionBreach as breach:
        breaches.append(breach)


def _recording(stream: Iterator[Message], book: AggregateBook, states: list) -> Iterator[Message]:
    """The stream, recording the whole book after each message.

    A message is applied by the consumer between one ``next`` and the following one, so on
    resuming the book holds its result.
    """
    for message in stream:
        yield message
        states.append(_signed_levels(book))


def _touch_frame(session: MarketSession) -> pd.DataFrame:
    """Per row: the mid, the two touches in ticks with an empty side as NaN, and ``e_n``."""
    book = session.lobster_book
    frame = pd.DataFrame(
        {
            "MidPrice": session.stats["MidPrice"].to_numpy(),
            "BidPrice1": book["BidPrice1"].where(book["BidPrice1"] != frames.BID_PADDING),
            "BidSize1": book["BidSize1"],
            "AskPrice1": book["AskPrice1"].where(book["AskPrice1"] != frames.ASK_PADDING),
            "AskSize1": book["AskSize1"],
            "OrderFlowContribution": session.stats["OrderFlowContribution"].to_numpy(),
        }
    )
    return frame.reset_index(drop=True).astype(float)


@dataclass(frozen=True, eq=False)
class CoupledPlacements:
    """The two placements of one path of events, folded from copies of one opening book.

    ``frame`` has a row per event, indexed by ``Event``: its time and type, the mid, the
    touches and ``e_n`` of each book after it, under ``Idealised`` and ``Geometric``
    prefixes, and ``BooksDiffer``.  The books differ after an event when they differ at
    some price, on either side, in what rests there; the touches alone do not decide it,
    since a limit order behind one changes the depth and no touch.

    The geometric placement drops a withdrawal from an empty side, so its session may have
    fewer rows than there are events.  The row of a dropped event repeats the book before it
    and has ``e_n = 0``, or NaN where a side is empty, as the session has it.

    The idealised placement cannot continue past an event that would empty a side.  The
    pair then stops before that event, both placements reading the events before it, and
    ``breach`` holds the :class:`AssumptionBreach`; it is None for a pair that reached the
    horizon.  A pair that stopped at a breach without a discrepancy says nothing of when
    one would have come.

    ``idealised_depth`` and ``geometric_depth`` are the whole books, a row per event and a
    column per price in ticks, holding the size at a bid price and minus the size at an ask
    price.
    """

    events: RecordedEvents
    idealised: MarketSession
    geometric: MarketSession
    idealised_journal: EventJournal
    geometric_journal: EventJournal
    frame: pd.DataFrame
    idealised_depth: pd.DataFrame
    geometric_depth: pd.DataFrame
    breach: AssumptionBreach | None

    @classmethod
    def on(
        cls,
        events: RecordedEvents,
        marks: MarkParams,
        uniform_depth: UniformDepth,
        touches: dict[int, tuple[int, int]],
        levels: GridDepth,
        rng: np.random.Generator | int | None = None,
    ) -> "CoupledPlacements":
        """Both placements of ``events``, from ``idealised_book(uniform_depth, touches, levels)``.

        ``rng`` draws the marks of the geometric placement, the idealised one drawing
        nothing.  Its reference price, read only when a side is empty, is the opening bid.
        """
        opening = idealised_book(uniform_depth, touches, levels)

        book, journal, states, breaches = opening.copy(), EventJournal.empty(), [], []
        flow = IdealisedFlow(events.replay(), uniform_depth)
        stream = _until_breach(flow.stream(book, events.horizon, journal), breaches)
        idealised = MarketSession.from_occupied_levels(
            book, _recording(stream, book, states), ReportedDepth(1), STATISTICS,
            PriceUnit(1), True,
        )
        idealised_journal, idealised_states = journal, states
        seen = events.head(len(journal)) if breaches else events

        book, journal, states = opening.copy(), EventJournal.empty(), []
        simulator = OrderFlowSimulator.driven_by(seen.replay(), marks, touches[BUY][0], rng)
        geometric = MarketSession.from_occupied_levels(
            book, _recording(simulator.stream(book, seen.horizon, journal), book, states),
            ReportedDepth(1), STATISTICS, PriceUnit(1), True,
        )

        emitted = np.array(journal.emitted, dtype=bool)
        # The opening book has both sides occupied, so the first event is never dropped and
        # every row index here is at least zero.
        row = np.cumsum(emitted) - 1
        geometric_states = [states[i] for i in row]

        geometric_touch = _touch_frame(geometric).iloc[row].reset_index(drop=True)
        unchanged = ~emitted & geometric_touch["MidPrice"].notna().to_numpy()
        geometric_touch.loc[unchanged, "OrderFlowContribution"] = 0.0
        frame = pd.concat(
            [
                pd.DataFrame({"TimeStamp": seen.times, "EventType": seen.types}),
                _touch_frame(idealised).add_prefix("Idealised"),
                geometric_touch.add_prefix("Geometric"),
            ],
            axis=1,
        )
        frame["BooksDiffer"] = [a != b for a, b in zip(idealised_states, geometric_states)]
        frame.index.name = "Event"
        return cls(
            seen, idealised, geometric, idealised_journal, journal, frame,
            _depth_frame(idealised_states), _depth_frame(geometric_states),
            breaches[0] if breaches else None,
        )

    @property
    def first_discrepancy(self) -> int | None:
        """The first event after which the books differ, None if they never do."""
        differ = self.frame["BooksDiffer"].to_numpy()
        return int(np.argmax(differ)) if differ.any() else None

    @property
    def first_discrepancy_time(self) -> float | None:
        first = self.first_discrepancy
        return None if first is None else float(self.frame["TimeStamp"].iloc[first])


def _depth_frame(states: list[dict[int, int]]) -> pd.DataFrame:
    depth = pd.DataFrame.from_records(states).fillna(0.0)
    depth = depth.reindex(columns=sorted(depth.columns), fill_value=0.0)
    depth.index.name = "Event"
    depth.columns.name = "Price"
    return depth


# ---- the first discrepancy, event by event -----------------------------------------

LIMIT_TYPES = (EventType.LIMIT_BUY, EventType.LIMIT_SELL)
WITHDRAWAL_TYPES = (EventType.WITHDRAW_BUY, EventType.WITHDRAW_SELL)


def first_discrepancy(
    events: RecordedEvents,
    marks: MarkParams,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    rng: np.random.Generator | int | None = None,
) -> int | None:
    """``CoupledPlacements.on(...).first_discrepancy``, folding the two books alone and
    stopping at it.

    A breach of the assumption before the books differ raises :class:`AssumptionBreach`,
    where the pair would record it.
    """
    idealised = idealised_book(uniform_depth, touches, levels)
    geometric = idealised.copy()
    flow = IdealisedFlow(events.replay(), uniform_depth)
    simulator = OrderFlowSimulator.driven_by(events.replay(), marks, touches[BUY][0], rng)
    # Until the books differ the geometric book has both sides occupied, so it drops no
    # event and the two streams stay aligned.
    pairs = zip(
        flow.stream(idealised, events.horizon, None),
        simulator.stream(geometric, events.horizon, None),
    )
    for event, (idealised_message, geometric_message) in enumerate(pairs):
        idealised.apply(idealised_message, record=False)
        geometric.apply(geometric_message, record=False)
        if _signed_levels(idealised) != _signed_levels(geometric):
            return event
    return None


def target_offsets(
    events: RecordedEvents,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
) -> pd.DataFrame:
    """At each limit event, the book the idealised placement finds it, and ``zeta*_n``.

    A row per limit event, indexed by ``Event``, its position in the path: ``TimeStamp``,
    ``EventType``, the ``Spread`` in ticks and ``TouchFull``, whether the touch of the
    order's side holds ``Sbar``, both before the event, and ``TargetOffset``,
    ``Spread - 1 - TouchFull``.  It is the offset at which (eq.limitPrice) prices the order
    where the idealised placement does, and is minus one when the idealised order trades,
    which no offset reproduces.  The idealised placement draws nothing, so the frame is a
    function of the path; a breach raises :class:`AssumptionBreach`.
    """
    book = idealised_book(uniform_depth, touches, levels)
    flow = IdealisedFlow(events.replay(), uniform_depth)
    rows = []
    for event, message in enumerate(flow.stream(book, events.horizon, None)):
        kind = EventType(int(events.types[event]))
        if kind in LIMIT_TYPES:
            touch = book.best_price(kind.direction)
            full = book.size_at(kind.direction, touch) == uniform_depth
            rows.append((event, events.times[event], int(kind), book.spread, full))
        book.apply(message, record=False)
    frame = pd.DataFrame(
        rows, columns=["Event", "TimeStamp", "EventType", "Spread", "TouchFull"]
    ).set_index("Event")
    frame["TargetOffset"] = frame["Spread"] - 1 - frame["TouchFull"].astype(int)
    return frame


def agreement_probability(target_offset, depth_decay: float) -> np.ndarray:
    """``q(zeta*) = eta (1 - eta)^zeta*``, the probability (eq.priceOffset) gives the offset
    ``zeta*``, and ``q(-1) = 0``."""
    offset = np.asarray(target_offset)
    return np.where(
        offset >= 0, depth_decay * (1.0 - depth_decay) ** np.maximum(offset, 0), 0.0
    )


def touch_shares(
    events: RecordedEvents,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
) -> pd.DataFrame:
    """At each withdrawal, the share of its side that rests at the best quote, on the book
    the idealised placement finds it.

    A row per withdrawal, indexed by ``Event``: ``TimeStamp``, ``EventType`` and
    ``TouchShare``.  With orders of one share the geometric withdrawal is the idealised one
    exactly when the level it draws is the best quote, which by Definition
    ``def.geometricPlacement`` *iii.* has that probability.  A breach raises
    :class:`AssumptionBreach`.
    """
    book = idealised_book(uniform_depth, touches, levels)
    flow = IdealisedFlow(events.replay(), uniform_depth)
    rows = []
    for event, message in enumerate(flow.stream(book, events.horizon, None)):
        kind = EventType(int(events.types[event]))
        if kind in WITHDRAWAL_TYPES:
            side = book.levels_map(kind.direction)
            share = side[book.best_price(kind.direction)] / sum(side.values())
            rows.append((event, events.times[event], int(kind), share))
        book.apply(message, record=False)
    return pd.DataFrame(
        rows, columns=["Event", "TimeStamp", "EventType", "TouchShare"]
    ).set_index("Event")


def conditional_survival(times, agreement, clock: np.ndarray) -> np.ndarray:
    """``P(chi > t | the events)``, the product of ``agreement`` over the ``times`` at or
    before ``t``, at every ``t`` of ``clock``.

    ``agreement`` is the probability that the event at each of ``times`` leaves the books
    equal, given that they were equal before it: :func:`agreement_probability` at a limit
    order, the ``TouchShare`` of :func:`touch_shares` at a withdrawal, one at a market
    order, with orders of one share.  The offsets and the levels drawn are independent of
    the events and of each other, so the probability that every event agrees is the product.
    """
    product = np.r_[1.0, np.cumprod(np.asarray(agreement, dtype=float))]
    return product[np.searchsorted(np.asarray(times, dtype=float), clock, side="right")]


def limit_event_outcomes(offsets: pd.DataFrame, first: int | None) -> pd.DataFrame:
    """The limit events of ``offsets`` up to the first discrepancy ``first``, with
    ``Agreed``: whether the books still agree after the event.  Past the first discrepancy
    the book is no longer the idealised one, and a limit event there says nothing of the
    rule."""
    reached = offsets if first is None else offsets.loc[offsets.index <= first]
    return reached.assign(Agreed=reached.index != first)


#: The touch whose walk an event of each type moves, and by how much.
WALK_STEPS = {
    EventType.MARKET_BUY: (SELL, -1),
    EventType.MARKET_SELL: (BUY, -1),
    EventType.LIMIT_BUY: (BUY, +1),
    EventType.LIMIT_SELL: (SELL, +1),
    EventType.WITHDRAW_BUY: (BUY, -1),
    EventType.WITHDRAW_SELL: (SELL, -1),
}


def touch_walk_exit(
    events: RecordedEvents, touches: dict[int, tuple[int, int]], uniform_depth: UniformDepth
) -> float | None:
    """``tau_G``, the first time a touch walk leaves ``[1, Sbar]``, None if neither does.

    The walk of a side starts from the size at its touch and moves by one share at each
    event acting on that touch.  Before ``tau_G`` the idealised book keeps both prices and
    its touches are the walks; at it a touch is cleared, or a limit order meets a full
    touch.
    """
    walk = {BUY: touches[BUY][1], SELL: touches[SELL][1]}
    for time, kind in zip(events.times, events.types):
        side, step = WALK_STEPS[EventType(int(kind))]
        walk[side] += step
        if not 1 <= walk[side] <= uniform_depth:
            return float(time)
    return None


def agreement_by_case(outcomes: pd.DataFrame, depth_decay: float) -> pd.DataFrame:
    """The frequency of agreement at the limit events of ``outcomes``, by the book each found,
    against ``q(zeta*)``.

    ``outcomes`` is :func:`limit_event_outcomes` of any number of paths, concatenated.  A row
    per ``(Spread, TouchFull)``: its ``TargetOffset``, the ``LimitEvents`` observed there,
    the frequency ``Agreed`` with its binomial ``StandardError``, and the ``Formula``.
    """
    grouped = outcomes.groupby(["Spread", "TouchFull"])
    table = pd.DataFrame(
        {
            "TargetOffset": grouped["TargetOffset"].first(),
            "LimitEvents": grouped.size(),
            "Agreed": grouped["Agreed"].mean(),
        }
    )
    table["StandardError"] = np.sqrt(
        table["Agreed"] * (1.0 - table["Agreed"]) / table["LimitEvents"]
    )
    table["Formula"] = agreement_probability(table["TargetOffset"], depth_decay)
    return table


def _readings(book: AggregateBook) -> tuple[float, int, int]:
    """The mid, NaN with a side empty, and the total size on each side."""
    mid = book.mid_price
    return (
        np.nan if mid is None else mid,
        sum(book.levels_map(BUY).values()),
        sum(book.levels_map(SELL).values()),
    )


def _read_on_clock(stream: Iterator[Message], book: AggregateBook, clock: np.ndarray):
    """``_readings`` of the book after the last message at or before each time of
    ``clock``, the stream folded into it."""
    readings, next_time = [], 0
    for message in stream:
        while next_time < clock.size and clock[next_time] < message.time:
            readings.append(_readings(book))
            next_time += 1
        book.apply(message, record=False)
    readings.extend([_readings(book)] * (clock.size - next_time))
    return np.array(readings, dtype=float)


def _readings_frame(readings: np.ndarray, clock: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(
        readings, index=pd.Index(clock, name="Time"),
        columns=["MidPrice", "BidDepth", "AskDepth"],
    )


def idealised_readings(
    events: RecordedEvents,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    clock: np.ndarray,
) -> pd.DataFrame:
    """The idealised book at every time of ``clock``, after the last event at or before it:
    ``MidPrice``, and ``BidDepth`` and ``AskDepth``, the total size on each side.  A breach
    of the assumption raises :class:`AssumptionBreach`."""
    clock = np.asarray(clock, dtype=float)
    book = idealised_book(uniform_depth, touches, levels)
    stream = IdealisedFlow(events.replay(), uniform_depth).stream(book, events.horizon, None)
    return _readings_frame(_read_on_clock(stream, book, clock), clock)


def geometric_readings(
    events: RecordedEvents,
    marks: MarkParams,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    clock: np.ndarray,
    rng: np.random.Generator | int | None = None,
) -> pd.DataFrame:
    """The geometric book from ``idealised_book(uniform_depth, touches, levels)``, read as
    :func:`idealised_readings` reads the idealised one; the mid is NaN while a side is
    empty."""
    clock = np.asarray(clock, dtype=float)
    book = idealised_book(uniform_depth, touches, levels)
    simulator = OrderFlowSimulator.driven_by(events.replay(), marks, touches[BUY][0], rng)
    stream = simulator.stream(book, events.horizon, None)
    return _readings_frame(_read_on_clock(stream, book, clock), clock)


def _touch_moves(touch: pd.DataFrame, uniform_depth: UniformDepth) -> pd.DataFrame:
    """Per event of one book, from its touches with the opening prepended: ``e_n`` by
    (``eq.orderFlowContribution``), and the size at the outer of the two values of each best
    price that moved, less ``Sbar`` per tick moved, signed by the move."""
    bid, bid_size = touch["BidPrice1"].to_numpy(), touch["BidSize1"].to_numpy()
    ask, ask_size = touch["AskPrice1"].to_numpy(), touch["AskSize1"].to_numpy()
    up_bid, down_bid = bid[1:] > bid[:-1], bid[1:] < bid[:-1]
    up_ask, down_ask = ask[1:] > ask[:-1], ask[1:] < ask[:-1]
    contribution = (
        ~down_bid * bid_size[1:] - ~up_bid * bid_size[:-1]
        - ~up_ask * ask_size[1:] + ~down_ask * ask_size[:-1]
    )
    outer_bid = np.where(up_bid, bid_size[:-1], np.where(down_bid, bid_size[1:], 0.0))
    outer_ask = np.where(up_ask, ask_size[1:], np.where(down_ask, ask_size[:-1], 0.0))
    move_bid, move_ask = np.diff(bid), np.diff(ask)
    depth = (
        np.sign(move_bid) * (outer_bid - uniform_depth * np.abs(move_bid))
        + np.sign(move_ask) * (outer_ask - uniform_depth * np.abs(move_ask))
    )
    return pd.DataFrame({"Contribution": contribution, "DepthMismatch": depth})


def distance_terms(
    pair: CoupledPlacements, uniform_depth: UniformDepth, touches: dict[int, tuple[int, int]]
) -> pd.DataFrame:
    """``2 Sbar (P^m_geometric - P^m_idealised)`` after each event, in ticks, and its three
    terms.

    ``ImbalanceMismatch`` is the geometric minus the idealised order flow imbalance since the
    opening; ``TouchSizeMismatch`` is the geometric minus the idealised bid size, less the
    same of the ask; ``DepthMismatch`` sums, over the moves of a geometric best price, the size
    at the outer of its two values less ``Sbar`` per tick moved, signed by the move.  Then
    ``Distance = ImbalanceMismatch - TouchSizeMismatch - DepthMismatch``, while both sides
    of both books are occupied.  ``IdealisedDepthMismatch`` is the same sum on the idealised
    book, where every move is one tick onto or off a queue of ``Sbar`` and the sum is zero;
    that is Proposition ``prop.idealisedUpdate``.  ``touches`` are those of the opening book.
    """
    opening = pd.DataFrame(
        {"BidPrice1": [touches[BUY][0]], "BidSize1": [touches[BUY][1]],
         "AskPrice1": [touches[SELL][0]], "AskSize1": [touches[SELL][1]]},
        dtype=float,
    )
    moves, books = {}, {}
    for placement in ("Idealised", "Geometric"):
        columns = [f"{placement}{column}" for column in opening.columns]
        book = pair.frame[columns].set_axis(opening.columns, axis=1).reset_index(drop=True)
        books[placement] = book
        moves[placement] = _touch_moves(pd.concat([opening, book], ignore_index=True),
                                        uniform_depth)
    sizes = {
        placement: (book["BidSize1"] - book["AskSize1"]).to_numpy()
        for placement, book in books.items()
    }
    return pd.DataFrame(
        {
            "TimeStamp": pair.frame["TimeStamp"].to_numpy(),
            "Distance": 2 * uniform_depth * (
                pair.frame["GeometricMidPrice"] - pair.frame["IdealisedMidPrice"]
            ).to_numpy(),
            "ImbalanceMismatch": np.cumsum(
                moves["Geometric"]["Contribution"] - moves["Idealised"]["Contribution"]
            ).to_numpy(),
            "TouchSizeMismatch": sizes["Geometric"] - sizes["Idealised"],
            "DepthMismatch": np.cumsum(moves["Geometric"]["DepthMismatch"]).to_numpy(),
            "IdealisedDepthMismatch": np.cumsum(moves["Idealised"]["DepthMismatch"]).to_numpy(),
        },
        index=pair.frame.index,
    )


def geometric_mid_moves(
    events: RecordedEvents,
    marks: MarkParams,
    uniform_depth: UniformDepth,
    touches: dict[int, tuple[int, int]],
    levels: GridDepth,
    rng: np.random.Generator | int | None = None,
) -> pd.DataFrame:
    """Every move of the mid-price of the geometric book, from ``idealised_book(uniform_depth,
    touches, levels)``.

    A row per move: ``TimeStamp``, the ``Move`` in ticks from the last mid defined before it,
    and ``AcrossEmptySide``, whether a side was empty in between.  While a side is empty the
    mid is undefined and the geometric placement prices a limit order against its fixed
    reference price instead of the opposite best quote, so a move across an empty side is
    not a move the book made from where it stood.
    """
    book = idealised_book(uniform_depth, touches, levels)
    simulator = OrderFlowSimulator.driven_by(events.replay(), marks, touches[BUY][0], rng)
    last, emptied, rows = book.mid_price, False, []
    for message in simulator.stream(book, events.horizon, None):
        book.apply(message, record=False)
        mid = book.mid_price
        if mid is None:
            emptied = True
        elif mid != last:
            rows.append((message.time, mid - last, emptied))
            last, emptied = mid, False
        else:
            emptied = False
    return pd.DataFrame(rows, columns=["TimeStamp", "Move", "AcrossEmptySide"])
