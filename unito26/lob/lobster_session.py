"""A LOBSTER pair as it is written, and the one transformation that makes it a session.

A :class:`~unito26.lob.session.MarketSession` has one row per aggressive order and one per
other message, which is what a fold produces.  A LOBSTER pair does not: the feed records
the execution of each *resting* order, so an order consuming five of them writes five rows
at one instant, with the intermediate states between them.  The two frames carry the same
columns and count different things, and no schema can say so.

So they are two types.  This module holds the raw one, which keeps the pair positionally
indexed exactly as the files have it, and :meth:`LobsterMarketSession.coarsened`, which is
the only way across.  What the crossing costs is stated there and measured by
``coarsening_report``.

``documentation/from-lobster-files-to-a-session.md`` §5 is the reference for the mechanism.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob import frames, lobster
from unito26.lob.lobster import LobsterEvent, LobsterFiles, TradingWindow
from unito26.lob.messages import PriceUnit, ReportedDepth, TickGrid
from unito26.lob.session import MarketSession, _with_vwap, statistics_from_book
from unito26.lob.statistics import SessionStatistics

__all__ = [
    "LobsterMarketSession",
    "execution_gap_census",
    "market_order_census",
    "market_order_index",
    "price_reversing_orders",
]

#: The two events that print on the tape.  A hidden execution moves no visible level, so it
#: is a trade the book never showed; it is here because one aggressive order can take lit
#: and hidden liquidity in a single sweep, and the rows of that sweep are one market order.
EXECUTIONS = (LobsterEvent.EXECUTION_VISIBLE, LobsterEvent.EXECUTION_HIDDEN)


def market_order_index(messages: pd.DataFrame) -> np.ndarray:
    """Which market order each row belongs to, or ``-1`` for a row in none.

    A **market order** is a maximal contiguous block of visible executions sharing an
    instant and a direction, together with any hidden executions lying strictly between two
    of them.  Section 6 of the notation names the object: the file gives the fills
    ``q_i``, a fold gives the market order ``q_M = sum q_i``, and this is how the second is
    recovered from the first.

    Three details, each of which was measured before it was chosen.

    **Contiguity, never a groupby on the instant.** The fills of one aggressive order are
    consecutive in the sequence.  Grouping by ``(TimeNanoseconds, Direction)`` alone joins
    two orders that merely arrived in the same nanosecond.

    **Hidden prints are absorbed only when interior.** A hidden execution leaves the visible
    book byte-identical while carrying a price of its own, often sub-penny.  Absorbing one
    that sits *between* two visible fills recovers the sweep that took both kinds of
    liquidity; absorbing one at the edge of a block merges rows with nothing to say they
    belong to the same aggressor, and it destroys the classification of the block by its
    prices, since a price that moved no level is not a level walked.

    **A block of hidden prints alone is no market order.** It answers ``-1``, and every such
    row in the sample repeats the book state before it.
    """
    kind = messages["Type"].to_numpy()
    if not len(kind):
        return np.zeros(0, dtype=np.int64)
    key = messages["TimeNanoseconds"].to_numpy()
    side = messages["Direction"].to_numpy()
    visible = kind == LobsterEvent.EXECUTION_VISIBLE
    execution = np.isin(kind, EXECUTIONS)

    fresh = np.ones(len(kind), dtype=bool)
    fresh[1:] = ~(
        execution[1:]
        & execution[:-1]
        & (key[1:] == key[:-1])
        & (side[1:] == side[:-1])
    )
    block = np.cumsum(fresh) - 1
    rows = np.arange(len(kind))

    blocks = int(block[-1]) + 1
    opens = np.full(blocks, len(kind), dtype=np.int64)
    closes = np.full(blocks, -1, dtype=np.int64)
    np.minimum.at(opens, block[visible], rows[visible])
    np.maximum.at(closes, block[visible], rows[visible])

    traded = closes >= 0
    label = np.full(blocks, -1, dtype=np.int64)
    label[traded] = np.arange(int(traded.sum()))
    inside = traded[block] & (rows >= opens[block]) & (rows <= closes[block])
    return np.where(inside, label[block], -1)


def _trade_rows(messages: pd.DataFrame, price_unit: PriceUnit) -> np.ndarray:
    """What each message traded, in ``trade_row_schema`` order.

    Visible executions only.  A type-5 print is a trade against an order that was never
    displayed, and it rests at or inside the touch, so including it would give the traded
    average of a tape the book never showed.  The lit VWAP is the one a book route could
    also produce, which is what makes it the comparable number.

    LOBSTER reports the *resting* side of a fill, so ``Direction`` names the passive order
    and the aggressor is its negation: an executed sell limit order is a buyer-initiated
    trade.  The name carries it, so the arithmetic below needs no comment of its own.

    ``TradedValue`` is in tick-shares, matching the fold's own trade rows, which is why the
    price is divided by the unit here and not left in the file's.
    """
    executed = (messages["Type"] == LobsterEvent.EXECUTION_VISIBLE).to_numpy()
    aggressor = -messages["Direction"].to_numpy()
    size = np.where(executed, messages["Size"].to_numpy(), 0).astype(float)
    price = np.where(executed, messages["Price"].to_numpy(), 0) / price_unit
    return np.column_stack([size, aggressor * size, size * price])


def _retained_rows(messages: pd.DataFrame, orders: np.ndarray) -> np.ndarray:
    """The rows a coarse session keeps: one per market order, and every other message.

    A market order keeps its **last** row, the state after the whole order finished
    matching, which is the state a fold writes for the single message it saw.  Hidden
    prints belonging to no market order are dropped, their rows repeating the state before
    them -- except at row 0, where there is nothing to repeat and dropping it would leave
    the session with no opening state.
    """
    execution = np.isin(messages["Type"].to_numpy(), EXECUTIONS)
    keep = ~execution
    inside = orders >= 0
    if inside.any():
        last = np.zeros(int(orders.max()) + 1, dtype=np.int64)
        np.maximum.at(last, orders[inside], np.flatnonzero(inside))
        keep[last] = True
    if len(orders) and orders[0] < 0:
        keep[0] = True
    return np.flatnonzero(keep)


def _coarse_trade_rows(
    messages: pd.DataFrame, orders: np.ndarray, keep: np.ndarray, price_unit: PriceUnit
) -> np.ndarray:
    """The fills of each market order, summed onto the row that survives it.

    Volume and traded value are additive over the fills, so this is the one part of the
    coarsening that loses nothing: 20 + 20 + 15 at one price is 55 at that price.  What it
    gains is that the row now holds a *trade* size, which the file never states.
    """
    fine = _trade_rows(messages, price_unit)
    inside = orders >= 0
    coarse = np.zeros((len(keep), fine.shape[1]))
    if not inside.any():
        return coarse
    totals = np.stack(
        [
            np.bincount(
                orders[inside], weights=fine[inside, column], minlength=int(orders.max()) + 1
            )
            for column in range(fine.shape[1])
        ],
        axis=1,
    )
    surviving = orders[keep]
    traded = surviving >= 0
    coarse[traded] = totals[surviving[traded]]
    return coarse


@dataclass(eq=False)  # DataFrame fields make a generated __eq__ raise, not compare
class LobsterMarketSession:
    """A LOBSTER pair, held as the files hold it.

    Both frames are indexed **by position**, because position is the only alignment the
    format guarantees: the orderbook file carries no clock, no sequence number and no key,
    and row *i* is the state after message *i* because of how the file was written.  The
    clock is a column of ``messages`` and never an index here, which is the difference
    between this type and a :class:`~unito26.lob.session.MarketSession` that no comment has
    to be trusted to maintain -- a frame of one shape is refused by the other's schema.

    It is not a session in the sense the rest of the package uses the word, and it has no
    statistics of its own until asked.  It exists to be measured and to be coarsened.
    """

    files: LobsterFiles
    reported_depth: ReportedDepth
    statistics: SessionStatistics
    price_unit: PriceUnit
    truncated: bool
    """Whether an unreported level may exist below the ones the frame carries.

    Always True for a file, and a field rather than a constant because it travels into the
    coarse session, where a False would silently strengthen every coverage claim.
    """
    messages: pd.DataFrame
    book: pd.DataFrame

    @classmethod
    def from_files(
        cls,
        files: LobsterFiles,
        spec: SessionStatistics,
        grid: TickGrid,
        window: TradingWindow,
    ) -> "LobsterMarketSession":
        """Read the pair, cut to ``window``, and check its prices against the tick grid.

        ``grid`` rather than a price unit: the caller states the instrument's tick size and
        the file's unit follows from it, since a wrong unit does not fail but rescales every
        price the session reports.
        """
        unit = lobster.price_unit(grid)
        messages, book = lobster.load_aligned(files, window)
        lobster.prices_on_the_tick_grid(book, unit, files.reported_depth)
        return cls(
            files=files,
            reported_depth=files.reported_depth,
            statistics=spec,
            price_unit=unit,
            truncated=True,
            messages=messages,
            book=book,
        )

    def market_orders(self) -> np.ndarray:
        """Which market order each row belongs to.  See :func:`market_order_index`."""
        return market_order_index(self.messages)

    def stats_from_frame(self) -> pd.DataFrame:
        """Every statistic the raw book determines, one row per row of the file.

        The same arithmetic a ``MarketSession`` runs, over a frame whose rows are executions
        of resting orders rather than messages.  Which is exactly why the answer is not
        comparable row for row with a fold's, and why the columns that survive the
        coarsening are worth knowing before either is read.
        """
        return self.statistics.positional_statistics_schema().validate(
            statistics_from_book(
                self.book,
                self.messages["Time"].to_numpy(),
                self.reported_depth,
                self.price_unit,
                self.truncated,
                self.statistics,
            )
        )

    def trades_from_messages(self) -> pd.DataFrame:
        """What each message traded: the lit tape, one row per execution of a resting order.

        Its ``Volume`` is a *fill* size and not a trade size, which is the trap LOBSTER's
        own demo names: the mean of this column is the mean execution, and the mean trade is
        the mean over :meth:`market_orders`.
        """
        return self.statistics.positional_trades_schema().validate(
            pd.DataFrame(
                _with_vwap(
                    self.statistics,
                    self.messages["Time"].to_numpy(),
                    _trade_rows(self.messages, self.price_unit),
                ),
                index=self.book.index,
            )
        )

    def coarsened(self, statistics: bool) -> MarketSession:
        """One row per market order, and one per every other message.

        What survives exactly: every statistic that is a function of one book state, since
        the surviving row *is* one of the file's rows; and every window sum of an extensive
        quantity, since all the rows of a market order share a timestamp and so a window
        holds one whole or not at all.  Volume, traded value and VWAP are unchanged to the
        bit.

        What does not: the order flow contribution, which is a function of two consecutive
        states and equals the sum over the fills only when the touch is emptied at most once
        -- a queue split, never a level walk -- and every per-row average, of which
        ``AverageDepth{w}`` is one.

        What is discarded on purpose: the queue information.  The file knows a level of 100
        was five orders of 20 and the coarse session does not, which is the whole of what an
        aggregate book cannot represent.
        """
        orders = self.market_orders()
        keep = _retained_rows(self.messages, orders)
        session = MarketSession._assemble(
            self.reported_depth,
            self.statistics,
            self.price_unit,
            self.truncated,
            self.messages["Time"].to_numpy()[keep],
            self.book.to_numpy()[keep],
            None,
            _coarse_trade_rows(self.messages, orders, keep, self.price_unit),
            None,
        )
        if statistics:
            session.stats = session.stats_from_frame()
        return session

    def executions_off_the_touch(self) -> pd.DataFrame:
        """Visible executions whose price is not the best price on the side that rested.

        Expected empty, and empty on every shipped file: price-time priority fills the best
        price first, so a type-4 row prints at the prior ``AskPrice1`` when ``Direction`` is
        -1 and at the prior ``BidPrice1`` when it is +1.  That is the passive-side claim
        stated as an equality rather than as a sign, and it is what a reader who takes
        ``Direction`` for the trade's own direction breaks.

        The first row has no state before it and is not examined.
        """
        kind = self.messages["Type"].to_numpy()
        price = self.messages["Price"].to_numpy()
        side = self.messages["Direction"].to_numpy()
        ask = self.book["AskPrice1"].to_numpy()
        bid = self.book["BidPrice1"].to_numpy()
        rows = np.flatnonzero(kind == LobsterEvent.EXECUTION_VISIBLE)
        rows = rows[rows > 0]
        resting = np.where(side[rows] == -1, ask[rows - 1], bid[rows - 1])
        off = rows[price[rows] != resting]
        return pd.DataFrame(
            {
                "Row": off,
                "Price": price[off],
                "RestingSideBest": resting[price[rows] != resting],
                "Direction": side[off],
            }
        )


# ---- what the granularity looks like, before anything is done about it -------------------


def _visible_orders(messages: pd.DataFrame, convention: str) -> np.ndarray:
    """Labels over the visible executions alone, under one grouping convention.

    The three differ only in what they are willing to join across, and the reference's own
    section 5 quotes two of them a paragraph apart.
    """
    kind = messages["Type"].to_numpy()
    key = messages["TimeNanoseconds"].to_numpy()
    side = messages["Direction"].to_numpy()
    visible = np.flatnonzero(kind == LobsterEvent.EXECUTION_VISIBLE)
    if convention == "instant and direction":
        return np.unique(key[visible] * 2 + (side[visible] > 0), return_inverse=True)[1]
    if convention == "contiguous fills":
        joined = (
            (np.diff(visible) == 1)
            & (key[visible][1:] == key[visible][:-1])
            & (side[visible][1:] == side[visible][:-1])
        )
        return np.cumsum(np.concatenate(([True], ~joined))) - 1
    if convention == "hidden absorbed":
        return market_order_index(messages)[visible]
    raise ValueError(f"no such grouping convention: {convention!r}")


#: The three ways of asking which fills belong to one order, weakest first.  The last is the
#: one :func:`market_order_index` implements and the only one the coarsening uses.
GROUPING_CONVENTIONS = ("instant and direction", "contiguous fills", "hidden absorbed")


def market_order_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Ticker": pa.Column(str, coerce=True),
            "Convention": pa.Column(
                str, pa.Check.isin(GROUPING_CONVENTIONS), coerce=True
            ),
            "Executions": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "MarketOrders": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "MultiFill": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "FillsInside": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Largest": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "QueueSplits": pa.Column("int64", pa.Check.ge(0), coerce=True),
        },
        strict=True,
        ordered=True,
    )


def market_order_census(pairs: Sequence[LobsterFiles]) -> pd.DataFrame:
    """How many fills a market order takes, under each grouping convention.

    ``QueueSplits`` is the column to read.  A multi-fill order is either a *level walk*,
    which an aggregate book could report one level at a time if it chose, or a *queue
    split* -- several resting orders at one price, which no sequence of aggregate states
    determines, because the aggregate book does not know a level of 100 is five orders of
    20.  Four fifths of them are queue splits, so the granularity gap is overwhelmingly the
    part an aggregate book cannot reach even in principle.

    Reads the message files only.  Which fills belong together is a question about the tape.
    """
    rows = []
    for files in pairs:
        messages = lobster.load_messages(files.messages_path)
        price = messages["Price"].to_numpy()[
            messages["Type"].to_numpy() == LobsterEvent.EXECUTION_VISIBLE
        ]
        for convention in GROUPING_CONVENTIONS:
            orders = _visible_orders(messages, convention)
            fills = np.bincount(orders) if orders.size else np.zeros(0, dtype=int)
            multi = fills > 1
            distinct = (
                pd.Series(price).groupby(orders).nunique().to_numpy()
                if orders.size
                else np.zeros(0, dtype=int)
            )
            rows.append(
                {
                    "Ticker": files.ticker,
                    "Convention": convention,
                    "Executions": int(len(price)),
                    "MarketOrders": int(fills.size),
                    "MultiFill": int(multi.sum()),
                    "FillsInside": int(fills[multi].sum()),
                    "Largest": int(fills.max()) if fills.size else 0,
                    "QueueSplits": int((distinct[multi] == 1).sum()),
                }
            )
    return market_order_census_schema().validate(pd.DataFrame(rows))


def execution_gap_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Adjacency": pa.Column(str, coerce=True),
            "Pairs": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "AtTheSameInstant": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "SmallestPositiveNanoseconds": pa.Column("int64", nullable=True, coerce=True),
        },
        strict=True,
        ordered=True,
    )


def execution_gap_census(messages: pd.DataFrame) -> pd.DataFrame:
    """How far apart two visible executions at one price on one side are.

    The argument the whole grouping rests on: within a split the instant is *exactly* equal,
    and the nearest pair that is not shares no instant by a margin of microseconds.  There
    is no ambiguous middle, so grouping on equality neither merges two orders nor splits
    one -- and that is a measured property of the data, not a guarantee of the format.

    Both adjacencies are reported because they answer differently and the reference quotes
    one while describing the other.
    """
    kind = messages["Type"].to_numpy()
    key = messages["TimeNanoseconds"].to_numpy()
    price = messages["Price"].to_numpy()
    side = messages["Direction"].to_numpy()
    visible = np.flatnonzero(kind == LobsterEvent.EXECUTION_VISIBLE)
    rows = []
    for adjacency, taken in (
        ("in the file", visible[np.diff(np.concatenate(([-1], visible))) == 1]),
        ("among the executions", visible[1:]),
    ):
        before = (
            taken - 1
            if adjacency == "in the file"
            else visible[:-1][np.isin(visible[1:], taken)]
        )
        same = (price[taken] == price[before]) & (side[taken] == side[before])
        gaps = key[taken][same] - key[before][same]
        positive = gaps[gaps > 0]
        rows.append(
            {
                "Adjacency": adjacency,
                "Pairs": int(same.sum()),
                "AtTheSameInstant": int((gaps == 0).sum()),
                "SmallestPositiveNanoseconds": (
                    int(positive.min()) if positive.size else None
                ),
            }
        )
    return execution_gap_census_schema().validate(pd.DataFrame(rows))


def price_reversing_orders(messages: pd.DataFrame) -> pd.DataFrame:
    """Market orders whose fills move back towards the touch.  Expected empty.

    An aggressive order walks away from the mid and never back, so a reversal is evidence
    that two distinct aggressors at one instant on one side have been read as one.  It is a
    **weak** instrument: two orders each sweeping monotonically are invisible to it, so an
    empty answer is consistent with the hole being empty and does not establish it.
    """
    orders = market_order_index(messages)
    kind = messages["Type"].to_numpy()
    price = messages["Price"].to_numpy()
    side = messages["Direction"].to_numpy()
    rows = np.flatnonzero((orders >= 0) & (kind == LobsterEvent.EXECUTION_VISIBLE))
    label = orders[rows]
    stepped = np.flatnonzero(label[1:] == label[:-1])
    # The aggressor is the negation of the resting side, and it pays worse prices as it
    # goes: a buyer walks up the ask, a seller down the bid.
    away = (price[rows][stepped + 1] - price[rows][stepped]) * -side[rows][stepped]
    reversing = np.unique(label[stepped][away < 0])
    return pd.DataFrame(
        {
            "Order": reversing,
            "Fills": [int((label == order).sum()) for order in reversing],
            "FirstRow": [int(rows[label == order][0]) for order in reversing],
            "LastRow": [int(rows[label == order][-1]) for order in reversing],
        }
    )
