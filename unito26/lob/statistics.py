"""Which statistics a session records, and the shape of the frames that hold them.

A :class:`SessionStatistics` is three parametrizations of one fold -- grid levels, shares,
seconds -- and everything about the frames follows from them: what the columns are called,
what order they sit in, which of them are coverage flags, and where the fold writes each
one.  All four are read off a single declaration, so they cannot drift apart.

That matters more than it looks.  The fold writes a row by position, into a buffer sized
from the declaration; the rolling reduction reads the same positions back by name; and
``stats_from_frame`` builds the same columns from a dict and reorders them.  Four readings
of one order.
"""

from __future__ import annotations

import numbers
from dataclasses import dataclass, field

import pandera.pandas as pa

from unito26.lob.messages import GridDepth, SweepSize

__all__ = ["StatisticColumn", "RowLayout", "SessionStatistics"]

#: The gap statistics, which are the same for every session.  Last in a statistics row,
#: because ``_write_statistics`` fills them with one slice assignment from the tail.
GAP_COLUMNS = [
    "BidOccupiedLevels", "AskOccupiedLevels",
    "BidGapCount", "AskGapCount",
    "BidLargestGap", "AskLargestGap",
    "BidFirstGapDistance", "AskFirstGapDistance",
    "BidFirstGapSize", "AskFirstGapSize",
    "BidLargestGapDistance", "AskLargestGapDistance",
]


def _whole(name: str, value) -> int:
    """``value`` as a count of whole things -- grid levels, shares or seconds.

    ``numbers.Integral`` rather than ``isinstance(value, int)``: a count read off a frame is
    a numpy integer and belongs here, and a float that happens to be whole does not.  The
    float is the one that matters, because it reaches the column names -- a window of 0.5
    names ``OFI0.5``, where the dot defeats ``DataFrame.query`` and attribute access, and two
    windows differing below ``%g`` precision name one column and return a frame short of what
    was asked for.
    """
    if not isinstance(value, numbers.Integral) or value < 1:
        raise ValueError(f"{name} must be a whole number of at least 1, got {value!r}")
    return int(value)


@dataclass(frozen=True, slots=True)
class StatisticColumn:
    """One column of a statistics frame, and whether it is a coverage flag.

    The flag is a field rather than a suffix on the name.  Every coverage column happens to
    end in ``Covered``, but a name is not a type: reading the kind of a column out of its
    spelling makes the schema depend on a convention nothing enforces.
    """

    name: str
    covered: bool

    def column(self) -> pa.Column:
        """A flag is 0 or 1 and always determined; a value may be NaN where it is not."""
        if self.covered:
            return pa.Column(float, pa.Check.isin((0.0, 1.0)), coerce=True)
        return pa.Column(float, nullable=True, coerce=True)


def _value(name: str) -> StatisticColumn:
    return StatisticColumn(name, False)


def _flag(name: str) -> StatisticColumn:
    return StatisticColumn(name, True)


def _schema(declaration: tuple[StatisticColumn, ...]) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {column.name: column.column() for column in declaration}, strict=True, ordered=True
    )


@dataclass(frozen=True, slots=True)
class RowLayout:
    """Where the fold writes each statistic in a row.

    Every offset is found by *name* in the declaration, so the writer's positions and the
    schema's column order are one statement rather than two.  A flag sits immediately after
    the value it qualifies, which is the one convention the writer still relies on and the
    only one the declaration states in a single place.

    Computed once per specification, never per message: the fold's inner loop indexes with
    these integers and does no lookup of its own.
    """

    spread: int
    mid_price: int
    micro_price: int
    imbalance: tuple[int, ...]
    """One offset per imbalance level, in specification order."""
    sweep: tuple[tuple[int, int], ...]
    """One ``(buy, sell)`` pair of offsets per sweep size, in specification order."""
    order_flow: int
    touch_depth: int
    gaps: slice


