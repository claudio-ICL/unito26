"""Assignment 1, point i: the book replayed from the message file against the orderbook file.

The pairs below are written by hand at depth 2, so every row of the expected outcome can be
checked by eye.  Each test states one property of the replay; none needs the data.
"""

import numpy as np
import pandas as pd
import pytest

from unito26.lob import frames, lobster
from unito26.lob.Federico_Andrione_reconciliation import (
    as_book_message, discrepancy_census, reconcile, repair_log, replay,
)
from unito26.lob.lobster import LobsterEvent
from unito26.lob.messages import BUY, SELL, MessageType, PriceUnit, ReportedDepth

DEPTH = ReportedDepth(2)
CENT = PriceUnit(100)
PAD_ASK, PAD_BID = frames.ASK_PADDING, frames.BID_PADDING

# time, type, order id, size, price, direction
MESSAGES = frames.lobster_message_file_columns()


def state(ask, ask_size, bid, bid_size, ask2, ask2_size, bid2, bid2_size):
    """One orderbook row at depth 2, in the file's own column order."""
    return [ask, ask_size, bid, bid_size, ask2, ask2_size, bid2, bid2_size]


def frames_of(messages, book):
    return (
        pd.DataFrame(messages, columns=MESSAGES),
        pd.DataFrame(book, columns=lobster.orderbook_columns(DEPTH)),
    )


# Every visible event type once, and a hidden execution at a sub-penny price.
ORDINARY = frames_of(
    [
        (34200.0, 1, 1, 10, 99900, 1),
        (34201.0, 1, 2, 30, 100000, 1),     # adds to the best bid
        (34202.0, 3, 1, 10, 99900, 1),      # deletes the second bid
        (34203.0, 4, 7, 20, 100200, -1),    # a buyer takes 20 from the resting ask
        (34204.0, 5, 0, 50, 100150, -1),    # hidden: no visible level moves
        (34205.0, 2, 7, 40, 100200, -1),    # partial cancellation of the ask
    ],
    [
        state(100200, 120, 100000, 100, PAD_ASK, 0, 99900, 10),
        state(100200, 120, 100000, 130, PAD_ASK, 0, 99900, 10),
        state(100200, 120, 100000, 130, PAD_ASK, 0, PAD_BID, 0),
        state(100200, 100, 100000, 130, PAD_ASK, 0, PAD_BID, 0),
        state(100200, 100, 100000, 130, PAD_ASK, 0, PAD_BID, 0),
        state(100200, 60, 100000, 130, PAD_ASK, 0, PAD_BID, 0),
    ],
)

# The best bid is cleared, and a level resting below the reported depth comes into view:
# 99800 x 50 was never in a message, so only the orderbook file can say it exists.
ENTERING = frames_of(
    [
        (34200.0, 1, 1, 10, 99900, 1),
        (34201.0, 4, 5, 100, 100000, 1),    # a seller clears the best bid
        (34202.0, 1, 9, 5, 99800, 1),       # and an order joins the level that came into view
    ],
    [
        state(100200, 120, 100000, 100, PAD_ASK, 0, 99900, 10),
        state(100200, 120, 99900, 10, PAD_ASK, 0, 99800, 50),
        state(100200, 120, 99900, 10, PAD_ASK, 0, 99800, 55),
    ],
)


# A bid inside the touch pushes 99900 out of view; it changes there unreported, from 10 to
# 15, and returns when that bid is deleted.  The messages alone still hold it at 10.
RETURNING = frames_of(
    [
        (34200.0, 1, 1, 10, 99900, 1),
        (34201.0, 1, 2, 20, 100100, 1),     # a bid inside the touch: 99900 leaves the view
        (34202.0, 3, 2, 20, 100100, 1),     # deleted: 99900 returns, at a size never reported
    ],
    [
        state(100200, 120, 100000, 100, PAD_ASK, 0, 99900, 10),
        state(100200, 120, 100100, 20, PAD_ASK, 0, 100000, 100),
        state(100200, 120, 100000, 100, PAD_ASK, 0, 99900, 15),
    ],
)


# The best bid is cleared with nothing behind it in the rebuilt book, and two levels come
# into view at once.
TWO_ENTERING = frames_of(
    [
        (34200.0, 1, 1, 10, 100000, 1),
        (34201.0, 4, 5, 100, 100000, 1),    # a seller clears the only bid the replay holds
    ],
    [
        state(100200, 120, 100000, 100, PAD_ASK, 0, PAD_BID, 0),
        state(100200, 120, 99900, 10, PAD_ASK, 0, 99800, 50),
    ],
)

# The file shows a bid inside the touch that no message announced.  The side is short of
# two levels, so the repair looks at the file; the level is inside the view, so it must
# not take it.
MISSING_INSIDE = frames_of(
    [
        (34200.0, 1, 1, 100, 100000, 1),
        (34201.0, 5, 0, 50, 100150, -1),    # hidden: the rebuilt book does not move
    ],
    [
        state(100200, 120, 100000, 100, PAD_ASK, 0, PAD_BID, 0),
        state(100200, 120, 100100, 5, PAD_ASK, 0, 100000, 100),
    ],
)

