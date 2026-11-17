"""The book replayed from a LOBSTER message file, reconciled with the orderbook file.

Assignment 1, point i.  :mod:`unito26.lob.lobster` loads the pair and states that
reconstructing one file from the other is not attempted there; this module attempts it, on
the aggregate book of :mod:`unito26.lob.orderbook`, and measures where the two disagree.

The replay is seeded from the first orderbook row of the window -- the state after the
first message -- and every later message is applied to it:

* a submission (type 1) is a limit order at its price;
* a partial cancellation, a deletion and a visible execution (types 2, 3, 4) remove size
  at ``(price, direction)``.  ``Direction`` names the side that *rested*, so an execution
  removes from that side, which is the side it is written on;
* a hidden execution, a cross trade and a halt (types 5, 6, 7) move no visible level.

After each message the replayed book is written as an orderbook row and compared with the
file's, level by level.  The comparison runs in one of two modes, chosen by the caller:

``refill=False``
    the messages alone.  The file is read once, for the seed.
``refill=True``
    the messages, plus the one thing the message file cannot carry.  It reports events
    only inside the top ``reported_depth`` occupied levels, so a level resting below them
    comes into view, when a level above empties, carrying size no message ever mentioned.
    Its size is taken from the orderbook file, and from nowhere else, and each such import
    is counted.  The replayed book is cut to ``reported_depth`` levels after every
    message, so a level that falls out of view and later returns is imported afresh rather
    than kept at a size the messages stopped updating.

The difference between the two modes *is* the discrepancy the truncation causes; whatever
remains under ``refill=True`` has some other cause.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob.lobster import LobsterEvent, orderbook_columns
from unito26.lob.messages import (
    BUY, SELL, Message, PriceUnit, ReportedDepth, limit_order, withdrawal,
)
from unito26.lob.orderbook import AggregateBook

__all__ = [
    "as_book_message",
    "discrepancy_census",
    "discrepancy_census_schema",
    "reconcile",
    "reconciliation_schema",
    "repair_log",
    "repair_log_schema",
    "replay",
]

#: Events that remove resting size at the price and on the side the message names.
_REMOVING = (
    LobsterEvent.PARTIAL_CANCELLATION,
    LobsterEvent.DELETION,
    LobsterEvent.EXECUTION_VISIBLE,
)

#: Events that leave every visible level as it was.  On a halt ``Price`` is a status code
#: and a hidden print may be sub-penny, so these are set aside before a price is read.
_INVISIBLE = (
    LobsterEvent.EXECUTION_HIDDEN,
    LobsterEvent.CROSS_TRADE,
    LobsterEvent.TRADING_HALT,
)


def as_book_message(
    kind: int, time: float, size: int, price: int, direction: int, unit: PriceUnit
) -> Message | None:
    """One row of a message file as a message for the aggregate book, or None.

    ``price`` is in the file's units and ``unit`` is how many of them make one tick, as
    :func:`unito26.lob.lobster.price_unit` returns it.  None for the events that move no
    visible level.  A type outside the format, or a visible price off the tick grid, is
    refused rather than rounded: either means the file is not what the replay assumes.
    """
    event = LobsterEvent(int(kind))
    if event in _INVISIBLE:
        return None
    if price % unit:
        raise ValueError(
            f"a {event.name} at {price} is not a multiple of the price unit {unit}"
        )
    ticks = int(price) // unit
    if event is LobsterEvent.SUBMISSION:
        return limit_order(float(time), int(size), ticks, int(direction))
    if event in _REMOVING:
        return withdrawal(float(time), int(size), ticks, int(direction))
    raise ValueError(f"no replay rule for {event.name}")


#: A level the repair forgets or imports: direction, price in ticks, size.
Level = tuple[int, int, int]


def _cut_to_depth(book: AggregateBook, depth: ReportedDepth) -> list[Level]:
    """Remove every level below the first ``depth`` occupied ones, on both sides.

    Returns the levels removed, at the size they had.
    """
    forgotten = []
    for direction in (BUY, SELL):
        levels = book.levels_map(direction)
        if len(levels) <= depth:
            continue  # nothing rests below the first ``depth`` levels: the usual case
        kept = {price for price, _ in book.occupied_levels(direction, depth)}
        for price, size in [(p, s) for p, s in levels.items() if p not in kept]:
            book.set_size(direction, price, 0)
            forgotten.append((direction, price, size))
    return forgotten


def _import_from_below(
    book: AggregateBook, columns: list[str], state: np.ndarray, unit: PriceUnit,
    depth: ReportedDepth,
) -> list[Level]:
    """Copy into ``book`` the levels of the file row lying beyond its deepest one.

    Only on a side holding fewer than ``depth`` levels, and only at prices worse than the
    deepest it holds: everything at or inside that price is the messages' business, and is
    compared rather than copied.  Returns the levels copied.

    ``state`` is the file row and ``columns`` its column names.  Few messages leave a side
    short of ``depth`` levels, so a book is built from the file row only for those.
    """
    short = [d for d in (BUY, SELL) if len(book.levels_map(d)) < depth]
    if not short:
        return []
    shown = AggregateBook.from_lobster_row(dict(zip(columns, state)), unit, depth)
    imported = []
    for direction in short:
        known = book.occupied_levels(direction, depth)
        deepest = known[-1][0] if known else None
        for price, size in shown.occupied_levels(direction, depth):
            beyond = deepest is None or price * direction < deepest * direction
            if beyond and book.size_at(direction, price) == 0:
                book.set_size(direction, price, size)
                imported.append((direction, price, size))
    return imported


def reconciliation_schema() -> pa.DataFrameSchema:
    """One row per replayed file row; ``FirstDifferingLevel`` is 0 where the rows agree."""
    return pa.DataFrameSchema(
        {
            "Row": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "Time": pa.Column(float, coerce=True),
            "Type": pa.Column("int64", pa.Check.isin([int(e) for e in LobsterEvent]),
                              coerce=True),
            "LevelsImported": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "FirstDifferingLevel": pa.Column("int64", pa.Check.ge(0), coerce=True),
        },
        strict=True,
        ordered=True,
    )


def replay(
    messages: pd.DataFrame,
    book: pd.DataFrame,
    unit: PriceUnit,
    depth: ReportedDepth,
    refill: bool,
) -> Iterator[tuple[int, float, int, list[Level], list[Level], AggregateBook, np.ndarray]]:
    """The replay :func:`reconcile` runs, one replayed row at a time.

    Each item is the row's index, time and type, the levels the repair forgot and imported
    after it (both empty when ``refill`` is False), the replayed book after the message, and
    the file's row.  The book is the same :class:`~unito26.lob.orderbook.AggregateBook` at
    every step, changed in place: read what is needed from it before the next item, such as
    ``last_traded_size``, which is positive when the message matched against the book.
    """
    if len(messages) != len(book):
        raise ValueError(
            f"the pair is not aligned: {len(messages)} messages and {len(book)} book states"
        )
    if len(book) < 2:
        raise ValueError("a replay needs a seed row and at least one row to replay")

    columns = orderbook_columns(depth)
    states = book[columns].to_numpy()
    replayed = AggregateBook.from_lobster_row(dict(zip(columns, states[0])), unit, depth)
    stream = zip(
        messages["Time"].to_numpy(), messages["Type"].to_numpy(),
        messages["Size"].to_numpy(), messages["Price"].to_numpy(),
        messages["Direction"].to_numpy(),
    )
    next(stream)  # message 0 produced the seed
    for row, (time, kind, size, price, direction) in enumerate(stream, start=1):
        message = as_book_message(kind, time, size, price, direction, unit)
        if message is not None:
            replayed.apply(message, False)
        forgotten, imported = [], []
        if refill:
            forgotten = _cut_to_depth(replayed, depth)
            imported = _import_from_below(replayed, columns, states[row], unit, depth)
        yield row, float(time), int(kind), forgotten, imported, replayed, states[row]


def reconcile(
    messages: pd.DataFrame,
    book: pd.DataFrame,
    unit: PriceUnit,
    depth: ReportedDepth,
    refill: bool,
) -> pd.DataFrame:
    """Replay ``messages`` from the first row of ``book`` and compare every later row.

    ``messages`` and ``book`` are the aligned pair of
    :func:`unito26.lob.lobster.load_aligned`, as a
    :class:`~unito26.lob.lobster_session.LobsterMarketSession` holds them.  ``refill`` has
    no default because it decides what is being measured; the module docstring says what
    each value means.
    """
    records = []
    for row, time, kind, _, imported, replayed, state in replay(
        messages, book, unit, depth, refill
    ):
        # A row holds four numbers per level, the first level first.
        differing = np.flatnonzero(np.asarray(replayed.to_lobster_row(unit, depth)) != state)
        records.append(
            (row, time, kind, len(imported),
             int(differing[0]) // 4 + 1 if differing.size else 0)
        )
    return reconciliation_schema().validate(
        pd.DataFrame(
            records,
            columns=["Row", "Time", "Type", "LevelsImported", "FirstDifferingLevel"],
        )
    )


def repair_log_schema() -> pa.DataFrameSchema:
    """One row per level the repair forgets or imports, in the order it does so."""
    return pa.DataFrameSchema(
        {
            "Row": pa.Column("int64", pa.Check.ge(1), coerce=True),
            "Action": pa.Column(str, pa.Check.isin(["forget", "import"])),
            "Direction": pa.Column("int64", pa.Check.isin([BUY, SELL]), coerce=True),
            "Price": pa.Column("int64", coerce=True),
            "Size": pa.Column("int64", pa.Check.ge(1), coerce=True),
        },
        strict=True,
        ordered=True,
    )


def repair_log(
    messages: pd.DataFrame, book: pd.DataFrame, unit: PriceUnit, depth: ReportedDepth
) -> pd.DataFrame:
    """The levels the repair of :func:`reconcile` forgets and imports, row by row.

    Prices are in ticks.  A level forgotten is one pushed beyond the reported depth, at the
    size the replay held; a level imported is copied from the file.  An import at a price
    forgotten earlier on the same side is a level returning into view.
    """
    records = [
        (row, action, direction, price, size)
        for row, _, _, forgotten, imported, _, _ in replay(messages, book, unit, depth, True)
        for action, levels in (("forget", forgotten), ("import", imported))
        for direction, price, size in levels
    ]
    return repair_log_schema().validate(
        pd.DataFrame(records, columns=["Row", "Action", "Direction", "Price", "Size"])
    )


def discrepancy_census_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "Event": pa.Column(str, coerce=True),
            "Rows": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "RowsImporting": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "LevelsImported": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "RowsDiffering": pa.Column("int64", pa.Check.ge(0), coerce=True),
            "TouchDiffering": pa.Column("int64", pa.Check.ge(0), coerce=True),
        },
        strict=True,
        ordered=True,
    )


def discrepancy_census(report: pd.DataFrame) -> pd.DataFrame:
    """The report of :func:`reconcile`, counted by event type.

    One row per type the format documents, including those the window does not contain,
    for the reason :func:`unito26.lob.lobster.event_census` gives: a type that never occurs
    is then visibly absent rather than silently missing.  ``TouchDiffering`` counts the
    rows whose first difference is at level 1, where every statistic of the assignment is
    read.
    """
    rows = []
    for event in LobsterEvent:
        of = report[report["Type"] == int(event)]
        rows.append({
            "Event": event.name,
            "Rows": len(of),
            "RowsImporting": int((of["LevelsImported"] > 0).sum()),
            "LevelsImported": int(of["LevelsImported"].sum()),
            "RowsDiffering": int((of["FirstDifferingLevel"] > 0).sum()),
            "TouchDiffering": int((of["FirstDifferingLevel"] == 1).sum()),
        })
    return discrepancy_census_schema().validate(pd.DataFrame(rows))
