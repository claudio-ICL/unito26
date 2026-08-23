"""Every performance variant must be indistinguishable from the scanning baseline.

An optimisation is only interesting if it computes the same thing, so the variants are
tested against the baseline rather than against expectations.  These tests are what
make it safe to benchmark: a variant that is fast and wrong is not on the ladder.

Agreement is checked on the *derived* views as well as on the level maps.  A book that
stores its volumes somewhere other than the two dicts can agree on every best price and
every occupied level while returning zero from `levels` and the volume accessors, and
nothing else here would notice.
"""

import pytest

from unito26.lob.messages import BUY, SELL, is_market_price, limit_order, withdrawal
from unito26.lob.orderbook import (
    AXIS_B_VARIANTS,
    AggregateBook,
    HeapBook,
    TickArrayBook,
)
from unito26.lob.replay import run
from unito26.lob.simulate import OrderFlowSimulator
from unito26.lob.worked_examples import CATALOGUE, check, reflect

MIRROR_CENTRE = 1001
DEPTH = 6


@pytest.fixture(scope="module")
def stream():
    """A realistic message stream, materialised once so every variant sees it identically."""
    simulator = OrderFlowSimulator(rng=0)
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
