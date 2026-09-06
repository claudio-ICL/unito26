"""Tests for the aggregate book, rungs L0 to L3.

The centrepiece is the worked example of section 8 of the notation, reproduced
verbatim.  Case B is the canonical fixture because it exercises, in one message,
everything that usually breaks: walking the book, a residual resting inside the old
spread, the index shift, and empty levels between the best price and the deeper ones.
"""

import math

import pytest

from unito26.lob.messages import (
    BUY,
    MARKET_BUY_PRICE,
    MARKET_SELL_PRICE,
    SELL,
    is_market_price,
    TickGrid,
    limit_order,
    market_order,
    withdrawal,
)
from unito26.lob import config
from unito26.lob.orderbook import AXIS_B_VARIANTS, AggregateBook
from unito26.lob.simulate import OrderFlowSimulator
from unito26.lob.worked_examples import CATALOGUE, check, reflect

TICK = TickGrid(0.01)


@pytest.fixture
def worked_example() -> AggregateBook:
    """The book at ``t-`` in section 8, in ticks.

    ask 10.03 x 180, ask 10.02 x 120 (best);  bid 10.00 x 100 (best), 9.99 x 200,
    9.98 x 150.  So the spread is 2 ticks and the mid is 10.01.
    """
    book = AggregateBook()
    book.bids = {1000: 100, 999: 200, 998: 150}
    book.asks = {1002: 120, 1003: 180}
    return book


class TestConfiguration:
    def test_best_prices_and_derived_quantities(self, worked_example):
        book = worked_example
        assert book.best_bid_price == 1000
        assert book.best_ask_price == 1002
        assert book.spread == 2
        assert book.mid_price == 1001.0
        assert TICK.to_price(book.best_ask_price) == pytest.approx(10.02)
        # I^1 = (100 - 120) / 220
        assert book.queue_imbalance(1) == pytest.approx(-0.0909, abs=1e-4)

    def test_levels_are_one_indexed_and_relative_to_the_best_price(self, worked_example):
        book = worked_example
        assert (book.bid_price(1), book.bid_size(1)) == (1000, 100)
        assert (book.bid_price(2), book.bid_size(2)) == (999, 200)
        assert (book.bid_price(3), book.bid_size(3)) == (998, 150)
        # By convention sizes vanish at non-positive indices; this is what makes the
        # shifted index of section 5 well defined.
        assert book.bid_size(0) == 0
        assert book.bid_size(-3) == 0

    def test_empty_book_reports_no_prices_rather_than_zero(self):
        book = AggregateBook()
        assert book.best_bid_price is None
        assert book.best_ask_price is None
        assert book.spread is None
        assert book.mid_price is None
        assert book.micro_price is None
        # 0/0: NaN rather than a raise, so a session can carry the row.
        assert math.isnan(book.queue_imbalance(1))


class TestCaseA:
    """Section 8, case A: sell (t, 250, 9.99, -1).  Fully executed, no remainder."""

    def test_fills_at_resting_prices(self, worked_example):
        result = worked_example.submit(limit_order(1.0, 250, 999, SELL), record=True)
        assert result.market_order_size == 250
        assert [(f.price, f.size) for f in result.fills] == [(1000, 100), (999, 150)]
        assert all(f.aggressor == SELL for f in result.fills)
        assert result.walked_the_book

    def test_resulting_configuration(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 250, 999, SELL), record=False)
        assert book.bids == {999: 50, 998: 150}
        assert book.asks == {1002: 120, 1003: 180}  # untouched: nothing was left over
        assert book.best_bid_price == 999
        assert book.spread == 3
        assert book.mid_price == 1000.5
        # I^1 = (50 - 120) / 170
        assert book.queue_imbalance(1) == pytest.approx(-0.4118, abs=1e-4)
        book.check_invariants()


class TestCaseB:
    """Section 8, case B: sell (t, 400, 9.99, -1).  Walks the book and leaves a rest.

    The canonical fixture.
    """

    def test_decomposition_into_market_part_and_resting_part(self, worked_example):
        result = worked_example.submit(limit_order(1.0, 400, 999, SELL), record=True)
        # q_M = min(400, 100 + 200) = 300, so 100 is left to rest.
        assert result.market_order_size == 300
        assert [(f.price, f.size) for f in result.fills] == [(1000, 100), (999, 200)]

    def test_residual_rests_inside_the_old_spread(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 400, 999, SELL), record=False)
        assert book.best_ask_price == 999  # was 1002; the rest improved it
        assert book.ask_size_at(999) == 100
        assert book.best_bid_price == 998
        assert book.spread == 1
        assert book.mid_price == 998.5
        # I^1 = (150 - 100) / 250
        assert book.queue_imbalance(1) == pytest.approx(0.2)
        book.check_invariants()

    def test_ask_indices_shift_and_leave_empty_levels(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 400, 999, SELL), record=False)
        # The best ask moved down by 3 ticks, so every ask index shifts by 3 and two
        # grid positions in between hold nothing at all.
        assert book.levels(SELL, 4) == [(999, 100), (1000, 0), (1001, 0), (1002, 120)]

    def test_both_routes_agree_on_total_size(self, worked_example):
        book = worked_example
        before = sum(book.bids.values()) + sum(book.asks.values())
        result = book.submit(limit_order(1.0, 400, 999, SELL), record=True)
        after = sum(book.bids.values()) + sum(book.asks.values())
        # Shares are conserved: what arrived, minus twice what traded (once from the
        # book, once from the incoming order), is what remains.
        assert after == before + 400 - 2 * result.market_order_size