@dataclass(frozen=True, slots=True)
class SessionStatistics:
    """Which statistics a session records, and what their columns are called.

    Three parametrizations of one fold, which is why they travel together.  They count
    different things -- grid levels, shares, seconds -- and the types say so.

    Each tuple is sorted and de-duplicated on construction.  Sorting ``sweep_sizes`` is
    what lets one walk of a side answer every size; de-duplicating is what makes two
    columns of the same name impossible rather than merely unlikely.

    ``windows`` are **integer** seconds.  A float window would name a column ``OFI0.5``,
    where the dot defeats ``DataFrame.query`` and attribute access, and ``1e6`` would name
    ``OFI1e+06``; two windows differing below ``%g`` precision would name one column and
    the frame would come back a column short.  Cont, Kukanov and Stoikov bucket in whole
    seconds, so nothing is lost by refusing the rest.
    """

    imbalance_levels: tuple[GridDepth, ...]
    """``n`` for each ``I^n``: positions on the price grid, in the sense of section 3."""

    sweep_sizes: tuple[SweepSize, ...]
    """``Q`` for each sweep cost: shares a hypothetical market order asks for."""

    windows: tuple[int, ...]
    """``w`` for each rolling statistic, in whole seconds."""

    layout: RowLayout = field(init=False, repr=False, compare=False)
    """Where the fold writes each statistic.  Derived, so it is not part of the identity."""

    def __post_init__(self) -> None:
        for name in ("imbalance_levels", "sweep_sizes", "windows"):
            values = {_whole(name, value) for value in getattr(self, name)}
            object.__setattr__(self, name, tuple(sorted(values)))
        object.__setattr__(self, "layout", self._layout())

    # ---- the declarations ------------------------------------------------------------
    #
    # The order here is the order the fold writes, the order the schemas declare and the
    # order `RowLayout` reads.  Nothing else states it.

    def row_declaration(self) -> tuple[StatisticColumn, ...]:
        """The statistics written per message, in buffer order.

        Separate from :meth:`declaration` because the rolling statistics are a reduction
        over a recorded series and are made once, at assembly.  A single list would leave
        them carrying the buffer's zero background, and would put unwritten columns in the
        middle of the row that ``_write_statistics`` fills by slice.
        """
        columns = [_value("Spread"), _value("MidPrice"), _value("MicroPrice")]
        for n in self.imbalance_levels:
            columns += [_value(f"QueueImbalance{n}"), _flag(f"QueueImbalance{n}Covered")]
        for size in self.sweep_sizes:
            for side in ("Buy", "Sell"):
                columns += [
                    _value(f"SweepCost{side}{size}"), _flag(f"SweepCost{side}{size}Covered")
                ]
        columns += [_value("OrderFlowContribution"), _value("TouchDepth")]
        return tuple(columns + [_value(name) for name in GAP_COLUMNS])

    def declaration(self) -> tuple[StatisticColumn, ...]:
        """Every column of the statistics frame: the rows above plus the rolling ones."""
        columns = list(self.row_declaration())
        for w in self.windows:
            columns += [
                _value(f"OrderFlowImbalance{w}"),
                _flag(f"OrderFlowImbalance{w}Covered"),
                _value(f"AverageDepth{w}"),
            ]
        return tuple(columns)

    def trade_row_declaration(self) -> tuple[StatisticColumn, ...]:
        """What the fold records about the trades, per message."""
        return tuple(_value(name) for name in ("Volume", "SignedVolume", "TradedValue"))

    def trade_declaration(self) -> tuple[StatisticColumn, ...]:
        """Every column of the trades frame."""
        columns = list(self.trade_row_declaration())
        for w in self.windows:
            columns += [_value(f"VWAP{w}"), _value(f"VWAPBuy{w}"), _value(f"VWAPSell{w}")]
        return tuple(columns)

    # ---- the schemas -----------------------------------------------------------------

    def row_schema(self) -> pa.DataFrameSchema:
        return _schema(self.row_declaration())

    def statistics_schema(self) -> pa.DataFrameSchema:
        return _schema(self.declaration())

    def trade_row_schema(self) -> pa.DataFrameSchema:
        return _schema(self.trade_row_declaration())

    def trades_schema(self) -> pa.DataFrameSchema:
        return _schema(self.trade_declaration())

    def _layout(self) -> RowLayout:
        names = [column.name for column in self.row_declaration()]
        return RowLayout(
            spread=names.index("Spread"),
            mid_price=names.index("MidPrice"),
            micro_price=names.index("MicroPrice"),
            imbalance=tuple(
                names.index(f"QueueImbalance{n}") for n in self.imbalance_levels
            ),
            sweep=tuple(
                (names.index(f"SweepCostBuy{size}"), names.index(f"SweepCostSell{size}"))
                for size in self.sweep_sizes
            ),
            order_flow=names.index("OrderFlowContribution"),
            touch_depth=names.index("TouchDepth"),
            gaps=slice(names.index(GAP_COLUMNS[0]), names.index(GAP_COLUMNS[-1]) + 1),
        )
