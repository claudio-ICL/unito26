"""Every performance variant must be indistinguishable from the scanning baseline.

An optimisation is only interesting if it computes the same thing, so the variants are
tested against the baseline rather than against expectations.  These tests are what
make it safe to benchmark: a variant that is fast and wrong is not on the ladder.

Agreement is checked on the *derived* views as well as on the level maps.  A book that
stores its volumes somewhere other than the two dicts can agree on every best price and
every occupied level while returning zero from `levels` and the volume accessors, and
nothing else here would notice.
"""

import math

import pytest

from unito26.lob.messages import (
    BUY,
    SELL,
    GridDepth,
    is_market_price,
    limit_order,
    withdrawal,
)
from unito26.lob.orderbook import (
    AXIS_B_VARIANTS,
    AggregateBook,
    HeapBook,
    TickArrayBook,
)
from unito26.lob import config
from unito26.lob.replay import run
from unito26.lob.simulate import OrderFlowSimulator
from unito26.lob.worked_examples import CATALOGUE, check, reflect

MIRROR_CENTRE = 1001
DEPTH = 6


@pytest.fixture(scope="module")
def stream():
    """A realistic message stream, materialised once so every variant sees it identically."""
    simulator = OrderFlowSimulator(
        config.example_order_flow_params(), config.example_mark_params(), 10000, rng=0
    )
    book = AggregateBook()
    simulator.warm_up(book, horizon=30.0)
    messages = []
    for message in simulator.stream(book, horizon=400.0):
        book.apply(message)
        messages.append(message)
    return messages


@pytest.fixture(scope="module")
def prices(stream):
    """The price range the stream visits, for the books that must be sized in advance."""
    return [message.price for message in stream if not is_market_price(message.price)]


