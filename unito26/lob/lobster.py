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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from pathlib import Path

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob import frames
from unito26.lob.frames import ASK_PADDING, BID_PADDING
from unito26.lob.messages import TICK_TOLERANCE, PriceUnit, ReportedDepth, TickGrid

__all__ = [
    "clock_census",
    "clock_origin_census",
    "constraint_census",
    "describe_messages",
    "describe_orderbook",
    "event_census",
    "file_census",
    "load_aligned",
    "load_messages",
    "load_orderbook",
    "LOBSTER_UNITS_PER_DOLLAR",
    "LobsterEvent",
    "LobsterFiles",
    "NASDAQ_REGULAR_HOURS",
    "orderbook_columns",
    "padding_census",
    "price_unit",
    "prices_on_the_tick_grid",
    "touch_census",
    "touch_prices",
    "TradingWindow",
    "write_pair",
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


def _clock(path: str | Path) -> np.ndarray:
    """The message file's ``Time`` column and nothing else.

    The clock is the index into the orderbook file, so a reader that wants a window of one
    column of the book still has to know where the window starts.  One column of the
    smaller file is the cheapest way to find out.
    """
    return pd.read_csv(
        path, header=None, usecols=[0], names=["Time"], dtype={"Time": float}
    )["Time"].to_numpy()


def _window_rows(clock: np.ndarray, window: TradingWindow) -> tuple[int, int]:
    """The half-open row range the window covers, both ends of the window closed.

    The sides are stated because timestamps repeat: ``left`` at the open keeps every
    message sharing it, ``right`` at the close does the same.  One AMZN instant carries 31
    messages, and the other pair of sides silently keeps none of them.
    """
    return (
        int(np.searchsorted(clock, window.opens, side="left")),
        int(np.searchsorted(clock, window.closes, side="right")),
    )


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
    first, last = _window_rows(clock, window)
    if first == last:
        raise ValueError(
            f"{window} contains no messages of {files.messages_path.name}, "
            f"whose clock runs {clock[0]} to {clock[-1]}"
        )
    return (
        messages.iloc[first:last].reset_index(drop=True),
        _read_orderbook(files.orderbook_path, files.reported_depth, first, last - first),
    )


# ---- writing a pair, which is how the sample's gaps are filled -------------------------


def write_pair(
    files: LobsterFiles, messages: pd.DataFrame, book: pd.DataFrame
) -> LobsterFiles:
    """Write a message file and an orderbook file: the inverse of :func:`load_aligned`.

    Nothing is validated on the way out, and that is the point.  No shipped sample contains
    a trading halt, a type outside the format or a row missing from the middle, so the file
    that exhibits one has to be constructed, and a writer that refused to write it would be
    useless for exactly the cases worth showing.

    ``Time`` is written with nine decimals, the resolution LOBSTER's own files carry.
    """
    columns = frames.lobster_message_file_columns()
    whole = {name: "int64" for name in columns if name != "Time"}
    messages[columns].astype(whole).to_csv(
        files.messages_path, header=False, index=False, float_format="%.9f"
    )
    book[orderbook_columns(files.reported_depth)].astype("int64").to_csv(
        files.orderbook_path, header=False, index=False
    )
    return files


# ---- the census: what the files say about themselves -----------------------------------
#
# Each function here answers one claim of
# `documentation/from-lobster-files-to-a-session.md`, and each returns a validated frame
# rather than a dictionary.  A census is a table: it prints beside the other tables, and a
# shape declared before the measurement is the discipline the reference argues for.


def file_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Ticker": pa.Column(str, coerce=True),
            "Depth": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "Opens": pa.Column(float, coerce=True),
            "Closes": pa.Column(float, coerce=True),
            "MessageMegabytes": pa.Column(float, coerce=True),
            "OrderbookMegabytes": pa.Column(float, coerce=True),
            "MessageRows": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "BookRows": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Columns": pa.Column("int64", pa.Check.ge(4), coerce=True),
        },
        strict=True,
        ordered=True,
    )


