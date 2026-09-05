"""Section 4: the sweep cost, the per-share price of taking liquidity.

The identity to hold on to is that a market order which does not walk pays exactly the
half-spread, which is what section 7 assumes; everything beyond that is the distance the
order travels on the price *grid*.  The book with a hole in it is the case that tells the
grid distance apart from a count of queues, and it is the only one here that can.
"""

import numpy as np
import pytest

from unito26.lob.messages import (
    BUY, SELL, GridDepth, ReportedDepth, SweepSize, withdrawal,
)
from unito26.lob.orderbook import AXIS_B_VARIANTS, AggregateBook, _sweep_cost
from unito26.lob.session import MarketSession
from unito26.lob.statistics import SessionStatistics
from unito26.lob.worked_examples import SECTION_8_BOOK, to_sides

DEPTH = ReportedDepth(5)

#: Section 8: bid 10.00 x 100, 9.99 x 200, 9.98 x 150; ask 10.02 x 120, 10.03 x 180.
#: So phi = 2 ticks and the half-spread is 1 tick.
BIDS, ASKS = to_sides(SECTION_8_BOOK)


def section_8(book_cls) -> AggregateBook:
    return book_cls.from_levels(dict(BIDS), dict(ASKS))


def sizes(*values) -> tuple[SweepSize, ...]:
    return tuple(SweepSize(v) for v in values)


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestTheWorkedExample:
    @pytest.mark.parametrize("size", [1, 50, 119, 120])
    def test_an_order_that_does_not_walk_pays_the_half_spread(self, book_cls, size):
        book = section_8(book_cls)
        assert book.sweep_cost(BUY, SweepSize(size), DEPTH) == pytest.approx(book.spread / 2)

    def test_walking_one_level_costs_a_tick_more_on_what_it_walks(self, book_cls):
        # 120 at 10.02 (one tick over the mid) and 120 at 10.03 (two).
        book = section_8(book_cls)
        assert book.sweep_cost(BUY, SweepSize(240), DEPTH) == pytest.approx(1.5)

    def test_it_is_not_exact_in_binary(self, book_cls):
        """1.6 is not representable, so every comparison here needs a tolerance."""
        book = section_8(book_cls)
        assert book.sweep_cost(BUY, SweepSize(300), DEPTH) == pytest.approx(1.6)

    @pytest.mark.parametrize("size", [0, -100])
    def test_a_size_that_is_not_a_number_of_shares_is_refused(self, book_cls, size):
        """Named for what the caller did.  Unscreened, a size of 0 divides by zero and a
        negative one takes nothing anywhere, is deemed filled, and trips the assertion that
        says the book is crossed -- sending the reader to the matching engine."""
        book = section_8(book_cls)
        with pytest.raises(ValueError, match="positive number of shares"):
            book.sweep_cost(BUY, SweepSize(size), DEPTH)

    def test_a_size_the_side_cannot_fill_is_undefined(self, book_cls):
        book = section_8(book_cls)
        assert book.sweep_cost(BUY, SweepSize(301), DEPTH) is None

    def test_the_two_sides_are_symmetric_here(self, book_cls):
        book = section_8(book_cls)
        assert book.sweep_cost(SELL, SweepSize(100), DEPTH) == pytest.approx(book.spread / 2)


class TestTheGridDistanceIsNotTheLevelIndex:
    """Asks at 101 and 110, nothing between: the second queue is nine ticks out.

    A cost read as "one tick per level walked" would answer 1.9.  The order travels nine
    ticks to reach that size, and the whole family of gap statistics exists because a real
    side is not contiguous.
    """

    BOOK = ({99: 40}, {101: 10, 110: 90})

    def test_the_touch_still_costs_the_half_spread(self):
        book = AggregateBook.from_levels(*self.BOOK)
        assert book.sweep_cost(BUY, SweepSize(10), DEPTH) == pytest.approx(book.spread / 2)

    def test_walking_across_a_hole_pays_the_grid_distance(self):
        book = AggregateBook.from_levels(*self.BOOK)
        expected = (10 * 101 + 90 * 110) / 100 - book.mid_price
        assert book.sweep_cost(BUY, SweepSize(100), DEPTH) == pytest.approx(expected)
        assert book.sweep_cost(BUY, SweepSize(100), DEPTH) == pytest.approx(9.1)
        # What counting queues instead of grid positions would have said.
        assert book.sweep_cost(BUY, SweepSize(100), DEPTH) != pytest.approx(1.9)


class TestUndefinedRatherThanWrong:
    def test_a_one_sided_book_has_no_mid_to_price_against(self):
        """The sweep is well defined; the benchmark is not."""
        book = AggregateBook.from_levels({}, {101: 10, 102: 20})
        assert book.sweep_cost(BUY, SweepSize(10), DEPTH) is None

    def test_the_reported_depth_bounds_what_can_be_answered(self):
        book = AggregateBook.from_levels({99: 40}, {101: 10, 102: 20, 103: 30})
        assert book.sweep_cost(BUY, SweepSize(60), ReportedDepth(3)) is not None
        assert book.sweep_cost(BUY, SweepSize(60), ReportedDepth(2)) is None

    def test_the_wrong_side_is_caught_rather_than_costed(self):
        """Handed the side it is not consuming, the walk yields a negative cost.

        Written as ``abs(value / size - mid)`` this would answer 1.0 -- a well-formed tick
        cost, and numerically what a correct buy of 120 answers.  The sign is the only
        thing that tells the two apart.
        """
        book = section_8(AggregateBook)
        asks = book.occupied_levels(SELL, DEPTH)
        with pytest.raises(AssertionError):
            _sweep_cost(asks, book.mid_price, sizes(100), SELL)


