"""The frame side of the package: the serialization protocol, and LOBSTER's vocabulary.

A serializable model object owns its own schema and its own conversions; what lives here
is what belongs to no single class.  :class:`FrameSerializable` fixes the protocol they
implement and writes the record and JSON forms once.  The sentinels and the column names
are LOBSTER's, shared by the book, the session and the file loader.

Column names are CamelCase throughout: they are schema keys, not Python identifiers.  The
book frame follows LOBSTER's layout exactly, padding sentinels included, so a shipped
orderbook file and one we wrote are the same object.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob.messages import ReportedDepth

__all__ = [
    "BID_PADDING",
    "ASK_PADDING",
    "LOBSTER_EVENT_TYPES",
    "FrameSerializable",
    "lobster_book_columns",
    "lobster_book_schema",
    "lobster_message_file_columns",
    "lobster_message_schema",
    "lobster_orderbook_file_schema",
    "lobster_padding_row",
    "positional_index",
    "session_book_schema",
    "session_index",
]

#: What LOBSTER writes where a side holds fewer levels than the file's depth.  The two
#: sentinels have *opposite signs*, so a filter written for one lets the other through --
#: and the corresponding sizes are 0, never null.
BID_PADDING = -9999999999
ASK_PADDING = 9999999999

#: The event types a message file may carry.  1, 2, 3, 4, 5 and 7 are the sample ReadMe's;
#: 6 is not documented there and is admitted because ``lobster.LobsterEvent`` names it.
LOBSTER_EVENT_TYPES = (1, 2, 3, 4, 5, 6, 7)


def _plain(value):
    """A pandas cell as a plain Python scalar, with every flavour of null as ``None``."""
    if value is None or (not isinstance(value, (list, tuple)) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


class FrameSerializable(ABC):
    """A model object with one canonical DataFrame form.

    A subclass supplies three things -- the schema, and the two conversions.  The record
    and JSON forms follow from those and are written once, here, so that every
    parametrization in the package is stored and read the same way.

    Records are the storage form: a list of one dict per frame row, keyed by schema
    column, holding plain Python scalars with ``None`` for a null.  A frozen example is
    written in a source file as a record list, which stays readable and stays diffable.
    """

    __slots__ = ()

    @classmethod
    @abstractmethod
    def schema(cls) -> pa.DataFrameSchema:
        """The pandera schema every frame form of this class validates against."""

    @abstractmethod
    def to_frame(self) -> pd.DataFrame:
        """This object as a validated frame."""

    @classmethod
    @abstractmethod
    def from_frame(cls, frame: pd.DataFrame) -> "FrameSerializable":
        """Rebuild from a frame, validating it first."""

    def to_records(self) -> list[dict]:
        return [
            {column: _plain(value) for column, value in row.items()}
            for row in self.to_frame().to_dict("records")
        ]

    @classmethod
    def from_records(cls, records: list[dict]) -> "FrameSerializable":
        return cls.from_frame(pd.DataFrame(records))

    def to_json(self, indent: int) -> str:
        return json.dumps(self.to_records(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "FrameSerializable":
        return cls.from_records(json.loads(text))

    @classmethod
    def read_json(cls, path) -> "FrameSerializable":
        with open(path, encoding="utf-8") as handle:
            return cls.from_records(json.load(handle))

    def write_json(self, path, indent: int) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.to_json(indent))


# ---- the book frame ----------------------------------------------------------------


def lobster_book_columns(reported_depth: ReportedDepth) -> list[str]:
    """LOBSTER's own order: ask price, ask size, bid price, bid size, repeated per level."""
    names: list[str] = []
    for level in range(1, reported_depth + 1):
        names += [f"AskPrice{level}", f"AskSize{level}", f"BidPrice{level}", f"BidSize{level}"]
    return names


def lobster_padding_row(reported_depth: ReportedDepth) -> np.ndarray:
    """One row of a LOBSTER book holding nothing: every level padded, on both sides.

    This is what a row *means* before anything is written into it, so a recorder that
    writes only the levels a book actually has can lay this down first and leave the rest
    alone.  The strides are the file's own layout -- ask price, ask size, bid price, bid
    size, repeated -- so they are stated once, here, beside the columns they name.
    """
    row = np.empty(4 * reported_depth, dtype=np.int64)
    row[0::4] = ASK_PADDING
    row[1::4] = 0
    row[2::4] = BID_PADDING
    row[3::4] = 0
    return row


def lobster_book_schema(reported_depth: ReportedDepth) -> pa.DataFrameSchema:
    """``4 x reported_depth`` integer columns and nothing else.

    No timestamp: a LOBSTER orderbook file carries none, its rows being aligned with the
    message file.  Time belongs on the index.  No nulls either -- a short side is padded
    with the sentinels, as the file does it.
    """
    columns = {}
    for level in range(1, reported_depth + 1):
        columns[f"AskPrice{level}"] = pa.Column("Int64", coerce=True)
        columns[f"AskSize{level}"] = pa.Column("Int64", pa.Check.ge(0), coerce=True)
        columns[f"BidPrice{level}"] = pa.Column("Int64", coerce=True)
        columns[f"BidSize{level}"] = pa.Column("Int64", pa.Check.ge(0), coerce=True)
    return pa.DataFrameSchema(columns, strict=True, ordered=True)