AXIS = 100000 + 100200  # the two best prices of every seed row above


def mirrored(pair):
    """The pair with the two sides exchanged: prices reflected about the mid, directions
    flipped.  What holds of the bid in the pairs above must hold of the ask in these."""
    messages, book = pair
    messages = messages.assign(Price=AXIS - messages["Price"], Direction=-messages["Direction"])
    levels = book.to_numpy().reshape(len(book), DEPTH, 4)[:, :, [2, 3, 0, 1]]
    for column, padding, other in ((0, PAD_BID, PAD_ASK), (2, PAD_ASK, PAD_BID)):
        prices = levels[:, :, column]
        levels[:, :, column] = np.where(prices == padding, other, AXIS - prices)
    return messages, pd.DataFrame(levels.reshape(len(book), -1), columns=book.columns)


def on_both_sides(pair):
    return pytest.mark.parametrize("pair", [pair, mirrored(pair)], ids=["bid", "ask"])


class TestOneMessage:
    def test_a_submission_is_a_limit_order(self):
        message = as_book_message(LobsterEvent.SUBMISSION, 1.0, 10, 99900, BUY, CENT)
        assert (message.kind, message.price, message.size, message.direction) == (
            MessageType.SUBMIT, 999, 10, BUY,
        )

    @pytest.mark.parametrize("kind", [
        LobsterEvent.PARTIAL_CANCELLATION, LobsterEvent.DELETION, LobsterEvent.EXECUTION_VISIBLE,
    ])
    def test_cancellations_and_visible_executions_remove_from_the_resting_side(self, kind):
        """``Direction`` names the side that rested, so an execution removes from it."""
        message = as_book_message(kind, 1.0, 20, 100200, SELL, CENT)
        assert (message.kind, message.price, message.direction) == (
            MessageType.WITHDRAW, 1002, SELL,
        )

    @pytest.mark.parametrize("kind", [
        LobsterEvent.EXECUTION_HIDDEN, LobsterEvent.CROSS_TRADE, LobsterEvent.TRADING_HALT,
    ])
    def test_events_that_move_no_visible_level_are_none(self, kind):
        """Including a halt, whose ``Price`` is a status code, and a sub-penny hidden print."""
        assert as_book_message(kind, 1.0, 0, -1, SELL, CENT) is None
        assert as_book_message(kind, 1.0, 50, 100150, SELL, CENT) is None

    def test_a_visible_price_off_the_grid_is_refused(self):
        with pytest.raises(ValueError, match="multiple"):
            as_book_message(LobsterEvent.SUBMISSION, 1.0, 10, 100150, BUY, CENT)

    def test_a_type_outside_the_format_is_refused(self):
        with pytest.raises(ValueError):
            as_book_message(8, 1.0, 10, 100000, BUY, CENT)


class TestTheReplay:
    @pytest.mark.parametrize("refill", [False, True])
    def test_every_row_agrees_when_nothing_enters_from_below(self, refill):
        report = reconcile(*ORDINARY, CENT, DEPTH, refill)
        assert report["Row"].tolist() == [1, 2, 3, 4, 5]
        assert (report["FirstDifferingLevel"] == 0).all()
        assert (report["LevelsImported"] == 0).all()

    def test_the_seed_row_is_not_replayed(self):
        """Row 0 is the state after message 0, which is where the replay starts from."""
        report = reconcile(*ORDINARY, CENT, DEPTH, False)
        assert 0 not in report["Row"].tolist()
        assert report["Time"].tolist() == ORDINARY[0]["Time"].tolist()[1:]

    @on_both_sides(ENTERING)
    def test_a_level_entering_from_below_is_a_discrepancy_of_the_messages_alone(self, pair):
        report = reconcile(*pair, CENT, DEPTH, False)
        assert report["FirstDifferingLevel"].tolist() == [2, 2]

    @on_both_sides(ENTERING)
    def test_and_the_orderbook_file_is_the_only_source_for_it(self, pair):
        report = reconcile(*pair, CENT, DEPTH, True)
        assert report["LevelsImported"].tolist() == [1, 0]
        assert report["FirstDifferingLevel"].tolist() == [0, 0]

    @on_both_sides(RETURNING)
    def test_a_level_returning_into_view_is_read_again_from_the_file(self, pair):
        alone = reconcile(*pair, CENT, DEPTH, False)
        refilled = reconcile(*pair, CENT, DEPTH, True)
        assert alone["FirstDifferingLevel"].tolist() == [0, 2]
        assert refilled["FirstDifferingLevel"].tolist() == [0, 0]
        assert refilled["LevelsImported"].tolist() == [0, 1]

    def test_it_reports_a_submission_that_the_replay_matches(self):
        """In the market a submission never trades; a replayed book can make it cross."""
        messages, book = frames_of(
            [
                (34200.0, 1, 1, 10, 99900, 1),
                (34201.0, 1, 2, 20, 100200, 1),     # a bid at the ask the replay holds
            ],
            [
                state(100200, 120, 100000, 100, PAD_ASK, 0, 99900, 10),
                state(100200, 100, 100000, 100, PAD_ASK, 0, 99900, 10),
            ],
        )
        steps = replay(messages, book, CENT, DEPTH, False)
        traded = [(row, kind, replayed.last_traded_size)
                  for row, _, kind, _, _, replayed, _ in steps]
        assert traded == [(1, LobsterEvent.SUBMISSION, 20)]

    def test_the_two_files_must_have_the_same_length(self):
        messages, book = ORDINARY
        with pytest.raises(ValueError, match="aligned"):
            reconcile(messages, book.iloc[:-1], CENT, DEPTH, True)

    def test_a_seed_row_alone_is_not_a_replay(self):
        messages, book = ORDINARY
        with pytest.raises(ValueError, match="seed"):
            reconcile(messages.iloc[:1], book.iloc[:1], CENT, DEPTH, True)



