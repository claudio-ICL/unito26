"""Reading the LOBSTER sample files -- descriptively, without reconstructing anything.

LOBSTER ships a *message* file and an *orderbook* file for the same session, the second
being the book the first produces.  Reconstructing one from the other is not attempted
here: this module loads the two files and describes them, which touches none of the edge
cases that make the reconstruction hard.

Those edge cases stand between the ladder's top rung and real data:

* **truncation** -- only events inside the visible price range are reported, so the
  deep levels are unknowable and even the last visible one degrades over the session;
* **pre-existing orders** -- messages reference orders posted before the file begins,
  so the book must be seeded from the first snapshot row, and that seeded size has
  no identity: a hybrid of aggregate and identified state;
* **hidden liquidity** -- type-5 executions are trades that move no visible level;
* **non-unique timestamps** -- section 1 assumes distinct timestamps, and real feeds
  carry many messages at the same nanosecond.  Identity is the order id, not the time.
  The cause is the entry below: one incoming order consuming five resting ones writes
  five rows at one timestamp;
* **execution granularity** -- the feed records the execution of each *resting* order, so
  an order that consumes k of them writes k rows where a fold writes one.  Four fifths of
  those are several orders at *one* price, which no sequence of aggregate states
  determines;
* **halts and crosses** -- not ordinary matching at all;
* **asymmetric reporting** -- the feed reports the *resting* side of a fill, so the
  aggressor's direction is ``-d``.  Trade signing, exactly, for free.

The data itself is not in the repository (``data/`` is gitignored), and
``documentation/from-lobster-files-to-a-session.md`` describes the format, the clock and
these edge cases without needing it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from pathlib import Path

import numpy as np
import pandas as pd

from unito26.lob import frames
from unito26.lob.frames import ASK_PADDING, BID_PADDING
from unito26.lob.messages import TICK_TOLERANCE, PriceUnit, ReportedDepth, TickGrid

__all__ = [
    "LOBSTER_UNITS_PER_DOLLAR",
    "NASDAQ_REGULAR_HOURS",
    "LobsterEvent",
    "LobsterFiles",
    "TradingWindow",
    "describe_messages",
    "describe_orderbook",
    "load_aligned",
    "load_messages",
    "load_orderbook",
    "orderbook_columns",
    "price_unit",
    "prices_on_the_tick_grid",
]


class LobsterEvent(IntEnum):
    """LOBSTER's ``type`` column.

    There is no "aggressive order" event.  A trade appears as the execution of the
    resting order it hit, so the aggressor's direction is inferred as ``-direction``.
    """

    SUBMISSION = 1
    PARTIAL_CANCELLATION = 2
    DELETION = 3
    EXECUTION_VISIBLE = 4
    EXECUTION_HIDDEN = 5
    CROSS_TRADE = 6
    TRADING_HALT = 7


#: LOBSTER's price unit: a dollar price times 10000, so \$91.14 is written ``911400``.
LOBSTER_UNITS_PER_DOLLAR = 10000

#: NASDAQ's regular session, 09:30 to 16:00, in seconds after midnight.  A named constant
#: rather than a default: which window a session covers changes what every statistic means,
#: so the caller states it.
NASDAQ_OPEN_SECOND = 34200.0
NASDAQ_CLOSE_SECOND = 57600.0

#: The filename LOBSTER writes, which fixes the reported depth before the file is opened.
_NAME = re.compile(
    r"^(?P<ticker>[A-Z.]+)_(?P<date>\d{4}-\d{2}-\d{2})"
    r"_(?P<start>\d+)_(?P<end>\d+)_(?:message|orderbook)_(?P<depth>\d+)\.csv$"
)


def price_unit(grid: TickGrid) -> PriceUnit:
    """How many of the file's price units make one tick of ``grid``.

    The caller states the tick size, which is a fact about the instrument, and the unit
    follows.  Stating the unit directly invites the magic ``100``, and a wrong one does not
    fail: it rescales every price, spread, mid and sweep cost the session reports, by a
    factor that cancels in any round trip through the same constant.
    """
    units = grid.tick_size * LOBSTER_UNITS_PER_DOLLAR
    if abs(units - round(units)) > TICK_TOLERANCE * LOBSTER_UNITS_PER_DOLLAR:
        raise ValueError(
            f"a tick of {grid.tick_size!r} is {units!r} of LOBSTER's price units, "
            f"which is not a whole number of them"
        )
    return PriceUnit(round(units))


@dataclass(frozen=True, slots=True)
class TradingWindow:
    """The span of a session, in seconds after midnight, closed at both ends.

    A pair of floats in positional order is exactly the swap ``CLAUDE.md`` asks for a type
    to prevent: reversed, it names no rows and yields an empty session rather than an error.
    """

    opens: float
    closes: float

    def __post_init__(self) -> None:
        if not self.opens < self.closes:
            raise ValueError(f"a window opens before it closes, got {self.opens}-{self.closes}")

    def covers(self, other: "TradingWindow") -> bool:
        return self.opens <= other.opens and other.closes <= self.closes


#: NASDAQ's regular session.  Passed explicitly; never a default.
NASDAQ_REGULAR_HOURS = TradingWindow(NASDAQ_OPEN_SECOND, NASDAQ_CLOSE_SECOND)


@dataclass(frozen=True, slots=True)
class LobsterFiles:
    """The pair of files for one ticker and day, named by the convention they are written in.

    Parsed from either member, because the two paths are the same type and are otherwise
    silently swappable, and because ``LEVEL`` in the name *is* the schema: a depth-10 file
    read as depth 50 is a column-count error, and read as depth 5 it is no error at all,
    only a different statistic under the same name.

    The filename counts **milliseconds** after midnight while the ``Time`` column counts
    seconds, which is why the fields are named for what they hold and the seconds are
    derived rather than parsed.
    """

    ticker: str
    day: date
    start_millisecond: int
    end_millisecond: int
    reported_depth: ReportedDepth
    directory: Path

    @classmethod
    def parse(cls, path: str | Path) -> "LobsterFiles":
        path = Path(path)
        matched = _NAME.match(path.name)
        if matched is None:
            raise ValueError(
                f"{path.name!r} is not a LOBSTER file name; expected "
                f"TICKER_YYYY-MM-DD_START_END_message_LEVEL.csv or its orderbook twin"
            )
        return cls(
            ticker=matched["ticker"],
            day=date.fromisoformat(matched["date"]),
            start_millisecond=int(matched["start"]),
            end_millisecond=int(matched["end"]),
            reported_depth=ReportedDepth(int(matched["depth"])),
            directory=path.parent,
        )

    @property
    def span(self) -> TradingWindow:
        """What the file claims to cover, in the seconds its ``Time`` column counts."""
        return TradingWindow(
            self.start_millisecond / 1000, self.end_millisecond / 1000
        )

    def _path(self, kind: str) -> Path:
        return self.directory / (
            f"{self.ticker}_{self.day.isoformat()}_{self.start_millisecond}"
            f"_{self.end_millisecond}_{kind}_{self.reported_depth}.csv"
        )

    @property
    def messages_path(self) -> Path:
        return self._path("message")

    @property
    def orderbook_path(self) -> Path:
        return self._path("orderbook")


def orderbook_columns(reported_depth: ReportedDepth) -> list[str]:
    """Column names for an orderbook file of the given depth.

    Delegates to :func:`unito26.lob.frames.lobster_book_columns`, so a shipped file and a
    frame we wrote carry one vocabulary and a comparison is equality, not translation.
    """
    return frames.lobster_book_columns(reported_depth)


def load_messages(path: str | Path) -> pd.DataFrame:
    """Load a LOBSTER message file, against the schema rather than by inference.

    Prices arrive as integers in units of 1/10000 of a dollar, so the feed already
    counts a fixed grid and no float touches a price.  They are left as they are.

    The clock is read as **text** and turned into two columns.  ``Time`` is the seconds
    the file states, parsed to float64, which the rolling windows subtract whole seconds
    from.  ``TimeNanoseconds`` is the same instant as an exact integer, built by splitting
    the text at the point rather than by scaling the float, and it is the only column
    anything may group on: two rows share an instant far more often than a reader expects,
    and float equality survives that here only because the clock counts from midnight.
    """
    text = pd.read_csv(
        path,
        header=None,
        names=frames.lobster_message_file_columns(),
        dtype={"Time": str, "Type": "int64", "OrderID": "int64",
               "Size": "int64", "Price": "int64", "Direction": "int64"},
    )
    stamps = text["Time"].str.split(".", n=1, expand=True)
    fraction = (
        stamps[1].fillna("") if stamps.shape[1] > 1
        else pd.Series("", index=stamps.index, dtype=str)
    )
    frame = pd.DataFrame(
        {
            "Time": text["Time"].astype(float),
            "TimeNanoseconds": stamps[0].astype("int64") * 1_000_000_000
            + fraction.str.slice(0, 9).str.ljust(9, "0").astype("int64"),
            "Type": text["Type"],
            "OrderID": text["OrderID"],
            "Size": text["Size"],
            "Price": text["Price"],
            "Direction": text["Direction"],
        }
    )
    return frames.lobster_message_schema().validate(frame)


def load_orderbook(path: str | Path, reported_depth: ReportedDepth) -> pd.DataFrame:
    """Load a LOBSTER orderbook file: one snapshot row per message, no timestamp column.

    Padded levels keep their sentinels, exactly as the file has them.  Normalising here
    would hide the one feature of the format most likely to corrupt a statistic.

    The dtypes are declared, not inferred.  Inference agrees with the declaration on every
    shipped file, so this fixes nothing today; what it does is turn a malformed row into an
    exception instead of a silently widened column -- a fractional size, an empty field or
    a non-numeric type each currently changes the dtype of a whole column without comment.
    """
    return _read_orderbook(path, reported_depth, 0, None)


def _read_orderbook(
    path: str | Path, reported_depth: ReportedDepth, skip: int, take: int | None
) -> pd.DataFrame:
    """``take`` rows of the orderbook file starting at data row ``skip``.

    ``names`` is what makes a read at or past the end of the file return an empty frame
    rather than raising for having no columns to parse.
    """
    return frames.lobster_orderbook_file_schema(reported_depth).validate(
        pd.read_csv(
            path,
            header=None,
            names=orderbook_columns(reported_depth),
            dtype="int64",
            skiprows=skip,
            nrows=take,
        )
    )


def _count_rows(path: str | Path) -> int:
    """Rows in a text file, counted without parsing it.

    Half a second and a constant few megabytes on a gigabyte-and-a-half orderbook file,
    which is what makes it worth doing before reading a window out of one.
    """
    rows, last = 0, b"\n"
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 24), b""):
            rows += block.count(b"\n")
            last = block[-1:]
    return rows if last == b"\n" else rows + 1


def prices_on_the_tick_grid(
    book: pd.DataFrame, unit: PriceUnit, reported_depth: ReportedDepth
) -> pd.DataFrame:
    """The book unchanged, or a refusal naming the first price that is not a whole tick.

    Checked once, here, rather than at every conversion.  ``AggregateBook.from_lobster_row``
    already refuses such a price row by row; the frame route divides the whole column and
    would answer a fractional tick count in every spread, mid and sweep cost without
    comment.

    Padded levels are skipped: the sentinels are not prices, and neither of them is a
    multiple of any ordinary unit.
    """
    names = [
        f"{side}Price{level}"
        for level in range(1, reported_depth + 1)
        for side in ("Ask", "Bid")
    ]
    values = book[names].to_numpy()
    quoted = (values != ASK_PADDING) & (values != BID_PADDING)
    off_grid = quoted & (values % unit != 0)
    if off_grid.any():
        row, column = (int(i) for i in np.argwhere(off_grid)[0])
        raise ValueError(
            f"{names[column]} is {values[row, column]} on row {row}, which is not a "
            f"multiple of the price unit {unit}"
        )
    return book


def load_aligned(
    files: LobsterFiles, window: TradingWindow
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The messages and the book states inside ``window``, as one aligned pair.

    The message file is the smaller of the two -- a thirtieth of its orderbook on the
    deepest samples -- and it carries the only clock, so it is read whole and used as the
    index into the other.  Times are non-decreasing, so a window is a contiguous run of
    rows, and only those rows of the orderbook file are parsed.  A five-minute window then
    costs a scan of the text and the memory of the rows it keeps, rather than of the file.

    **Alignment is assumed, not verified.** The orderbook file carries no timestamp, no
    sequence number and no key: row *i* corresponds to message *i* because of how the file
    was written, and nothing in the contents establishes it.  Equal lengths are checked
    here, which catches a file truncated or extended at either end; a row missing from the
    *middle* shifts every state after it and is undetectable by any count.
    """
    if not files.span.covers(window):
        raise ValueError(
            f"{window} is not inside {files.span}, which is what "
            f"{files.messages_path.name} covers"
        )
    messages = load_messages(files.messages_path)
    states = _count_rows(files.orderbook_path)
    if states != len(messages):
        raise ValueError(
            f"the pair is not aligned: {files.messages_path.name} has {len(messages)} "
            f"messages and {files.orderbook_path.name} has {states} book states"
        )

    clock = messages["Time"].to_numpy()
    # Closed at both ends, as LOBSTER's own demo cuts a session.  The sides are stated
    # because timestamps repeat: `right` at the close keeps every message sharing it.
    first = int(np.searchsorted(clock, window.opens, side="left"))
    last = int(np.searchsorted(clock, window.closes, side="right"))
    if first == last:
        raise ValueError(
            f"{window} contains no messages of {files.messages_path.name}, "
            f"whose clock runs {clock[0]} to {clock[-1]}"
        )
    return (
        messages.iloc[first:last].reset_index(drop=True),
        _read_orderbook(files.orderbook_path, files.reported_depth, first, last - first),
    )


