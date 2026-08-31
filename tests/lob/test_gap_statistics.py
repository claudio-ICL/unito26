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
    """`side_statistics` is what the session fold uses: the same four numbers from one
    walk of the side rather than four."""

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
