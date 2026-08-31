"""Occupied levels, the holes between them, and the span they cover.

Every assertion runs on all five rungs: the dict books walk sorted keys, the bitmap books
read the answer off an integer, and the whole point is that they cannot disagree.
"""

import pytest

from unito26.lob.messages import BUY, SELL, ReportedDepth
from unito26.lob.orderbook import AXIS_B_VARIANTS

#: The stub's example, written the way `occupied_levels` returns it: (price, volume).
LADDER_BIDS = {100: 25, 99: 50, 97: 50, 96: 150, 93: 200}


@pytest.fixture(params=AXIS_B_VARIANTS, ids=lambda c: c.__name__)
def book_cls(request):
    return request.param


class TestTheWorkedLadder:
    """Bids at 100, 99, 97, 96, 93: grid levels 1, 2, 4, 5, 8 are filled."""

    @pytest.fixture
    def book(self, book_cls):
        return book_cls.from_levels(LADDER_BIDS, {110: 10})

    def test_occupied_levels_come_back_best_first(self, book):
        assert book.occupied_levels(BUY, ReportedDepth(5)) == [
            (100, 25), (99, 50), (97, 50), (96, 150), (93, 200)
        ]

    def test_the_holes_are_grid_indices(self, book):
        assert book.empty_grid_positions(BUY, ReportedDepth(5)) == [3, 6, 7]

    def test_gap_count_counts_runs_not_positions(self, book):
        assert book.gap_count(BUY, ReportedDepth(5)) == 2
        assert len(book.empty_grid_positions(BUY, ReportedDepth(5))) == 3

    def test_largest_gap(self, book):
        assert book.largest_gap_size_between_non_empty_levels(BUY, ReportedDepth(5)) == 2

    def test_span(self, book):
        assert book.grid_span(BUY, ReportedDepth(5)) == 8

    def test_a_shallower_read_sees_a_shorter_span(self, book):
        # Only 100, 99, 97 are reported, so the span stops there and 93 is invisible.
        assert book.grid_span(BUY, ReportedDepth(3)) == 4
        assert book.empty_grid_positions(BUY, ReportedDepth(3)) == [3]


class TestCaseB:
    """Section 8 case B leaves asks at 999, 1002, 1003: two interior holes."""

    @pytest.fixture
    def book(self, book_cls):
        return book_cls.from_levels({998: 150}, {999: 100, 1002: 120, 1003: 180})

    def test_the_holes_sit_above_the_residual(self, book):
        assert book.empty_grid_positions(SELL, ReportedDepth(3)) == [2, 3]
        assert book.gap_count(SELL, ReportedDepth(3)) == 1
        assert book.largest_gap_size_between_non_empty_levels(SELL, ReportedDepth(3)) == 2
        assert book.grid_span(SELL, ReportedDepth(3)) == 5

    def test_a_side_with_one_level_has_no_gaps(self, book):
        assert book.empty_grid_positions(BUY, ReportedDepth(3)) == []
        assert book.grid_span(BUY, ReportedDepth(3)) == 1


class TestBoundaries:
    def test_an_empty_side_reports_nothing(self, book_cls):
        book = book_cls.from_levels({}, {1002: 120})
        assert book.occupied_levels(BUY, ReportedDepth(5)) == []
        assert book.grid_span(BUY, ReportedDepth(5)) == 0
        assert book.empty_grid_positions(BUY, ReportedDepth(5)) == []

    def test_contiguous_levels_have_no_holes(self, book_cls):
        book = book_cls.from_levels({100: 1, 99: 1, 98: 1}, {110: 1})
        assert book.empty_grid_positions(BUY, ReportedDepth(3)) == []
        assert book.gap_count(BUY, ReportedDepth(3)) == 0
        assert book.grid_span(BUY, ReportedDepth(3)) == 3

    def test_depth_must_be_positive(self, book_cls):
        book = book_cls.from_levels(LADDER_BIDS, {110: 10})
        with pytest.raises(ValueError):
            book.occupied_levels(BUY, ReportedDepth(0))

    @pytest.mark.parametrize("depth", [1, 2, 3, 4, 5])
    def test_holes_are_strictly_interior(self, book_cls, depth):
        book = book_cls.from_levels(LADDER_BIDS, {110: 10})
        holes = book.empty_grid_positions(BUY, ReportedDepth(depth))
        span = book.grid_span(BUY, ReportedDepth(depth))
        assert all(1 < hole < span for hole in holes)


