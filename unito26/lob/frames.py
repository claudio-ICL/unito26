"""Schemas, and the round trip between the model objects and validated DataFrames.

The schemas live here rather than on the classes they describe: ``orderbook.py`` is the
file a reader goes to for the book itself, and hanging a validation library off it costs
that reading and buys the book nothing.

Column names are CamelCase throughout -- they are schema keys, not Python identifiers.
The book frame follows LOBSTER's own layout exactly, including its padding sentinels, so
a shipped orderbook file and one we wrote are the same object.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob.hawkes import HawkesParams
from unito26.lob.messages import BUY, SELL, ReportedDepth
from unito26.lob.orderbook import AggregateBook
from unito26.lob.simulate import MarkParams

__all__ = [
    "BID_PADDING",
    "ASK_PADDING",
    "mark_params_schema",
    "mark_params_to_frame",
    "mark_params_from_frame",
    "hawkes_params_schema",
    "hawkes_params_to_frame",
    "hawkes_params_from_frame",
    "lobster_book_schema",
    "lobster_book_columns",
    "book_to_lobster_row",
    "book_from_lobster_row",
    "to_json",
    "from_json",
]

#: What LOBSTER writes where a side holds fewer levels than the file's depth.  The two
#: sentinels have *opposite signs*, so a filter written for one lets the other through --
#: and the corresponding sizes are 0, never null.
BID_PADDING = -9999999999
ASK_PADDING = 9999999999


# ---- parameters -------------------------------------------------------------------


def mark_params_schema() -> pa.DataFrameSchema:
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


def mark_params_to_frame(marks: MarkParams) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "DepthDecay": [float(marks.depth_decay)],
            "MeanLogSize": [float(marks.mean_log_size)],
            "SigmaLogSize": [float(marks.sigma_log_size)],
            "Lot": [marks.lot],
        }
    )
    return mark_params_schema().validate(frame)


def mark_params_from_frame(frame: pd.DataFrame) -> MarkParams:
    frame = mark_params_schema().validate(frame)
    if len(frame) != 1:
        raise ValueError(f"mark parameters are one row, got {len(frame)}")
    row = frame.iloc[0]
    return MarkParams(
        depth_decay=float(row["DepthDecay"]),
        mean_log_size=float(row["MeanLogSize"]),
        sigma_log_size=float(row["SigmaLogSize"]),
        lot=int(row["Lot"]),
    )


def hawkes_params_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Component": pa.Column("Int64", pa.Check.ge(0), coerce=True),
            "Cause": pa.Column("Int64", pa.Check.ge(0), coerce=True),
            "BaseIntensity": pa.Column(float, pa.Check.ge(0.0), nullable=True, coerce=True),
            "Kernel": pa.Column(float, pa.Check.ge(0.0), coerce=True),
            "Decay": pa.Column(float, pa.Check.gt(0.0), coerce=True),
        },
        strict=True,
    )


def hawkes_params_to_frame(params: HawkesParams) -> pd.DataFrame:
    """Long form: one row per ``(Component, Cause)`` pair.

    ``Component`` is the type being excited and ``Cause`` the type exciting it, matching
    ``excitation[i, j]``.  The baseline is a vector, so it sits on the diagonal and is
    null off it; the decay is a scalar and repeats.
    """
    dimension = params.dimension
    index = pd.MultiIndex.from_product(
        [range(dimension), range(dimension)], names=("Component", "Cause")
    )
    baseline = np.full((dimension, dimension), np.nan)
    np.fill_diagonal(baseline, params.baseline)
    frame = pd.DataFrame(
        {
            "BaseIntensity": baseline.flatten(),
            "Kernel": params.excitation.flatten(),
            "Decay": float(params.decay),
        },
        index=index,
    ).reset_index()
    return hawkes_params_schema().validate(frame)


def hawkes_params_from_frame(frame: pd.DataFrame) -> HawkesParams:
    """Rebuild by pivoting on ``(Component, Cause)``.

    Reshaping in row order would silently transpose a frame whose rows arrived in a
    different order, and no schema can constrain row order.
    """
    frame = hawkes_params_schema().validate(frame)
    decays = frame["Decay"].unique()
    if len(decays) != 1:
        raise ValueError(f"the decay is shared by every pair; frame carries {list(decays)}")

    kernel = frame.pivot(index="Component", columns="Cause", values="Kernel")
    dimension = len(kernel)
    if kernel.shape != (dimension, dimension) or kernel.isna().to_numpy().any():
        raise ValueError(f"the (Component, Cause) grid must be complete and square, got {kernel.shape}")

    diagonal = frame[frame["Component"] == frame["Cause"]].sort_values("Component")
    if len(diagonal) != dimension:
        raise ValueError(f"expected {dimension} diagonal rows carrying the baseline, got {len(diagonal)}")
    return HawkesParams(
        baseline=diagonal["BaseIntensity"].to_numpy(dtype=float),
        excitation=kernel.to_numpy(dtype=float),
        decay=float(decays[0]),
    )


def to_json(frame: pd.DataFrame) -> str:
    return frame.to_json()


def from_json(text: str) -> pd.DataFrame:
    """``pd.read_json`` treats a bare string as a path, so the text is wrapped."""
    return pd.read_json(io.StringIO(text))


# ---- the book ---------------------------------------------------------------------


def lobster_book_columns(reported_depth: ReportedDepth) -> list[str]:
    """LOBSTER's own order: ask price, ask size, bid price, bid size, repeated per level."""
    names: list[str] = []
    for level in range(1, reported_depth + 1):
        names += [f"AskPrice{level}", f"AskSize{level}", f"BidPrice{level}", f"BidSize{level}"]
    return names