def describe_messages(messages: pd.DataFrame) -> dict:
    """Descriptive statistics over the message file.

    The withdrawal rate is the number to read first.  Most posted orders are cancelled
    rather than traded, which is what price-time priority produces: a queue position has
    value, and the cheapest way to hold a good one is to post early and withdraw when the
    market moves.  It is also why removal by name, rather than matching, is the hot path
    in a real book.
    """
    counts = messages["Type"].value_counts().sort_index()
    labelled = {LobsterEvent(int(k)).name: int(v) for k, v in counts.items()}

    submissions = labelled.get("SUBMISSION", 0)
    withdrawals = labelled.get("PARTIAL_CANCELLATION", 0) + labelled.get("DELETION", 0)
    executions = labelled.get("EXECUTION_VISIBLE", 0)
    hidden = labelled.get("EXECUTION_HIDDEN", 0)

    gaps = np.diff(messages["Time"].to_numpy())
    return {
        "messages": len(messages),
        "by_type": labelled,
        "submissions": submissions,
        "withdrawals": withdrawals,
        "executions_visible": executions,
        "executions_hidden": hidden,
        "withdrawal_rate": withdrawals / submissions if submissions else float("nan"),
        "session_seconds": float(messages["Time"].iloc[-1] - messages["Time"].iloc[0]),
        "median_gap_seconds": float(np.median(gaps)),
        "simultaneous_message_fraction": float((gaps == 0).mean()),
    }