class TestTheBatchedRead:
    """`side_statistics` is what the session fold uses: every number from one walk of the
    side rather than one walk per number."""

    @pytest.mark.parametrize(
        "bids,asks,depth",
        [
            (LADDER_BIDS, {110: 10}, 5),
            (LADDER_BIDS, {110: 10}, 3),
            ({998: 150}, {999: 100, 1002: 120, 1003: 180}, 3),
            ({100: 5}, {110: 8}, 4),
            ({}, {110: 8}, 2),
            ({100: 5}, {}, 2),
        ],
    )
    def test_it_agrees_with_the_individual_methods(self, book_cls, bids, asks, depth):
        depth = ReportedDepth(depth)
        book = book_cls.from_levels(bids, asks)
        for direction in (BUY, SELL):
            batched = book.side_statistics(direction, depth)
            assert batched.levels == book.occupied_levels(direction, depth)
            assert batched.occupied == book.occupied_level_count(direction, depth)
            assert batched.grid_span == book.grid_span(direction, depth)
            assert batched.gap_count == book.gap_count(direction, depth)
            assert batched.largest_gap == book.largest_gap_size_between_non_empty_levels(
                direction, depth
            )
            assert batched.first_gap_size == book.first_gap_size(direction, depth)
            assert batched.first_gap_distance == book.first_gap_distance(direction, depth)
            assert batched.largest_gap_distance == book.largest_gap_distance(
                direction, depth
            )


class TestWhereTheGapsAre:
    """The three statistics that say *where* the holes sit, not just how many.

    A distance is measured to the empty position, so grid position ``i`` lies ``i - 1``
    ticks from the touch; a side with no gap answers NaN, because there is no position to
    name and zero would name the touch, which is always occupied.
    """

    def read(self, book_cls, bids, depth=8):
        book = book_cls.from_levels(bids, {200: 10})
        return book.side_statistics(BUY, ReportedDepth(depth))

    def test_a_contiguous_side_has_no_gap_to_place(self, book_cls):
        side = self.read(book_cls, {100: 5, 99: 5, 98: 5})
        assert side.gap_count == 0
        assert side.first_gap_size == 0 and side.largest_gap == 0
        assert side.first_gap_distance is None
        assert side.largest_gap_distance is None

    def test_one_gap_is_measured_from_the_touch(self, book_cls):
        # 100, 99, then 97: grid position 3 is empty, one level, two ticks down.
        side = self.read(book_cls, {100: 5, 99: 5, 97: 5})
        assert (side.gap_count, side.first_gap_size, side.largest_gap) == (1, 1, 1)
        assert side.first_gap_distance == 2.0
        assert side.largest_gap_distance == 2.0

    def test_the_nearest_gap_is_not_always_the_largest(self, book_cls):
        # 99 empty (one tick down), then 97, 96, 95 empty (three ticks down).
        side = self.read(book_cls, {100: 5, 98: 5, 94: 5})
        assert side.gap_count == 2
        assert (side.first_gap_distance, side.first_gap_size) == (1.0, 1)
        assert (side.largest_gap_distance, side.largest_gap) == (3.0, 3)

    def test_equal_gaps_break_toward_the_touch(self, book_cls):
        # 99, 98 empty one tick down; 95, 94 empty five ticks down.  The nearer wins.
        side = self.read(book_cls, {100: 5, 97: 5, 96: 5, 93: 5})
        assert side.gap_count == 2 and side.largest_gap == 2
        assert side.largest_gap_distance == 1.0
        assert side.first_gap_distance == 1.0

    def test_a_hole_beyond_the_deepest_reported_level_is_not_a_gap(self, book_cls):
        """Depth 2 reports 100 and 99 only; the hole before 95 is outside the span."""
        side = self.read(book_cls, {100: 5, 99: 5, 95: 5}, depth=2)
        assert side.grid_span == 2 and side.gap_count == 0
        assert side.first_gap_distance is None

    def test_a_single_level_and_an_empty_side_place_nothing(self, book_cls):
        alone = self.read(book_cls, {100: 5})
        assert alone.occupied == 1 and alone.first_gap_distance is None
        empty = book_cls.from_levels({}, {200: 10}).side_statistics(BUY, ReportedDepth(3))
        assert empty.occupied == 0 and empty.first_gap_size == 0
        assert empty.largest_gap_distance is None

    def test_the_ask_side_measures_upward(self, book_cls):
        book = book_cls.from_levels({50: 10}, {100: 5, 102: 5})
        side = book.side_statistics(SELL, ReportedDepth(4))
        assert side.gap_count == 1 and side.first_gap_size == 1
        assert side.first_gap_distance == 1.0
