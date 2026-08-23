"""Every performance variant must be indistinguishable from the scanning baseline.

An optimisation is only interesting if it computes the same thing, so the variants are
tested against the baseline rather than against expectations.  These tests are what
make it safe to benchmark: a variant that is fast and wrong is not on the ladder.
"""

import pytest

from unito26.lob.messages import BUY, SELL, is_market_price
from unito26.lob.orderbook import (
    AggregateBook,
    BandBook,
    BitmapBook,
    CachedBestBook,
    HeapBook,
)
from unito26.lob.replay import run
from unito26.lob.simulate import MarkParams, OrderFlowSimulator

WORKED_EXAMPLE = ({1000: 100, 999: 200, 998: 150}, {1002: 120, 1003: 180})


def build(cls, origin=900, width=400, **kwargs):
    """Construct a variant, supplying the band arguments the two indexed ones need."""
    if cls is BandBook:
        return cls(origin=origin, width=width, **kwargs)
    if cls is BitmapBook:
        return cls(origin=origin, **kwargs)
    return cls(**kwargs)


VARIANTS = [AggregateBook, CachedBestBook, HeapBook, BandBook, BitmapBook]


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


@pytest.mark.parametrize("cls", VARIANTS, ids=lambda c: c.__name__)
class TestVariantsMatchTheBaseline:
    def test_reproduces_the_worked_example(self, cls):
        from unito26.lob.messages import limit_order

        book = cls.from_levels(
            *WORKED_EXAMPLE,
            **({"origin": 900, "width": 400} if cls is BandBook else {}),
            **({"origin": 900} if cls is BitmapBook else {}),
        )
        result = book.submit(limit_order(1.0, 400, 999, SELL))
        assert result.market_order_size == 300
        assert book.best_bid_price == 998
        assert book.best_ask_price == 999
        assert book.levels(SELL, 4) == [(999, 100), (1000, 0), (1001, 0), (1002, 120)]

    def test_agrees_with_the_baseline_over_a_whole_session(self, cls, stream):
        prices = [m.price for m in stream if not is_market_price(m.price)]
        origin, width = min(prices) - 5, max(prices) - min(prices) + 11

        reference = AggregateBook()
        reference_tally = run(reference, stream)

        book = build(cls, origin=origin, width=width)
        tally = run(book, stream)

        assert book.bids == reference.bids
        assert book.asks == reference.asks
        assert tally == reference_tally
        book.check_invariants()

    def test_best_price_tracks_the_baseline_at_every_step(self, cls, stream):
        """The strong form: not just the same final state, the same state throughout.

        A cache can be wrong for a while and right again by the end, so comparing final
        states is not enough.
        """
        prices = [m.price for m in stream if not is_market_price(m.price)]
        origin, width = min(prices) - 5, max(prices) - min(prices) + 11

        reference = AggregateBook()
        book = build(cls, origin=origin, width=width)
        for message in stream[:5000]:
            reference.apply(message)
            book.apply(message)
            assert book.best_price(BUY) == reference.best_price(BUY)
            assert book.best_price(SELL) == reference.best_price(SELL)


class TestCacheHonesty:
    def test_cached_best_agrees_with_a_full_rescan_throughout(self, stream):
        # A cache is a claim about state held elsewhere; the only honest way to keep
        # one is to be able to check it.
        book = CachedBestBook()
        for message in stream[:5000]:
            book.apply(message)
            book.verify_cache()

    def test_refilling_the_stale_best_price_is_handled(self):
        # The case that broke the cursor logic when it was first written: empty the
        # best level, then refill that exact price before anything reads the book.
        from unito26.lob.messages import limit_order, withdrawal

        for cls in VARIANTS:
            book = cls.from_levels(
                {1000: 100, 999: 200},
                {1002: 120},
                **({"origin": 900, "width": 400} if cls is BandBook else {}),
                **({"origin": 900} if cls is BitmapBook else {}),
            )
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
        assert sum(book.heap_overhead().values()) == 0
        book.check_invariants()


class TestBandLimits:
    def test_price_outside_the_band_is_refused_loudly(self):
        book = BandBook(origin=1000, width=10)
        from unito26.lob.messages import limit_order

        with pytest.raises(ValueError, match="outside the band"):
            book.submit(limit_order(1.0, 10, 5000, BUY))
