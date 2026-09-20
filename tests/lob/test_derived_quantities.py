"""Section 4: the spread, the mid, the micro-price and the imbalance."""

import math

import numpy as np
import pytest

from unito26.lob.messages import GridDepth
from unito26.lob.orderbook import AggregateBook


def crossed_weighted_mid(ask, bid, ask_size, bid_size):
    """P^mu written out directly, sharing no code with the implementation.

    The ask price carries the *bid* size.  This is the only independent witness the
    micro-price has: asserting instead that a bid-heavy book lifts it above the mid is
    tautological once it is implemented as ``P^m + (phi/2) I^1``, since inverting the
    imbalance inverts both sides of that.
    """
    return (ask * bid_size + bid * ask_size) / (ask_size + bid_size)


class TestMicroPrice:
    def test_matches_the_crossed_weighting_on_the_worked_example(self):
        book = AggregateBook.from_levels({1000: 100}, {1002: 120})
        assert book.micro_price == pytest.approx(crossed_weighted_mid(1002, 1000, 120, 100))

    def test_matches_it_on_random_books(self):
        rng = np.random.default_rng(0)
        for _ in range(2000):
            bid = int(rng.integers(100, 10000))
            ask = bid + int(rng.integers(1, 50))
            bid_size, ask_size = (int(rng.integers(1, 10000)) for _ in range(2))
            book = AggregateBook.from_levels({bid: bid_size}, {ask: ask_size})
            # approx, not ==: the identity is exact over the rationals and the two
            # expressions disagree in the last bit for roughly three books in a thousand.
            assert book.micro_price == pytest.approx(
                crossed_weighted_mid(ask, bid, ask_size, bid_size)
            )

    def test_it_sits_toward_the_thin_side(self):
        bid_heavy = AggregateBook.from_levels({100: 900}, {102: 100})
        assert bid_heavy.queue_imbalance(GridDepth(1)) > 0
        assert bid_heavy.micro_price > bid_heavy.mid_price

    def test_it_stays_inside_the_spread(self):
        rng = np.random.default_rng(1)
        for _ in range(500):
            bid = int(rng.integers(100, 1000))
            ask = bid + int(rng.integers(1, 20))
            book = AggregateBook.from_levels(
                {bid: int(rng.integers(1, 500))}, {ask: int(rng.integers(1, 500))}
            )
            assert bid <= book.micro_price <= ask

    def test_it_is_undefined_when_a_side_is_empty(self):
        assert AggregateBook.from_levels({100: 5}, {}).micro_price is None
        assert AggregateBook().micro_price is None


class TestQueueImbalance:
    def test_the_worked_example(self):
        book = AggregateBook.from_levels({1000: 100, 999: 200, 998: 150}, {1002: 120, 1003: 180})
        assert book.queue_imbalance(GridDepth(1)) == pytest.approx((100 - 120) / 220)

    def test_n_counts_grid_positions_not_queues(self):
        """Bids at 100 and 90: at n = 2 the window is {100, 99} and 90 is outside it."""
        book = AggregateBook.from_levels({100: 40, 90: 60}, {101: 10, 102: 20})
        assert book.queue_imbalance(GridDepth(2)) == pytest.approx((40 - 30) / 70)
        # By queue rather than by grid position this would be (100 - 30) / 130.
        assert book.queue_imbalance(GridDepth(2)) != pytest.approx((100 - 30) / 130)

    def test_it_is_strictly_interior_while_both_sides_are_occupied(self):
        rng = np.random.default_rng(2)
        book = AggregateBook.from_levels(
            {1000 - i: int(rng.integers(1, 999)) for i in range(0, 30, 3)},
            {1002 + i: int(rng.integers(1, 999)) for i in range(0, 30, 2)},
        )
        for n in range(1, 40):
            assert -1 < book.queue_imbalance(GridDepth(n)) < 1

    def test_one_empty_side_saturates_it(self):
        assert AggregateBook.from_levels({100: 5}, {}).queue_imbalance(GridDepth(1)) == 1.0
        assert AggregateBook.from_levels({}, {100: 5}).queue_imbalance(GridDepth(1)) == -1.0

    def test_an_empty_book_is_nan_rather_than_a_raise(self):
        assert math.isnan(AggregateBook().queue_imbalance(GridDepth(1)))

    def test_zero_levels_is_refused(self):
        """At n = 0 both windows are empty by the S^{.,j} = 0 convention, so the value
        would be NaN on a perfectly healthy book."""
        book = AggregateBook.from_levels({100: 5}, {102: 5})
        with pytest.raises(ValueError):
            book.queue_imbalance(GridDepth(0))
