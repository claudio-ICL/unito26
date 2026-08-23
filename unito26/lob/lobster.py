"""Reading the LOBSTER sample files -- descriptively, without reconstructing anything.

LOBSTER ships a *message* file and an *orderbook* file for the same session, the second
being the book the first produces.  Rebuilding one from the other is the summit this
strand points at, and it is deliberately **not** attempted here: this module loads the
two files and describes them, which is cheap, motivating, and touches none of the edge
cases that make the reconstruction hard.

Those edge cases are worth knowing even so, because they are what stands between the
ladder's top rung and real data:

* **truncation** -- only events inside the visible price range are reported, so the
  deep levels are unknowable and even the last visible one degrades over the session;
* **pre-existing orders** -- messages reference orders posted before the file begins,
  so the book must be seeded from the first snapshot row, and that seeded volume has
  no identity: a hybrid of aggregate and identified state;
* **hidden liquidity** -- type-5 executions are trades that move no visible level;
* **non-unique timestamps** -- section 1 assumes distinct timestamps, and real feeds
  carry many messages at the same nanosecond.  Identity is the order id, not the time;
* **halts and crosses** -- not ordinary matching at all;
* **asymmetric reporting** -- the feed reports the *resting* side of a fill, so the
  aggressor's direction is ``-d``.  Trade signing, exactly, for free.

The data itself is not in the repository (``data/`` is gitignored).
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path

import numpy as np
import pandas as pd

__all__ = ["LobsterEvent", "MESSAGE_COLUMNS", "load_messages", "load_orderbook",
           "orderbook_columns", "describe_messages", "describe_orderbook"]


class LobsterEvent(IntEnum):
    """LOBSTER's ``type`` column.

    Note what is *absent*: there is no "aggressive order" event.  A trade appears as
    the execution of the resting order it hit, so the aggressor's direction has to be
    inferred -- and here it is exactly ``-direction``.
    """

    SUBMISSION = 1
    PARTIAL_CANCELLATION = 2
    DELETION = 3
    EXECUTION_VISIBLE = 4
    EXECUTION_HIDDEN = 5
    CROSS_TRADE = 6
    TRADING_HALT = 7


MESSAGE_COLUMNS = ["time", "type", "order_id", "size", "price", "direction"]


def orderbook_columns(depth: int) -> list[str]:
    """Column names for an orderbook file of the given depth.

    The layout is ask price, ask size, bid price, bid size, repeated per level -- the
    same order :func:`unito26.lob.replay.lobster_levels` produces, so a future
    comparison is equality rather than translation.
    """
    names: list[str] = []
    for level in range(1, depth + 1):
        names += [
            f"ask_price_{level}",
            f"ask_size_{level}",
            f"bid_price_{level}",
            f"bid_size_{level}",
        ]
    return names


def load_messages(path: str | Path) -> pd.DataFrame:
    """Load a LOBSTER message file.

    Prices arrive as integers in units of 1/10000 of a dollar, which is a gift: the
    feed already counts a fixed grid, so no float ever touches a price.  They are left
    exactly as they are.
    """
    frame = pd.read_csv(path, header=None, names=MESSAGE_COLUMNS)
    frame["type"] = frame["type"].astype("int8")
    frame["direction"] = frame["direction"].astype("int8")
    return frame


def load_orderbook(path: str | Path, depth: int = 10) -> pd.DataFrame:
    """Load a LOBSTER orderbook file: one dense snapshot row per message."""
    return pd.read_csv(path, header=None, names=orderbook_columns(depth))


def describe_messages(messages: pd.DataFrame) -> dict:
    """Descriptive statistics over the message file.

    The headline number is the withdrawal rate.  Most posted orders never trade; they
    are cancelled.  That is not waste, it is what price-time priority produces: a queue
    position is an asset, and the cheapest way to keep a good one is to post early and
    withdraw when the market moves.  It is also why removal-by-name, not matching, is
    the hot path in a real book.
    """
    counts = messages["type"].value_counts().sort_index()
    labelled = {LobsterEvent(int(k)).name: int(v) for k, v in counts.items()}

    submissions = labelled.get("SUBMISSION", 0)
    withdrawals = labelled.get("PARTIAL_CANCELLATION", 0) + labelled.get("DELETION", 0)
    executions = labelled.get("EXECUTION_VISIBLE", 0)
    hidden = labelled.get("EXECUTION_HIDDEN", 0)

    gaps = np.diff(messages["time"].to_numpy())
    return {
        "messages": len(messages),
        "by_type": labelled,
        "submissions": submissions,
        "withdrawals": withdrawals,
        "executions_visible": executions,
        "executions_hidden": hidden,
        "withdrawal_rate": withdrawals / submissions if submissions else float("nan"),
        "session_seconds": float(messages["time"].iloc[-1] - messages["time"].iloc[0]),
        "median_gap_seconds": float(np.median(gaps)),
        "simultaneous_message_fraction": float((gaps == 0).mean()),
    }


def describe_orderbook(book: pd.DataFrame, tick: int = 100) -> dict:
    """Descriptive statistics over the shipped orderbook file.

    ``tick`` is the tick size in the file's own price units: LOBSTER quotes in
    1/10000 of a dollar, so a one-cent tick is 100.
    """
    spread = (book["ask_price_1"] - book["bid_price_1"]) / tick
    mid = (book["ask_price_1"] + book["bid_price_1"]) / 2
    top = book["bid_size_1"] + book["ask_size_1"]
    imbalance = (book["bid_size_1"] - book["ask_size_1"]) / top.where(top > 0)
    return {
        "snapshots": len(book),
        "spread_ticks_mean": float(spread.mean()),
        "spread_ticks_median": float(spread.median()),
        "one_tick_spread_fraction": float((spread <= 1).mean()),
        "mid_first": float(mid.iloc[0]),
        "mid_last": float(mid.iloc[-1]),
        "queue_imbalance_mean": float(imbalance.mean()),
        "crossed_or_locked_rows": int((spread <= 0).sum()),
    }