def describe_orderbook(book: pd.DataFrame, unit: PriceUnit) -> dict:
    """Descriptive statistics over the shipped orderbook file.

    Every price here is in **ticks**, ``unit`` being how many of the file's price units make
    one -- see :func:`price_unit`, which derives it from a tick size.  Reporting a spread in
    ticks beside a mid in the file's units would put two scales in one dictionary, which is
    the mistake this whole conversion exists to avoid.

    Rows whose touch is padded are dropped first.  The sentinels are ``-9999999999`` on
    the bid and ``+9999999999`` on the ask -- opposite signs, so a filter written for one
    lets the other through, and a single padded row moves a mean spread by 10^8 ticks.
    """
    ask, bid = book["AskPrice1"], book["BidPrice1"]
    quoted = (ask != frames.ASK_PADDING) & (bid != frames.BID_PADDING)
    ask, bid = ask.where(quoted), bid.where(quoted)
    spread = (ask - bid) / unit
    mid = (ask + bid) / 2 / unit
    top = book["BidSize1"] + book["AskSize1"]
    imbalance = (book["BidSize1"] - book["AskSize1"]) / top.where(top > 0)
    return {
        "snapshots": len(book),
        "unquoted_rows": int((~quoted).sum()),
        "spread_ticks_mean": float(spread.mean()),
        "spread_ticks_median": float(spread.median()),
        "one_tick_spread_fraction": float((spread <= 1).mean()),
        "mid_first": float(mid.dropna().iloc[0]),
        "mid_last": float(mid.dropna().iloc[-1]),
        "queue_imbalance_mean": float(imbalance.mean()),
        "crossed_or_locked_rows": int((spread <= 0).sum()),
    }