def file_census(pairs: Sequence[LobsterFiles]) -> pd.DataFrame:
    """What the pairs are, before a byte of either is parsed.

    Names, sizes and line counts only.  The two row counts are the thing to read first:
    they agree on every pair, and that agreement is the only evidence for the alignment
    obtainable without parsing, the orderbook file carrying no clock, no sequence number
    and no key.
    """
    return file_census_schema().validate(
        pd.DataFrame(
            [
                {
                    "Ticker": files.ticker,
                    "Depth": int(files.reported_depth),
                    "Opens": files.span.opens,
                    "Closes": files.span.closes,
                    "MessageMegabytes": files.messages_path.stat().st_size / 1e6,
                    "OrderbookMegabytes": files.orderbook_path.stat().st_size / 1e6,
                    "MessageRows": _count_rows(files.messages_path),
                    "BookRows": _count_rows(files.orderbook_path),
                    "Columns": 4 * int(files.reported_depth),
                }
                for files in pairs
            ]
        )
    )


def event_census_schema() -> pa.DataFrameSchema:
    columns = {
        "Ticker": pa.Column(str, coerce=True),
        "Depth": pa.Column("int64", pa.Check.ge(1), coerce=True),
        "Messages": pa.Column("int64", pa.Check.ge(0), coerce=True),
    }
    for event in LobsterEvent:
        columns[event.name] = pa.Column("int64", pa.Check.ge(0), coerce=True)
    return pa.DataFrameSchema(columns, strict=True, ordered=True)


def event_census(pairs: Sequence[LobsterFiles]) -> pd.DataFrame:
    """How many of each event type each message file carries.

    One column per documented type, including the types no sample contains.  The columns
    come from the format and not from the data, which is section 3 of the reference in a
    single table: a schema written from what a file happens to hold inherits that file's
    blind spots.
    """
    rows = []
    for files in pairs:
        messages = load_messages(files.messages_path)
        counts = messages["Type"].value_counts()
        row = {
            "Ticker": files.ticker,
            "Depth": int(files.reported_depth),
            "Messages": len(messages),
        }
        row.update({event.name: int(counts.get(int(event), 0)) for event in LobsterEvent})
        rows.append(row)
    return event_census_schema().validate(pd.DataFrame(rows))


def touch_schema() -> pa.DataFrameSchema:
    """The clock and the two best prices, positionally indexed as the file is."""
    return pa.DataFrameSchema(
        {
            "Time": pa.Column(float, pa.Check.ge(0.0), coerce=True),
            "AskPrice1": pa.Column("int64", coerce=True),
            "BidPrice1": pa.Column("int64", coerce=True),
        },
        strict=True,
        ordered=True,
    )


def touch_prices(files: LobsterFiles, window: TradingWindow) -> pd.DataFrame:
    """The touch, and no other column of the orderbook file.

    ``usecols`` is what makes a claim about the whole sample affordable: the touch is two of
    the file's ``4 x LEVEL`` columns, and reading only those answers every question about
    the spread at a fraction of the memory a full read costs.  The sentinels are left
    intact -- a padded touch is a real answer, and the caller decides what to do with it.
    """
    clock = _clock(files.messages_path)
    first, last = _window_rows(clock, window)
    if first == last:
        raise ValueError(
            f"{window} contains no messages of {files.messages_path.name}, "
            f"whose clock runs {clock[0]} to {clock[-1]}"
        )
    book = pd.read_csv(
        files.orderbook_path,
        header=None,
        names=orderbook_columns(files.reported_depth),
        usecols=["AskPrice1", "BidPrice1"],
        dtype="int64",
        skiprows=first,
        nrows=last - first,
    )
    book.insert(0, "Time", clock[first:last])
    return touch_schema().validate(book.reset_index(drop=True))


def touch_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Ticker": pa.Column(str, coerce=True),
            "Depth": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "Rows": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Unquoted": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Crossed": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Locked": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "NarrowestTicks": pa.Column(float, nullable=True, coerce=True),
            "WidestTicks": pa.Column(float, nullable=True, coerce=True),
        },
        strict=True,
        ordered=True,
    )


