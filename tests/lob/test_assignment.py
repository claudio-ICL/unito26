import numpy as np
import pandas as pd
from unito26.lob.assignment import (
    bucket_pairs,
    count_mismatches,
    implied_depth,
    to_message,
    touch_residual,
)
from unito26.lob.imbalance_regression import AlignedSeries
from unito26.lob.messages import MessageType


def test_to_message():
    sub = pd.Series({"Time": 10.0, "Type": 1, "Size": 100, "Price": 250000, "Direction": 1})
    msg = to_message(sub)
    assert msg is not None
    assert msg.price == 2500
    assert msg.kind == MessageType.SUBMIT

    hidden = pd.Series({"Time": 10.0, "Type": 5, "Size": 100, "Price": 250000, "Direction": 1})
    assert to_message(hidden) is None


def test_implied_depth():
    assert np.isclose(implied_depth(0.05), 10.0)


def test_touch_residual():
    times = np.array([0.0, 1.0, 2.0])
    bid = np.array([100.0, 120.0, 120.0])
    ask = np.array([100.0, 100.0, 90.0])
    res = touch_residual(times, bid, ask, window=1.0, depth=10.0)
    assert np.isnan(res[0])
    assert np.isclose(res[1], -1.0)



def test_bucket_pairs():
    times = np.array([0.5, 1.5, 2.5])
    pred = np.array([1.0, 2.0, 3.0])
    mid = AlignedSeries(times, np.array([100.0, 102.0, 105.0]), np.zeros(3, dtype=int))
    x, move = bucket_pairs(times, pred, mid, bucket=1.0)
    assert np.allclose(x, [1.0, 2.0])
    assert np.allclose(move, [2.0, 3.0])


def test_count_mismatches():
    msgs = pd.DataFrame([
        {"Time": 1.0, "Type": 1, "Size": 100, "Price": 10000, "Direction": 1},
        {"Time": 2.0, "Type": 1, "Size": 200, "Price": 10000, "Direction": 1},
    ])
    book = pd.DataFrame([
        {"AskPrice1": 10100, "AskSize1": 100, "BidPrice1": 10000, "BidSize1": 100},
        {"AskPrice1": 10100, "AskSize1": 100, "BidPrice1": 10000, "BidSize1": 300},
    ])
    out = count_mismatches(msgs, book, price_unit=100, depth=1)
    assert out["rows compared"] == 1
    assert out["rows with a mismatch"] == 0
    
