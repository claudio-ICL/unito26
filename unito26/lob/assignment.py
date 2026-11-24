from __future__ import annotations
import numpy as np
import pandas as pd
from unito26.lob import imbalance_regression as ir
from unito26.lob import lobster
from unito26.lob import messages
from unito26.lob import orderbook as ob
from unito26.lob import session


TICK_IN_LOBSTER_UNITS = 100

def implied_depth(slope):
    return 1 / (2 * slope)

def to_message(row):
    time = float(row['Time'])
    event_type = row['Type']
    size = int(row['Size'])
    price = int(row['Price']) // TICK_IN_LOBSTER_UNITS
    direction = int(row['Direction'])
    if event_type == lobster.LobsterEvent.SUBMISSION:
        return messages.Message(time=time, size=size, price=price, direction=direction, kind=messages.MessageType.SUBMIT)
    elif event_type in (lobster.LobsterEvent.PARTIAL_CANCELLATION, lobster.LobsterEvent.DELETION, lobster.LobsterEvent.EXECUTION_VISIBLE):
        return messages.Message(time=time, size=size, price=price, direction=direction, kind=messages.MessageType.WITHDRAW)
    return None

def touch_residual(times, bid_size, ask_size, window, depth):
    start = session.window_start(times, window) - 1
    imbalance = bid_size - ask_size
    eps = np.full(len(times), np.nan)
    ok = start >= 0
    eps[ok] = -(imbalance[ok] - imbalance[start[ok]]) / (2 * depth)
    return eps

def count_mismatches(messages: pd.DataFrame, lobster_book: pd.DataFrame, price_unit: int, depth: int) -> dict:
    if len(messages) != len(lobster_book):
        raise ValueError("len mismatch between msgs and book")

    book = ob.AggregateBook.from_lobster_row(lobster_book.iloc[0], price_unit, depth)
    lobster_rows = lobster_book.to_numpy()

    mismatches = 0
    mismatches_per_level = [0] * depth
    first_mismatch = None

    for i in range(1, len(messages)):
        message = to_message(messages.iloc[i])
        if message is not None:
            book.apply(message, record=False)

        our_row = np.asarray(book.to_lobster_row(price_unit, depth))
        their_row = lobster_rows[i]

        if (our_row != their_row).any():
            mismatches += 1
            if first_mismatch is None:
                first_mismatch = i
            for j in range(depth):
                if (our_row[4*j:4*j+4] != their_row[4*j:4*j+4]).any():
                    mismatches_per_level[j] += 1

    return {
        "rows compared": len(messages) - 1,
        "rows with a mismatch": mismatches,
        "first mismatch": first_mismatch,
        "mismatches per level": mismatches_per_level,
    }


def bucket_pairs(times, predictor, mid, bucket):
    coarse_x = ir.bucket_series(ir.AlignedSeries(times, predictor, mid.segments), ir.Horizon(float(bucket)))
    coarse_mid = ir.bucket_series(mid, ir.Horizon(float(bucket)))
    x = coarse_x.values[:-1]
    move = np.diff(coarse_mid.values)
    adjacent = np.isclose(np.diff(coarse_mid.times), bucket)
    keep = adjacent & np.isfinite(x) & np.isfinite(move)
    return x[keep], move[keep]