def touch_census(
    pairs: Sequence[LobsterFiles], window: TradingWindow, grid: TickGrid
) -> pd.DataFrame:
    """Whether the sample ever crosses or locks, over every row of every pair.

    A crossed book is a bug and a locked one is a market state the format permits; neither
    occurs here.  That is a property of one day, not of the format, and asserting ``spread
    > 0`` in a schema on the strength of it is the mistake section 3 of the reference is
    about.

    Rows whose touch is padded are counted apart rather than filtered silently: the two
    sentinels have opposite signs, and a mean spread taken over them moves by ``10^8``.
    """
    unit = price_unit(grid)
    rows = []
    for files in pairs:
        touch = touch_prices(files, window)
        ask, bid = touch["AskPrice1"].to_numpy(), touch["BidPrice1"].to_numpy()
        quoted = (ask != ASK_PADDING) & (bid != BID_PADDING)
        spread = (ask[quoted] - bid[quoted]) / unit
        rows.append(
            {
                "Ticker": files.ticker,
                "Depth": int(files.reported_depth),
                "Rows": len(touch),
                "Unquoted": int((~quoted).sum()),
                "Crossed": int((spread < 0).sum()),
                "Locked": int((spread == 0).sum()),
                "NarrowestTicks": float(spread.min()) if spread.size else float("nan"),
                "WidestTicks": float(spread.max()) if spread.size else float("nan"),
            }
        )
    return touch_census_schema().validate(pd.DataFrame(rows))


def constraint_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Constraint": pa.Column(str, coerce=True),
            "Rejects": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "RejectedTypes": pa.Column(str, coerce=True),
        },
        strict=True,
        ordered=True,
    )


def constraint_census(messages: pd.DataFrame, unit: PriceUnit) -> pd.DataFrame:
    """What each constraint a reader writes first would throw away.

    Four of the five candidates of section 3; the fifth is about the spread, which is a
    property of the book rather than of a message, and :func:`touch_census` measures it.

    The rejected types are the useful column.  A constraint that rejects nothing here may
    still be wrong -- it encodes an assumption this day happens to satisfy -- and one that
    rejects only hidden executions is saying something about hidden liquidity rather than
    about the format.
    """
    rejected = {
        "OrderID > 0": messages["OrderID"] <= 0,
        "Price >= 0": messages["Price"] < 0,
        f"Price % {unit} == 0": messages["Price"] % unit != 0,
        "Size > 0": messages["Size"] <= 0,
    }
    rows = []
    for constraint, refused in rejected.items():
        types = sorted(messages.loc[refused, "Type"].unique())
        rows.append(
            {
                "Constraint": constraint,
                "Rejects": int(refused.sum()),
                "RejectedTypes": ", ".join(LobsterEvent(int(t)).name for t in types),
            }
        )
    return constraint_census_schema().validate(pd.DataFrame(rows))


def padding_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Side": pa.Column(str, pa.Check.isin(("Ask", "Bid")), coerce=True),
            "Level": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "Rows": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "FirstTime": pa.Column(float, coerce=True),
            "LastTime": pa.Column(float, coerce=True),
        },
        strict=True,
        ordered=True,
    )


#: Rows per chunk when sweeping the price columns of an orderbook file.  Large enough that
#: the per-chunk overhead disappears, small enough that the deepest sample stays in a few
#: hundred megabytes.
PADDING_CHUNK = 1 << 17


