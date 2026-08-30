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
    TickGrid,
    limit_order,
    market_order,
    withdrawal,
)
from unito26.lob.orderbook import AggregateBook
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
        assert (book.bid_price(1), book.bid_volume(1)) == (1000, 100)
        assert (book.bid_price(2), book.bid_volume(2)) == (999, 200)
        assert (book.bid_price(3), book.bid_volume(3)) == (998, 150)
        # By convention volumes vanish at non-positive indices; this is what makes the
        # shifted index of section 5 well defined.
        assert book.bid_volume(0) == 0
        assert book.bid_volume(-3) == 0

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
        result = worked_example.submit(limit_order(1.0, 250, 999, SELL))
        assert result.market_order_size == 250
        assert [(f.price, f.size) for f in result.fills] == [(1000, 100), (999, 150)]
        assert all(f.aggressor == SELL for f in result.fills)
        assert result.walked_the_book

    def test_resulting_configuration(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 250, 999, SELL))
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
        result = worked_example.submit(limit_order(1.0, 400, 999, SELL))
        # q_M = min(400, 100 + 200) = 300, so 100 is left to rest.
        assert result.market_order_size == 300
        assert [(f.price, f.size) for f in result.fills] == [(1000, 100), (999, 200)]

    def test_residual_rests_inside_the_old_spread(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 400, 999, SELL))
        assert book.best_ask_price == 999  # was 1002; the rest improved it
        assert book.ask_volume_at(999) == 100
        assert book.best_bid_price == 998
        assert book.spread == 1
        assert book.mid_price == 998.5
        # I^1 = (150 - 100) / 250
        assert book.queue_imbalance(1) == pytest.approx(0.2)
        book.check_invariants()

    def test_ask_indices_shift_and_leave_empty_levels(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 400, 999, SELL))
        # The best ask moved down by 3 ticks, so every ask index shifts by 3 and two
        # grid positions in between hold nothing at all.
        assert book.levels(SELL, 4) == [(999, 100), (1000, 0), (1001, 0), (1002, 120)]

    def test_both_routes_agree_on_total_volume(self, worked_example):
        book = worked_example
        before = sum(book.bids.values()) + sum(book.asks.values())
        result = book.submit(limit_order(1.0, 400, 999, SELL))
        after = sum(book.bids.values()) + sum(book.asks.values())
        # Shares are conserved: what arrived, minus twice what traded (once from the
        # book, once from the incoming order), is what remains.
        assert after == before + 400 - 2 * result.market_order_size


class TestExhaustedSide:
    def test_consuming_the_whole_bid_side_leaves_it_undefined(self, worked_example):
        book = worked_example
        # Sell 500 at 9.98: the price-eligible bid volume is 100+200+150 = 450.
        result = book.submit(limit_order(1.0, 500, 998, SELL))
        assert result.market_order_size == 450
        assert book.bids == {}
        assert book.best_bid_price is None
        assert book.spread is None
        # The 50 left over rests on the ask side at its own limit price.
        assert book.ask_volume_at(998) == 50
        book.check_invariants()

    def test_imbalance_still_defined_when_only_one_side_is_empty(self, worked_example):
        book = worked_example
        book.submit(limit_order(1.0, 500, 998, SELL))
        assert book.queue_imbalance(1) == -1.0


class TestMarketOrders:
    """Market-to-limit: the remainder rests at the price it last executed against."""

    def test_remainder_rests_at_the_last_traded_price(self, worked_example):
        book = worked_example
        # A market sell far larger than the bid side: 450 trade, down to 9.98, and the
        # 550 left over becomes an ask at 9.98 -- the price the order last got.
        result = book.submit(market_order(1.0, 1000, SELL))
        assert result.market_order_size == 450
        assert result.unfilled == 0
        assert book.bids == {}
        assert book.ask_volume_at(998) == 550
        assert book.best_ask_price == 998
        book.check_invariants()

    def test_nothing_ever_rests_at_a_sentinel_price(self, worked_example):
        book = worked_example
        book.submit(market_order(1.0, 1000, SELL))
        book.submit(market_order(2.0, 1000, BUY))
        for levels in (book.bids, book.asks):
            assert MARKET_SELL_PRICE not in levels
            assert MARKET_BUY_PRICE not in levels

    def test_with_nothing_to_trade_against_the_remainder_is_unfilled(self):
        # The one case where a remainder cannot rest: no fill, so no price to inherit.
        # It can only arise against an empty side, where there was no liquidity to take
        # at any price, so nothing is lost by refusing it.
        book = AggregateBook.from_levels({1000: 100}, {})
        result = book.submit(market_order(1.0, 60, BUY))
        assert result.fills == []
        assert result.unfilled == 60
        assert book.asks == {}
        assert book.bids == {1000: 100}
        book.check_invariants()

    def test_market_buy_ignores_the_price_constraint_entirely(self, worked_example):
        book = worked_example
        result = book.submit(market_order(1.0, 250, BUY))
        assert [(f.price, f.size) for f in result.fills] == [(1002, 120), (1003, 130)]
        assert book.asks == {1003: 50}


class TestPassiveOrdersAndWithdrawals:
    def test_a_non_marketable_order_just_joins_its_level(self, worked_example):
        book = worked_example
        result = book.submit(limit_order(1.0, 75, 999, BUY))
        assert result.fills == []
        assert book.bid_volume_at(999) == 275
        assert book.best_bid_price == 1000  # unchanged

    def test_withdrawal_is_one_signed_delta(self, worked_example):
        book = worked_example
        result = book.withdraw(withdrawal(1.0, 60, 999, BUY))
        assert result.fills == []
        assert [(d.price, d.volume) for d in result.deltas] == [(999, 140)]
        assert book.bid_volume_at(999) == 140

    def test_withdrawing_a_whole_level_can_move_the_best_price_downwards(
        self, worked_example
    ):
        book = worked_example
        book.withdraw(withdrawal(1.0, 100, 1000, BUY))
        assert 1000 not in book.bids
        assert book.best_bid_price == 999  # the best price now moves *down*

    def test_lenient_mode_removes_what_is_there(self, worked_example):
        book = worked_example
        book.withdraw(withdrawal(1.0, 999, 998, SELL))  # nothing rests there at all
        assert book.bids == {1000: 100, 999: 200, 998: 150}

    def test_strict_mode_refuses_to_overwithdraw(self, worked_example):
        book = worked_example
        book.strict = True
        with pytest.raises(ValueError, match="only 150 resting"):
            book.withdraw(withdrawal(1.0, 400, 998, BUY))


class TestSnapshotAliasing:
    def test_copy_is_independent(self, worked_example):
        book = worked_example
        snapshot = book.copy()
        book.submit(market_order(1.0, 300, BUY))
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
