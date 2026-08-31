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
    "FrameSerializable",
    "lobster_book_columns",
    "lobster_book_schema",
    "lobster_padding_row",
]

#: What LOBSTER writes where a side holds fewer levels than the file's depth.  The two
#: sentinels have *opposite signs*, so a filter written for one lets the other through --
#: and the corresponding sizes are 0, never null.
BID_PADDING = -9999999999
ASK_PADDING = 9999999999


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