class TestProperties:
    def random_book(self, rng) -> AggregateBook:
        bid = int(rng.integers(200, 2000))
        ask = bid + int(rng.integers(1, 8))
        bids = {bid - i: int(rng.integers(1, 500)) for i in range(0, 12, int(rng.integers(1, 3)))}
        asks = {ask + i: int(rng.integers(1, 500)) for i in range(0, 12, int(rng.integers(1, 3)))}
        return AggregateBook.from_levels(bids, asks)

    def test_the_per_share_cost_is_non_decreasing_in_the_size(self):
        rng = np.random.default_rng(0)
        for _ in range(500):
            book = self.random_book(rng)
            for direction in (BUY, SELL):
                costs = [
                    book.sweep_cost(direction, SweepSize(size), ReportedDepth(12))
                    for size in range(10, 400, 30)
                ]
                seen = [c for c in costs if c is not None]
                assert seen == sorted(seen)

    def test_it_starts_at_the_half_spread_and_never_falls_below_it(self):
        rng = np.random.default_rng(1)
        for _ in range(500):
            book = self.random_book(rng)
            for direction in (BUY, SELL):
                cost = book.sweep_cost(direction, SweepSize(1), ReportedDepth(12))
                assert cost == pytest.approx(book.spread / 2)

    def test_one_walk_answers_every_size_as_one_walk_per_size_does(self):
        rng = np.random.default_rng(2)
        for _ in range(500):
            book = self.random_book(rng)
            for direction in (BUY, SELL):
                levels = book.occupied_levels(-direction, ReportedDepth(12))
                asked = sizes(*range(10, 500, 37))
                batched = _sweep_cost(levels, book.mid_price, asked, direction)
                singly = [
                    _sweep_cost(levels, book.mid_price, (size,), direction)[0] for size in asked
                ]
                assert batched == singly

    def test_the_method_agrees_with_the_walk_it_delegates_to(self):
        rng = np.random.default_rng(3)
        for _ in range(200):
            book = self.random_book(rng)
            for direction in (BUY, SELL):
                depth = ReportedDepth(12)
                levels = book.occupied_levels(-direction, depth)
                for size in sizes(1, 90, 400, 5000):
                    assert book.sweep_cost(direction, size, depth) == _sweep_cost(
                        levels, book.mid_price, (size,), direction
                    )[0]


def test_every_rung_of_the_ladder_agrees_with_the_baseline():
    rng = np.random.default_rng(4)
    bids = {1000 - i: int(rng.integers(1, 999)) for i in range(0, 30, 3)}
    asks = {1002 + i: int(rng.integers(1, 999)) for i in range(0, 30, 2)}
    reference = AggregateBook.from_levels(bids, asks)
    depth = ReportedDepth(8)
    for book_cls in AXIS_B_VARIANTS:
        book = book_cls.from_levels(bids, asks)
        for direction in (BUY, SELL):
            for size in sizes(1, 100, 1000, 99999):
                assert book.sweep_cost(direction, size, depth) == reference.sweep_cost(
                    direction, size, depth
                )


class TestWhatTheCoveredFlagPromises:
    """Three outcomes, and the flag separates the two that are answers from the one that
    is not: the sweep filled; it cannot be filled at any price; nothing is known."""

    #: A withdrawal against a level that holds nothing: the fold needs a message, and
    #: this one leaves the book exactly as it was built.
    MESSAGES = [withdrawal(1.0, 1, 500, BUY)]

    def folded(self, bids, asks, size, depth):
        spec = SessionStatistics((GridDepth(1),), (SweepSize(size),), (1,))
        stats = MarketSession.from_occupied_levels(
            AggregateBook.from_levels(bids, asks), self.MESSAGES,
            ReportedDepth(depth), spec, 1, True,
        ).stats
        return (
            stats[f"SweepCostBuy{size}"].iloc[0],
            bool(stats[f"SweepCostBuy{size}Covered"].iloc[0]),
        )

    def test_a_sweep_that_fills_is_covered_and_priced(self):
        cost, covered = self.folded({999: 50}, {1001: 100, 1002: 100}, 150, 2)
        # mid 1000; 100 at 1001 and 50 at 1002, so 1001.333... per share.
        assert covered and cost == pytest.approx((100 * 1001 + 50 * 1002) / 150 - 1000)

    def test_a_side_that_genuinely_runs_out_is_covered_and_unpriced(self):
        """Covered says the frame determines the answer, and the answer is that this size
        cannot be bought.  NaN under a raised flag means exactly that."""
        cost, covered = self.folded({999: 50}, {1001: 100}, 150, 4)
        assert covered and np.isnan(cost)

    def test_a_window_that_merely_ended_is_not_covered(self):
        cost, covered = self.folded({999: 50}, {1001: 100, 1002: 100}, 150, 1)
        assert not covered and np.isnan(cost)

    def test_a_missing_mid_is_not_covered_even_when_the_sweep_fills(self):
        """The liquidity is there; the benchmark is not.  Read off the consumed side
        alone this row looks perfectly determined, which is why the flag also asks
        whether there is a mid to measure against."""
        cost, covered = self.folded({}, {1001: 100, 1002: 100}, 150, 4)
        assert np.isnan(cost)
        assert not covered