class TestExhaustedSide:
    def test_consuming_the_whole_bid_side_leaves_it_undefined(self, worked_example):
        book = worked_example
        # Sell 500 at 9.98: the price-eligible bid size is 100+200+150 = 450.
        result = book.submit(limit_order(1.0, 500, 998, SELL), record=True)
        assert result.market_order_size == 450
        assert book.bids == {}
        assert book.best_bid_price is None
        assert book.spread is None
        # The 50 left over rests on the ask side at its own limit price.
        assert book.ask_size_at(998) == 50
        book.check_invariants()

    def test_imbalance_still_defined_when_only_one_side_is_empty(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 500, 998, SELL), record=False)
        assert book.queue_imbalance(1) == -1.0


class TestMarketOrders:
    """Market-to-limit: the remainder rests at the price it last executed against."""

    def test_remainder_rests_at_the_last_traded_price(self, worked_example):
        book = worked_example
        # A market sell far larger than the bid side: 450 trade, down to 9.98, and the
        # 550 left over becomes an ask at 9.98 -- the price the order last got.
        result = book.submit(market_order(1.0, 1000, SELL), record=True)
        assert result.market_order_size == 450
        assert result.unfilled == 0
        assert book.bids == {}
        assert book.ask_size_at(998) == 550
        assert book.best_ask_price == 998
        book.check_invariants()

    def test_nothing_ever_rests_at_a_sentinel_price(self, worked_example):
        book = worked_example
        book.submit(market_order(1.0, 1000, SELL), record=False)
        book.submit(market_order(2.0, 1000, BUY), record=False)
        for levels in (book.bids, book.asks):
            assert MARKET_SELL_PRICE not in levels
            assert MARKET_BUY_PRICE not in levels

    def test_with_nothing_to_trade_against_the_remainder_is_unfilled(self):
        # The one case where a remainder cannot rest: no fill, so no price to inherit.
        # It can only arise against an empty side, where there was no liquidity to take
        # at any price, so nothing is lost by refusing it.
        book = AggregateBook.from_levels({1000: 100}, {})
        result = book.submit(market_order(1.0, 60, BUY), record=True)
        assert result.fills == []
        assert result.unfilled == 60
        assert book.asks == {}
        assert book.bids == {1000: 100}
        book.check_invariants()

    def test_market_buy_ignores_the_price_constraint_entirely(self, worked_example):
        book = worked_example
        result = book.submit(market_order(1.0, 250, BUY), record=True)
        assert [(f.price, f.size) for f in result.fills] == [(1002, 120), (1003, 130)]
        assert book.asks == {1003: 50}


class TestPassiveOrdersAndWithdrawals:
    def test_a_non_marketable_order_just_joins_its_level(self, worked_example):
        book = worked_example
        result = book.submit(limit_order(1.0, 75, 999, BUY), record=True)
        assert result.fills == []
        assert book.bid_size_at(999) == 275
        assert book.best_bid_price == 1000  # unchanged

    def test_withdrawal_is_one_signed_delta(self, worked_example):
        book = worked_example
        result = book.withdraw(withdrawal(1.0, 60, 999, BUY), record=True)
        assert result.fills == []
        assert [(d.price, d.resting) for d in result.deltas] == [(999, 140)]
        assert book.bid_size_at(999) == 140

    def test_withdrawing_a_whole_level_can_move_the_best_price_downwards(
        self, worked_example
    ):
        book = worked_example
        book.withdraw(withdrawal(1.0, 100, 1000, BUY), record=False)
        assert 1000 not in book.bids
        assert book.best_bid_price == 999  # the best price now moves *down*

    def test_lenient_mode_removes_what_is_there(self, worked_example):
        book = worked_example
        book.withdraw(withdrawal(1.0, 999, 998, SELL), record=False)  # nothing rests there at all
        assert book.bids == {1000: 100, 999: 200, 998: 150}

    def test_strict_mode_refuses_to_overwithdraw(self, worked_example):
        book = worked_example
        book.strict = True
        with pytest.raises(ValueError, match="only 150 resting"):
            book.withdraw(withdrawal(1.0, 400, 998, BUY), record=False)