def _book_columns(reported_depth: ReportedDepth, dtype) -> dict:
    columns = {}
    for level in range(1, reported_depth + 1):
        columns[f"AskPrice{level}"] = pa.Column(dtype, coerce=True)
        columns[f"AskSize{level}"] = pa.Column(dtype, pa.Check.ge(0), coerce=True)
        columns[f"BidPrice{level}"] = pa.Column(dtype, coerce=True)
        columns[f"BidSize{level}"] = pa.Column(dtype, pa.Check.ge(0), coerce=True)
    return columns


def session_index() -> pa.Index:
    """The clock every assembled session frame is indexed by.

    Non-decreasing rather than increasing, and explicitly **not unique**.  A LOBSTER
    session repeats a timestamp on 3% of its rows, because one incoming order consuming
    several resting ones writes one row per resting order at a single instant, and a
    uniqueness constraint here would reject the file.  See
    ``documentation/from-lobster-files-to-a-session.md``.
    """
    return pa.Index(
        float,
        pa.Check(
            lambda stamps: bool(stamps.is_monotonic_increasing),
            error="times must be non-decreasing to window over them",
        ),
        name="TimeStamp",
        unique=False,
    )


def positional_index() -> pa.Index:
    """The index of a frame that is rows of a file: 0, 1, 2, and nothing further.

    Declared rather than omitted.  A schema with no ``index`` validates *any* index, so
    leaving it out does not say "positional", it says "unchecked": a clocked session frame
    passes a file schema that is silent about its index, and the two shapes this package
    exists to keep apart would meet without a word.
    """
    return pa.Index(
        "int64",
        pa.Check(
            lambda rows: bool(rows.is_monotonic_increasing),
            error="a frame of file rows is indexed by position",
        ),
        name=None,
        unique=True,
    )


def session_book_schema(reported_depth: ReportedDepth) -> pa.DataFrameSchema:
    """The book frame a session holds: the columns above, on the session clock.

    Distinct from :func:`lobster_book_schema` only in the index, which is the difference
    that matters: the same columns off a file carry a positional index and mean rows of a
    file, and these mean states of a book at a time.
    """
    return pa.DataFrameSchema(
        _book_columns(reported_depth, "Int64"),
        index=session_index(),
        strict=True,
        ordered=True,
    )


def lobster_orderbook_file_schema(reported_depth: ReportedDepth) -> pa.DataFrameSchema:
    """A frame read straight from an orderbook file: positional index, plain ``int64``.

    ``int64`` and not the nullable ``Int64`` of the session frame.  A file has no nulls by
    construction -- that is what the padding sentinels are for -- and coercing to the
    extension dtype replaces one contiguous integer block with one masked column per field,
    which on a file-sized frame costs more memory than reading only the rows wanted saves.
    """
    return pa.DataFrameSchema(
        _book_columns(reported_depth, "int64"),
        index=positional_index(),
        strict=True,
        ordered=True,
    )


def lobster_message_file_columns() -> list[str]:
    """The six columns a message file carries, in its order."""
    return ["Time", "Type", "OrderID", "Size", "Price", "Direction"]


def lobster_message_schema() -> pa.DataFrameSchema:
    """A message file, plus the exact clock derived from its text.

    Three constraints a reader expects are missing, and their absence cannot be read off
    the code, so it is stated here.  ``OrderID`` is unconstrained: a hidden execution
    carries no order id and writes 0, as does every trading halt.  ``Price`` reaches down
    to -1 because on a type-7 halt the column is not a price at all but a status code,
    -1, 0 or 1 for halted, quoting resumed and trading resumed.  ``Size`` admits 0 for the
    same reason, a bound no shipped sample exercises.

    ``Type`` and ``Direction`` are ``int64`` rather than a narrow width on purpose.  A
    narrow integer *launders* corruption instead of catching it: read as ``int8``, a
    ``Type`` of 260 wraps to 4 -- a valid visible execution -- and the membership check
    below then passes it.

    ``TimeNanoseconds`` is the key, and the only column anything may group or join on.
    ``Time`` is the coordinate the rolling windows do arithmetic on.  They are separate
    because equality on the float is safe only for a clock counted from midnight; see
    ``documentation/from-lobster-files-to-a-session.md``.
    """
    return pa.DataFrameSchema(
        {
            "Time": pa.Column(float, pa.Check.ge(0.0), coerce=True),
            "TimeNanoseconds": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Type": pa.Column("int64", pa.Check.isin(LOBSTER_EVENT_TYPES), coerce=True),
            "OrderID": pa.Column("int64", coerce=True),
            "Size": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "Price": pa.Column("int64", pa.Check.ge(-1), coerce=True),
            "Direction": pa.Column("int64", pa.Check.isin((-1, 1)), coerce=True),
        },
        index=positional_index(),
        strict=True,
        ordered=True,
    )