def lobster_book_schema(reported_depth: ReportedDepth) -> pa.DataFrameSchema:
    """``4 x reported_depth`` integer columns and nothing else.

    No timestamp: a LOBSTER orderbook file carries none, its rows being aligned with the
    message file.  Time belongs on the index.  No nulls either -- a short side is padded
    with the sentinels, exactly as the file does it.
    """
    columns = {}
    for level in range(1, reported_depth + 1):
        columns[f"AskPrice{level}"] = pa.Column("Int64", coerce=True)
        columns[f"AskSize{level}"] = pa.Column("Int64", pa.Check.ge(0), coerce=True)
        columns[f"BidPrice{level}"] = pa.Column("Int64", coerce=True)
        columns[f"BidSize{level}"] = pa.Column("Int64", pa.Check.ge(0), coerce=True)
    return pa.DataFrameSchema(columns, strict=True, ordered=True)


def book_to_lobster_row(
    book: AggregateBook, price_unit: int, reported_depth: ReportedDepth
) -> list[int]:
    """One row of the top ``reported_depth`` **occupied** levels, in file units.

    ``price_unit`` is the number of LOBSTER price units in one tick -- 100 for a penny,
    since LOBSTER quotes dollars times 10000.  It is an integer, unlike
    :class:`~unito26.lob.messages.TickGrid`'s currency ``tick_size``.
    """
    asks = book.occupied_levels(SELL, reported_depth)
    bids = book.occupied_levels(BUY, reported_depth)
    row: list[int] = []
    for level in range(reported_depth):
        ask = asks[level] if level < len(asks) else (None, 0)
        bid = bids[level] if level < len(bids) else (None, 0)
        row += [
            ASK_PADDING if ask[0] is None else ask[0] * price_unit, ask[1],
            BID_PADDING if bid[0] is None else bid[0] * price_unit, bid[1],
        ]
    return row


def book_from_lobster_row(
    book_cls: type[AggregateBook], row, price_unit: int, reported_depth: ReportedDepth
) -> AggregateBook:
    """Inverse of :func:`book_to_lobster_row`, for any rung of the ladder.

    A classmethod-style constructor rather than a method: the band-indexed books must be
    sized from the prices before anything is written into them.
    """
    levels: dict[int, dict[int, int]] = {BUY: {}, SELL: {}}
    for level in range(1, reported_depth + 1):
        for direction, side, padding in ((SELL, "Ask", ASK_PADDING), (BUY, "Bid", BID_PADDING)):
            price = int(row[f"{side}Price{level}"])
            size = int(row[f"{side}Size{level}"])
            if price == padding or size == 0:
                continue
            if price % price_unit:
                raise ValueError(f"price {price} is not a multiple of {price_unit}")
            levels[direction][price // price_unit] = size
    return book_cls.from_levels(levels[BUY], levels[SELL])
