"""Reading the LOBSTER sample files -- descriptively, without reconstructing anything.

LOBSTER ships a *message* file and an *orderbook* file for the same session, the second
being the book the first produces.  Reconstructing one from the other is not attempted
here: this module loads the two files and describes them, which touches none of the edge
cases that make the reconstruction hard.

Those edge cases stand between the ladder's top rung and real data:

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

from unito26.lob import frames
from unito26.lob.messages import ReportedDepth

__all__ = ["LobsterEvent", "MESSAGE_COLUMNS", "load_messages", "load_orderbook",
           "orderbook_columns", "describe_messages", "describe_orderbook"]


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


MESSAGE_COLUMNS = ["time", "type", "order_id", "size", "price", "direction"]


def orderbook_columns(reported_depth: ReportedDepth) -> list[str]:
    """Column names for an orderbook file of the given depth.

    Delegates to :func:`unito26.lob.frames.lobster_book_columns`, so a shipped file and a
    frame we wrote carry one vocabulary and a comparison is equality, not translation.
    """
    return frames.lobster_book_columns(reported_depth)


def load_messages(path: str | Path) -> pd.DataFrame:
    """Load a LOBSTER message file.

    Prices arrive as integers in units of 1/10000 of a dollar, so the feed already
    counts a fixed grid and no float touches a price.  They are left as they are.
    """
    frame = pd.read_csv(path, header=None, names=MESSAGE_COLUMNS)
    frame["type"] = frame["type"].astype("int8")
    frame["direction"] = frame["direction"].astype("int8")
    return frame


def load_orderbook(path: str | Path, reported_depth: ReportedDepth) -> pd.DataFrame:
    """Load a LOBSTER orderbook file: one snapshot row per message, no timestamp column.

    Padded levels keep their sentinels, exactly as the file has them.  Normalising here
    would hide the one feature of the format most likely to corrupt a statistic.
    """
    return pd.read_csv(path, header=None, names=orderbook_columns(reported_depth))


def describe_messages(messages: pd.DataFrame) -> dict:
    """Descriptive statistics over the message file.

    The withdrawal rate is the number to read first.  Most posted orders are cancelled
    rather than traded, which is what price-time priority produces: a queue position has
    value, and the cheapest way to hold a good one is to post early and withdraw when the
    market moves.  It is also why removal by name, rather than matching, is the hot path
    in a real book.
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


def describe_orderbook(book: pd.DataFrame, price_unit: int) -> dict:
    """Descriptive statistics over the shipped orderbook file.

    ``price_unit`` is the number of the file's price units in one tick: LOBSTER quotes in
    1/10000 of a dollar, so a one-cent tick is 100.

    Rows whose touch is padded are dropped first.  The sentinels are ``-9999999999`` on
    the bid and ``+9999999999`` on the ask -- opposite signs, so a filter written for one
    lets the other through, and a single padded row moves a mean spread by 10^8 ticks.
    """
    ask, bid = book["AskPrice1"], book["BidPrice1"]
    quoted = (ask != frames.ASK_PADDING) & (bid != frames.BID_PADDING)
    ask, bid = ask.where(quoted), bid.where(quoted)
    spread = (ask - bid) / price_unit
    mid = (ask + bid) / 2
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