class TestSnapshotAliasing:
    def test_copy_is_independent(self, worked_example):
        book = worked_example
        snapshot = book.copy()
        book.submit(market_order(1.0, 300, BUY), record=False)
        # The classic bug: had the tap stored the book itself, this would now equal
        # the live state rather than the state at the moment it was taken.
        assert snapshot.asks == {1002: 120, 1003: 180}
        assert book.asks != snapshot.asks


MIRROR_CENTRE = 1001


@pytest.mark.parametrize("example", CATALOGUE, ids=lambda e: e.name)
class TestTheCatalogue:
    """Every branch of ``prop.lobUpdate``, on the baseline book.

    The expected states are derived from the notation rather than captured from a run,
    so these are the tests that can fail when the implementation is wrong -- as opposed
    to merely when it changes.
    """

    def test_the_transition_is_what_the_notation_says(self, example):
        check(AggregateBook, example)

    def test_the_mirrored_transition_agrees(self, example):
        # A symmetry of the matching rule, so this passes only if `d` really does
        # collapse both sides of the book into one comparison.
        check(AggregateBook, reflect(example, MIRROR_CENTRE))

    def test_reflecting_twice_is_the_identity(self, example):
        once = reflect(example, MIRROR_CENTRE)
        assert reflect(once, MIRROR_CENTRE).transition == example.transition


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestRecordingIsOptional:
    """The fold does not read the fills or the deltas, so it does not pay for them.

    What must not change is the book: the two settings differ in what is returned and in
    nothing else.
    """

    def test_the_book_ends_in_the_same_state(self, book_cls):
        simulator = OrderFlowSimulator(
            config.example_order_flow_params(), config.example_mark_params(), 10000, rng=13
        )
        driver = AggregateBook()
        messages = []
        for message in simulator.stream(driver, horizon=120.0, journal=None):
            driver.apply(message, record=False)
            messages.append(message)

        prices = [m.price for m in messages if not is_market_price(m.price)]
        silent = book_cls.for_prices(prices)
        recording = book_cls.for_prices(prices)
        for message in messages:
            assert silent.apply(message, record=False) is None
            assert recording.apply(message, record=True) is not None
        for direction in (BUY, SELL):
            assert silent.levels_map(direction) == recording.levels_map(direction)

    def test_a_withdrawal_that_removes_nothing_still_returns_nothing(self, book_cls):
        book = book_cls.from_levels({999: 10}, {1001: 10})
        assert book.withdraw(withdrawal(1.0, 5, 990, BUY), record=False) is None
        assert book.withdraw(withdrawal(1.0, 5, 990, BUY), record=True).deltas == []


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestSizingFromAStream:
    """`for_prices` is handed a message stream, so it must drop the two sentinels.

    They fail differently, which is how a filter written for one comes to let the other
    through: the buy sentinel is `sys.maxsize` and asks for a band no machine has, the
    sell sentinel is 0 and quietly widens the band by the whole reference price.
    """

    REAL = [9995, 10000, 10004, 9998]

    def test_the_sentinels_contribute_no_range(self, book_cls):
        stream = self.REAL + [MARKET_BUY_PRICE, MARKET_SELL_PRICE, MARKET_BUY_PRICE]
        from_stream = book_cls.for_prices(stream)
        from_real = book_cls.for_prices(self.REAL)
        assert from_stream.levels_map(BUY) == from_real.levels_map(BUY)
        for attribute in ("origin", "width"):
            assert getattr(from_stream, attribute, None) == getattr(from_real, attribute, None)

    def test_the_buy_sentinel_no_longer_asks_for_an_impossible_band(self, book_cls):
        # Before the filter this raised MemoryError on the tick-indexed rung.
        book = book_cls.for_prices([9995, MARKET_BUY_PRICE])
        book.set_size(BUY, 9995, 10)
        assert book.best_bid_price == 9995


def test_a_level_at_the_sell_sentinel_is_not_sizeable():
    """The cost of the sentinel being an ordinary integer, stated where it bites.

    `grid_prices` cannot tell a genuine level at 0 from a market sell, so a band that
    would have to span both refuses.  The alternative -- sizing from the sentinel -- is
    the bug this filter exists to remove.
    """
    from unito26.lob.orderbook import TickArrayBook

    with pytest.raises(ValueError, match="outside the band"):
        TickArrayBook.from_levels({MARKET_SELL_PRICE: 5}, {500: 5})