class TestTheRepairLog:
    def test_it_tells_a_level_returning_into_view_from_one_entering_for_the_first_time(self):
        """A new level is imported only; a returning one is forgotten first, at its old size."""
        columns = ["Row", "Action", "Direction", "Price", "Size"]
        entering = repair_log(*ENTERING, CENT, DEPTH)[columns].values.tolist()
        returning = repair_log(*RETURNING, CENT, DEPTH)[columns].values.tolist()
        assert entering == [[1, "import", BUY, 998, 50]]
        assert returning == [[1, "forget", BUY, 999, 10], [2, "import", BUY, 999, 15]]

    def test_it_names_the_ask_when_the_level_is_an_ask(self):
        columns = ["Row", "Action", "Direction", "Price", "Size"]
        returning = repair_log(*mirrored(RETURNING), CENT, DEPTH)[columns].values.tolist()
        assert returning == [[1, "forget", SELL, 1003, 10], [2, "import", SELL, 1003, 15]]

class TestTheCensus:
    def test_every_replayed_row_is_counted_once(self):
        census = discrepancy_census(reconcile(*ORDINARY, CENT, DEPTH, True))
        assert census["Rows"].sum() == 5
        assert census.set_index("Event").loc["EXECUTION_HIDDEN", "Rows"] == 1

    def test_imports_and_differences_are_counted_by_event(self):
        census = discrepancy_census(reconcile(*ENTERING, CENT, DEPTH, False)).set_index("Event")
        assert census.loc["EXECUTION_VISIBLE", "RowsDiffering"] == 1
        assert census.loc["SUBMISSION", "RowsDiffering"] == 1
        assert census["TouchDiffering"].sum() == 0

    def test_a_row_importing_two_levels_is_one_row_and_two_levels(self):
        census = discrepancy_census(reconcile(*TWO_ENTERING, CENT, DEPTH, True)).set_index("Event")
        assert census.loc["EXECUTION_VISIBLE", "RowsImporting"] == 1
        assert census.loc["EXECUTION_VISIBLE", "LevelsImported"] == 2
        assert census["RowsDiffering"].sum() == 0


class TestTheRefillHidesNothing:
    """The levels copied from the file are the ones no message reaches, and only those."""

    def test_a_wrong_size_at_the_touch_is_still_a_discrepancy(self):
        messages, book = ORDINARY
        book = book.copy()
        book.loc[1, "BidSize1"] += 1
        report = reconcile(messages, book, CENT, DEPTH, True)
        assert report["FirstDifferingLevel"].tolist() == [1, 0, 0, 0, 0]
        assert (report["LevelsImported"] == 0).all()

    def test_a_price_the_messages_know_is_never_copied(self):
        messages, book = ENTERING
        book = book.copy()
        book.loc[1, "BidSize1"] = 11
        report = reconcile(messages, book, CENT, DEPTH, True)
        assert report["LevelsImported"].tolist() == [1, 0]
        assert report["FirstDifferingLevel"].tolist() == [1, 0]

    def test_a_level_missing_inside_the_view_is_not_taken_from_the_file(self):
        report = reconcile(*MISSING_INSIDE, CENT, DEPTH, True)
        assert report["LevelsImported"].tolist() == [0]
        assert report["FirstDifferingLevel"].tolist() == [1]

    def test_a_side_that_holds_all_its_levels_takes_nothing_from_the_file(self):
        """The file shows 99800 where the messages hold 99900: a difference, and no import."""
        messages, book = ORDINARY[0].iloc[:2], ORDINARY[1].iloc[:2].copy()
        book.loc[1, ["BidPrice2", "BidSize2"]] = [99800, 50]
        report = reconcile(messages, book, CENT, DEPTH, True)
        assert report["LevelsImported"].tolist() == [0]
        assert report["FirstDifferingLevel"].tolist() == [2]