@pytest.mark.parametrize("cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestVariantsMatchTheBaseline:
    def test_reproduces_the_catalogue(self, cls):
        for example in CATALOGUE:
            check(cls, example)
            check(cls, reflect(example, MIRROR_CENTRE))

    def test_agrees_with_the_baseline_over_a_whole_session(self, cls, stream, prices):
        reference = AggregateBook()
        reference_tally = run(reference, stream)

        book = cls.for_prices(prices)
        tally = run(book, stream)

        assert book.levels_map(BUY) == reference.levels_map(BUY)
        assert book.levels_map(SELL) == reference.levels_map(SELL)
        assert tally == reference_tally
        book.check_invariants()

    def test_tracks_the_baseline_at_every_step(self, cls, stream, prices):
        """The strong form: not just the same final state, the same state throughout.

        A cache can be wrong for a while and right again by the end, so comparing final
        states is not enough.
        """
        reference = AggregateBook()
        book = cls.for_prices(prices)
        for message in stream[:5000]:
            reference.apply(message)
            book.apply(message)
            for direction in (BUY, SELL):
                assert book.best_price(direction) == reference.best_price(direction)
                assert book.levels(direction, DEPTH) == reference.levels(direction, DEPTH)
            assert book.best_bid_volume == reference.best_bid_volume
            assert book.best_ask_volume == reference.best_ask_volume


class TestCacheHonesty:
    def test_cache_agrees_with_a_full_rescan_throughout(self, stream):
        # A cache is a claim about state held elsewhere; the only honest way to keep
        # one is to be able to check it.
        book = AXIS_B_VARIANTS[1]()
        for message in stream[:5000]:
            book.apply(message)
            book.check_cache_is_consistent()

    def test_refilling_the_emptied_best_price_is_handled(self):
        # The case that broke the cursor logic when it was first written: empty the
        # best level, then refill that exact price before anything reads the book.
        for cls in AXIS_B_VARIANTS:
            book = cls.from_levels({1000: 100, 999: 200}, {1002: 120})
            book.withdraw(withdrawal(1.0, 100, 1000, BUY))  # best bid level emptied
            book.submit(limit_order(2.0, 40, 1000, BUY))  # and immediately refilled
            assert book.best_bid_price == 1000, f"{cls.__name__} lost the refilled best"


class TestHeapHousekeeping:
    def test_lazy_deletion_accumulates_and_compaction_clears_it(self, stream):
        book = HeapBook()
        run(book, stream)
        overhead = book.heap_overhead()
        # Lazy deletion is not free: stale entries pile up in proportion to how many
        # levels have ever existed, which is the honest half of the technique.
        assert sum(overhead.values()) > 0
        book.compact()
        assert book.heap_overhead() == {BUY: 0, SELL: 0}
        book.check_invariants()


class TestTheBandIsTheFusedBookTradeOff:
    """The cost of indexing by tick, made explicit rather than discovered in production."""

    def test_writing_outside_the_band_is_refused_loudly(self):
        book = TickArrayBook(origin=1000, width=10)
        with pytest.raises(ValueError, match="outside the band"):
            book.submit(limit_order(1.0, 10, 5000, BUY))

    def test_reading_outside_the_band_is_simply_empty(self):
        # Reads run off the edge in ordinary use: `levels` walks a fixed depth up from
        # the best price whether or not the band reaches that far.  Nothing rests
        # there, which is a true answer and not an error.
        book = TickArrayBook.from_levels({1005: 50}, {1008: 40})
        assert book.volume_at(BUY, 999_999) == 0
        assert len(book.levels(SELL, DEPTH)) == DEPTH


class TestTheCeilingIsPartOfTheEncoding:
    """The ask bitmap counts down from `ceiling`, and the two ways it can be wrong differ.

    `price -> C - price` is self-inverse for *any* C, so an encode and a decode sharing a
    wrong C still agree with each other.  A ceiling set too *low* is loud -- a price above
    it shifts by a negative count and raises -- while one set too *high* is silent, and
    merely leaves the occupancy integer wider than the band.  So the edges are checked for
    the decode and `ceiling` itself for the tightness, since no behaviour reports the
    second.  Every other test keeps its prices `BAND_MARGIN` clear of the edges, which is
    why the band is built by hand here.
    """

    ORIGIN, WIDTH = 1000, 10

    def book(self):
        return TickArrayBook(origin=self.ORIGIN, width=self.WIDTH)

    @pytest.mark.parametrize("offset", [0, 1, 4, 8, 9])
    def test_an_ask_anywhere_in_the_band_decodes_to_itself(self, offset):
        book = self.book()
        price = self.ORIGIN + offset
        book.set_volume(SELL, price, 70)
        assert book.best_ask_price == price
        assert book.levels_map(SELL) == {price: 70}
        assert book.occupied_levels(SELL, 3) == [(price, 70)]

    def test_the_two_edges_are_both_reachable_and_ordered(self):
        book = self.book()
        floor, ceiling = self.ORIGIN, self.ORIGIN + self.WIDTH - 1
        assert book.ceiling == ceiling
        book.set_volume(SELL, ceiling, 11)
        book.set_volume(SELL, floor, 22)
        assert book.best_ask_price == floor
        assert book.occupied_levels(SELL, 2) == [(floor, 22), (ceiling, 11)]
        assert book.levels_map(SELL) == {floor: 22, ceiling: 11}

    def test_it_matches_the_baseline_at_the_edges(self):
        floor, ceiling = self.ORIGIN, self.ORIGIN + self.WIDTH - 1
        asks = {floor: 22, floor + 3: 33, ceiling: 11}
        book = self.book()
        for price, volume in asks.items():
            book.set_volume(SELL, price, volume)
        reference = AggregateBook.from_levels({}, asks)
        assert book.levels_map(SELL) == reference.levels_map(SELL)
        for depth in (1, 2, 3):
            assert book.occupied_levels(SELL, depth) == reference.occupied_levels(SELL, depth)
            assert book.side_statistics(SELL, depth) == reference.side_statistics(SELL, depth)

    def test_a_copy_decodes_its_ask_side_the_same_way(self):
        """`copy` goes through `_empty_like`, which must preserve the width: the ask bits
        are meaningless against a different one."""
        book = self.book()
        book.set_volume(SELL, self.ORIGIN + self.WIDTH - 1, 11)
        book.set_volume(SELL, self.ORIGIN, 22)
        clone = book.copy()
        assert clone.ceiling == book.ceiling
        assert clone.levels_map(SELL) == book.levels_map(SELL)
        assert clone.best_ask_price == book.best_ask_price


class TestTheImbalanceProfile:
    """`queue_imbalance_profile` is the batched reading; `queue_imbalance` is the
    definition.  Nothing keeps them together except this."""

    LEVELS = tuple(GridDepth(n) for n in (1, 2, 3, 5, 10, 40))

    @pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        "bids,asks",
        [
            ({1000: 100, 999: 200, 995: 50}, {1002: 120, 1003: 180, 1010: 40}),
            ({1000: 100}, {1001: 100}),
            ({1000: 900}, {1002: 100}),      # bid-heavy: the sign convention
            ({}, {1001: 50}),                # one side empty: -1 everywhere
            ({1000: 50}, {}),                # the other: +1 everywhere
            ({}, {}),                        # both empty: NaN everywhere
        ],
    )
    def test_it_agrees_with_the_definition_term_by_term(self, book_cls, bids, asks):
        book = book_cls.from_levels(bids, asks)
        profile = book.queue_imbalance_profile(self.LEVELS)
        for n, batched in zip(self.LEVELS, profile):
            alone = book.queue_imbalance(n)
            assert (math.isnan(batched) and math.isnan(alone)) or batched == alone

    def test_the_window_may_run_off_the_band(self):
        """A grid position outside the band holds nothing, so the running total stops
        growing rather than going short or raising."""
        book = TickArrayBook(origin=1000, width=10)
        book.set_volume(BUY, 1001, 30)
        book.set_volume(SELL, 1008, 70)
        reference = AggregateBook.from_levels({1001: 30}, {1008: 70})
        wide = tuple(GridDepth(n) for n in (1, 2, 3, 9, 40, 400))
        assert book.queue_imbalance_profile(wide) == reference.queue_imbalance_profile(wide)

    @pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
    def test_a_level_below_one_is_refused(self, book_cls):
        book = book_cls.from_levels({1000: 10}, {1001: 10})
        with pytest.raises(ValueError, match="must be >= 1"):
            book.queue_imbalance_profile((GridDepth(0),))