def padding_census(files: LobsterFiles, window: TradingWindow) -> pd.DataFrame:
    """Which levels a file pads, how often, and between which times.

    Swept in chunks over the price columns alone.  A full read of the deepest sample peaks
    at several gigabytes, and every question here is answered by ``2 x LEVEL`` of the
    file's ``4 x LEVEL`` columns.

    Only the levels that pad appear, so a file that pads nowhere -- every depth-10 sample --
    answers an empty frame.  That is the claim, not an absence of one.
    """
    clock = _clock(files.messages_path)
    first, last = _window_rows(clock, window)
    prices = [
        f"{side}Price{level}"
        for level in range(1, files.reported_depth + 1)
        for side in ("Ask", "Bid")
    ]
    sentinel = {"Ask": ASK_PADDING, "Bid": BID_PADDING}
    found: dict[str, list[int]] = {}
    offset = 0
    for chunk in pd.read_csv(
        files.orderbook_path,
        header=None,
        names=orderbook_columns(files.reported_depth),
        usecols=prices,
        dtype="int64",
        skiprows=first,
        nrows=last - first,
        chunksize=PADDING_CHUNK,
    ):
        for column in prices:
            padded = np.flatnonzero(chunk[column].to_numpy() == sentinel[column[:3]])
            if not padded.size:
                continue
            seen = found.setdefault(column, [0, offset + int(padded[0]), 0])
            seen[0] += padded.size
            seen[2] = offset + int(padded[-1])
        offset += len(chunk)
    rows = [
        {
            "Side": column[:3],
            "Level": int(column[8:]),
            "Rows": count,
            "FirstTime": float(clock[first + begins]),
            "LastTime": float(clock[first + ends]),
        }
        for column, (count, begins, ends) in found.items()
    ]
    rows.sort(key=lambda row: (row["Side"], row["Level"]))
    return padding_census_schema().validate(
        pd.DataFrame(rows, columns=list(padding_census_schema().columns))
    )


def clock_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Decimals": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Rows": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "Example": pa.Column(str, coerce=True),
        },
        strict=True,
        ordered=True,
    )


def clock_census(path: str | Path) -> pd.DataFrame:
    """How many decimal places the clock carries, counted from the text.

    From the text and never from the parse, because the question is what the file says and
    a float has already answered it.  LOBSTER's ReadMe promises at least milliseconds and up
    to nanoseconds; a sample carries twelve decimals on two rows, finer than the
    documentation admits and finer than the nanosecond key keeps.
    """
    text = pd.read_csv(
        path, header=None, usecols=[0], names=["Time"], dtype={"Time": str}
    )["Time"]
    fraction = text.str.split(".", n=1).str[1].fillna("")
    grouped = pd.DataFrame({"Decimals": fraction.str.len(), "Time": text}).groupby(
        "Decimals"
    )["Time"]
    return clock_census_schema().validate(
        pd.DataFrame(
            {
                "Decimals": grouped.size().index,
                "Rows": grouped.size().to_numpy(),
                "Example": grouped.first().to_numpy(),
            }
        )
    )


def clock_origin_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Origin": pa.Column(str, coerce=True),
            "SpacingNanoseconds": pa.Column(float, coerce=True),
            "ClosestPairNanoseconds": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "DistinctExact": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "DistinctFloat": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "AdjacentCollisions": pa.Column("int64", pa.Check.ge(0), coerce=True),
        },
        strict=True,
        ordered=True,
    )


def clock_origin_census(
    messages: pd.DataFrame, origins: Mapping[str, int]
) -> pd.DataFrame:
    """What the same instants survive, measured from each origin.

    ``origins`` are offsets in **nanoseconds** added to the file's own clock, which counts
    from midnight.  The exact integer is unchanged by the shift; the float64 parse is not,
    and that difference is the measurement.

    The two columns to read against each other are the spacing the parse can represent and
    the closest pair of instants the file actually holds.  From midnight the first is four
    orders of magnitude below the second and nothing can merge.  From the Unix epoch the
    two are comparable, and whether anything merges stops being a property of the format and
    becomes a property of how busy the ticker is: this is why nothing in the package groups
    on anything but ``TimeNanoseconds``.
    """
    exact = messages["TimeNanoseconds"].to_numpy()
    distinct = np.unique(exact)
    apart = np.diff(distinct)
    moved = np.diff(exact) != 0
    rows = []
    for origin, offset in origins.items():
        shifted = (exact + offset).astype(np.float64) / 1e9
        spacing = float(np.spacing(shifted.max())) * 1e9
        rows.append(
            {
                "Origin": origin,
                "SpacingNanoseconds": spacing,
                "ClosestPairNanoseconds": int(apart.min()) if apart.size else 0,
                "DistinctExact": int(distinct.size),
                "DistinctFloat": int(np.unique(shifted).size),
                "AdjacentCollisions": int((moved & (np.diff(shifted) == 0)).sum()),
            }
        )
    return clock_origin_census_schema().validate(pd.DataFrame(rows))


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
