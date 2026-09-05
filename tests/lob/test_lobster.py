"""Reading LOBSTER files through declared schemas.

The sample files are not in the repository, so everything here is written into ``tmp_path``.
What is worth testing is not that a well-formed file loads -- it is that the schema admits
what the *format* permits and refuses what it does not, and those two sets are not the ones
a reader guesses from a day of data.
"""

import numpy as np
import pandas as pd
import pandera.errors as pe
import pytest

from unito26.lob import frames, lobster
from unito26.lob.lobster import LobsterEvent
from unito26.lob.messages import ReportedDepth, TickGrid

DEPTH = ReportedDepth(2)

# time, type, order id, size, price, direction
ORDINARY = [
    "34200.017459617,1,11885113,21,2238100,1",
    "34200.189607670,4,3911376,20,2239600,-1",
]


def write(path, rows):
    path.write_text("\n".join(rows) + "\n")
    return path


def book_rows(count):
    """Well-formed orderbook rows at ``DEPTH``, second level padded on both sides."""
    return [
        f"2239600,100,2238100,21,{frames.ASK_PADDING},0,{frames.BID_PADDING},0"
        for _ in range(count)
    ]


class TestTheMessageSchemaAdmitsWhatTheFormatWrites:
    """Each of these is a real row that an obvious constraint would reject."""

    def test_a_hidden_execution_carries_no_order_id(self, tmp_path):
        frame = lobster.load_messages(
            write(tmp_path / "m.csv", ["34200.017459617,5,0,1,2238200,-1"])
        )
        assert frame["OrderID"].iloc[0] == 0

    @pytest.mark.parametrize("price,meaning", [(-1, "halted"), (0, "quoting"), (1, "trading")])
    def test_a_halt_writes_a_status_code_where_the_price_goes(self, tmp_path, price, meaning):
        frame = lobster.load_messages(
            write(tmp_path / "m.csv", [f"36023.0,7,0,0,{price},-1"])
        )
        assert frame["Price"].iloc[0] == price
        assert frame["Size"].iloc[0] == 0

    def test_a_sub_penny_hidden_print_is_admitted(self, tmp_path):
        frame = lobster.load_messages(
            write(tmp_path / "m.csv", ["34200.5,5,0,100,2238150,-1"])
        )
        assert frame["Price"].iloc[0] % 100 != 0


class TestTheMessageSchemaRefusesWhatItDoesNot:
    @pytest.mark.parametrize("row", [
        "34200.0,8,1,10,2238100,1",          # no such event type
        "34200.0,1,1,10,2238100,0",          # direction is +1 or -1
        "34200.0,1,1,-5,2238100,1",          # negative size
        "34200.0,1,1,10,-2,1",               # below the halt's -1
    ])
    def test_a_row_outside_the_format_raises(self, tmp_path, row):
        with pytest.raises(pe.SchemaError):
            lobster.load_messages(write(tmp_path / "m.csv", [row]))

    @pytest.mark.parametrize("narrow", ["int8", "Int8"])
    def test_a_narrow_dtype_would_have_laundered_this_one(self, tmp_path, narrow):
        """``Type`` 260 becomes 4 -- a valid execution -- when the column is 8 bits wide.

        Narrowing launders the corruption a declared dtype is supposed to catch: the wrap
        happens inside ``read_csv``, silently, and any membership check then passes.  Read
        as ``int64`` the value survives to be refused, which is why the schema is wide.
        """
        path = write(tmp_path / "m.csv", ["34200.0,260,1,10,2238100,1"])
        laundered = pd.read_csv(
            path, header=None, names=frames.lobster_message_file_columns(),
            dtype={"Type": narrow},
        )
        assert laundered["Type"].iloc[0] == LobsterEvent.EXECUTION_VISIBLE

        with pytest.raises(pe.SchemaError):
            lobster.load_messages(path)


class TestTheClockIsReadFromTheText:
    def test_nanoseconds_are_exact(self, tmp_path):
        frame = lobster.load_messages(write(tmp_path / "m.csv", ORDINARY))
        assert frame["TimeNanoseconds"].tolist() == [34200017459617, 34200189607670]

    def test_more_precision_than_nanoseconds_is_truncated_not_rounded(self, tmp_path):
        frame = lobster.load_messages(
            write(tmp_path / "m.csv", ["36754.716797047004,1,1,10,2238100,1"])
        )
        assert frame["TimeNanoseconds"].iloc[0] == 36754716797047

    def test_a_whole_second_has_no_fraction_to_split(self, tmp_path):
        frame = lobster.load_messages(write(tmp_path / "m.csv", ["34200,1,1,10,2238100,1"]))
        assert frame["TimeNanoseconds"].iloc[0] == 34200_000_000_000

    def test_repeated_instants_survive_as_the_same_key(self, tmp_path):
        rows = ["34200.5,4,1,10,2238100,-1", "34200.5,4,2,10,2238100,-1"]
        frame = lobster.load_messages(write(tmp_path / "m.csv", rows))
        assert frame["TimeNanoseconds"].nunique() == 1


class TestTheOrderbookFileIsItsOwnShape:
    def test_it_loads_with_the_sentinels_intact(self, tmp_path):
        frame = lobster.load_orderbook(write(tmp_path / "b.csv", book_rows(2)), DEPTH)
        assert frame.shape == (2, 4 * DEPTH)
        assert frame["AskPrice2"].iloc[0] == frames.ASK_PADDING
        assert frame["BidPrice2"].iloc[0] == frames.BID_PADDING
        assert frame["AskSize2"].iloc[0] == 0

    def test_it_is_plain_int64_and_not_the_masked_extension_dtype(self, tmp_path):
        frame = lobster.load_orderbook(write(tmp_path / "b.csv", book_rows(1)), DEPTH)
        assert set(frame.dtypes) == {np.dtype("int64")}

    def test_a_fractional_size_raises_instead_of_widening_the_column(self, tmp_path):
        row = f"2239600,100.5,2238100,21,{frames.ASK_PADDING},0,{frames.BID_PADDING},0"
        with pytest.raises(ValueError):
            lobster.load_orderbook(write(tmp_path / "b.csv", [row]), DEPTH)


class TestTheSessionFrameAndTheFileFrameAreDifferentSchemas:
    """Same columns, different index, and the difference is the point."""

    def frame(self, stamps):
        return pd.DataFrame(
            [[10, 1, 9, 2]] * len(stamps),
            columns=frames.lobster_book_columns(ReportedDepth(1)),
            index=pd.Index(np.asarray(stamps, dtype=float), name="TimeStamp"),
        )

    def test_the_file_schema_wants_no_clock_and_the_session_schema_does(self):
        depth = ReportedDepth(1)
        positional = self.frame([1.0]).reset_index(drop=True)
        frames.lobster_orderbook_file_schema(depth).validate(positional)
        with pytest.raises(pe.SchemaError):
            frames.session_book_schema(depth).validate(positional)

    def test_repeated_instants_are_admitted(self):
        """3% of a LOBSTER session, so `unique=True` here would reject the file."""
        assert len(frames.session_book_schema(ReportedDepth(1)).validate(
            self.frame([1.0, 1.0, 1.0])
        )) == 3

    def test_a_clock_that_goes_backwards_is_not(self):
        with pytest.raises(pe.SchemaError):
            frames.session_book_schema(ReportedDepth(1)).validate(self.frame([2.0, 1.0]))

    def test_an_empty_session_validates_as_empty(self):
        assert frames.session_book_schema(ReportedDepth(1)).validate(self.frame([])).empty


# ---- the file pair, the window and the unit -------------------------------------------

NAME = "TICK_2012-06-21_34200000_57600000_{kind}_2.csv"


def pair(tmp_path, times, states=None):
    """A well-formed pair whose ``AskPrice1`` encodes the row, so a slice is identifiable."""
    states = len(times) if states is None else states
    (tmp_path / NAME.format(kind="message")).write_text(
        "".join(f"{t},1,{i + 1},10,2238100,1\n" for i, t in enumerate(times))
    )
    (tmp_path / NAME.format(kind="orderbook")).write_text(
        "".join(
            f"{2240000 + 100 * i},100,2238100,21,{frames.ASK_PADDING},0,"
            f"{frames.BID_PADDING},0\n"
            for i in range(states)
        )
    )
    return lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message"))


class TestTheFilePair:
    def test_either_member_names_the_same_pair(self, tmp_path):
        one = lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message"))
        other = lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="orderbook"))
        assert one == other

    def test_the_depth_comes_from_the_name(self, tmp_path):
        assert lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message")).reported_depth == 2

    def test_the_filename_counts_milliseconds_and_the_span_counts_seconds(self, tmp_path):
        files = lobster.LobsterFiles.parse(tmp_path / NAME.format(kind="message"))
        assert files.start_millisecond == 34200000
        assert files.span == lobster.TradingWindow(34200.0, 57600.0)

    def test_a_name_off_the_convention_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="not a LOBSTER file name"):
            lobster.LobsterFiles.parse(tmp_path / "AMZN_2012-06-21.csv")


class TestTheWindow:
    def test_it_must_open_before_it_closes(self):
        with pytest.raises(ValueError, match="opens before it closes"):
            lobster.TradingWindow(57600.0, 34200.0)

    def test_the_regular_session_is_nasdaq_hours(self):
        assert lobster.NASDAQ_REGULAR_HOURS == lobster.TradingWindow(34200.0, 57600.0)


class TestThePriceUnit:
    def test_a_cent_tick_is_a_hundred_of_lobsters_units(self):
        assert lobster.price_unit(TickGrid(0.01)) == 100

    def test_lobsters_own_unit_is_one(self):
        assert lobster.price_unit(TickGrid(1 / lobster.LOBSTER_UNITS_PER_DOLLAR)) == 1

    def test_a_tick_finer_than_the_file_can_express_is_refused(self):
        with pytest.raises(ValueError, match="not a whole number"):
            lobster.price_unit(TickGrid(0.000001))

    def test_a_book_off_the_grid_is_refused_by_the_column_and_the_row(self, tmp_path):
        files = pair(tmp_path, [34200.5, 34201.5])
        _, book = lobster.load_aligned(files, lobster.NASDAQ_REGULAR_HOURS)
        book.loc[1, "AskPrice1"] = 2240050
        with pytest.raises(ValueError, match="AskPrice1 is 2240050 on row 1"):
            lobster.prices_on_the_tick_grid(book, lobster.price_unit(TickGrid(0.01)), DEPTH)

    def test_the_padding_sentinels_are_not_prices_and_are_skipped(self, tmp_path):
        files = pair(tmp_path, [34200.5])
        _, book = lobster.load_aligned(files, lobster.NASDAQ_REGULAR_HOURS)
        assert frames.ASK_PADDING % 100 != 0
        lobster.prices_on_the_tick_grid(book, lobster.price_unit(TickGrid(0.01)), DEPTH)


class TestTheAlignedRead:
    def test_the_window_selects_by_time_and_not_by_position(self, tmp_path):
        files = pair(tmp_path, [34200.0, 34201.0, 34202.0, 34203.0, 34204.0])
        messages, book = lobster.load_aligned(
            files, lobster.TradingWindow(34201.0, 34203.0)
        )
        assert messages["Time"].tolist() == [34201.0, 34202.0, 34203.0]
        assert book["AskPrice1"].tolist() == [2240100, 2240200, 2240300]

    def test_both_ends_are_closed(self, tmp_path):
        files = pair(tmp_path, [34200.0, 34201.0, 34202.0])
        messages, _ = lobster.load_aligned(files, lobster.TradingWindow(34200.0, 34202.0))
        assert len(messages) == 3

    def test_every_message_sharing_the_closing_instant_is_kept(self, tmp_path):
        """`side="right"` at the close.  The wrong side drops a whole queue split."""
        files = pair(tmp_path, [34200.0, 34201.0, 34201.0, 34201.0])
        messages, book = lobster.load_aligned(
            files, lobster.TradingWindow(34200.5, 34201.0)
        )
        assert len(messages) == 3
        assert book["AskPrice1"].tolist() == [2240100, 2240200, 2240300]

    def test_a_window_outside_what_the_file_covers_is_refused(self, tmp_path):
        files = pair(tmp_path, [34200.0])
        with pytest.raises(ValueError, match="is not inside"):
            lobster.load_aligned(files, lobster.TradingWindow(57600.0, 57700.0))

    def test_a_window_that_names_no_message_is_refused(self, tmp_path):
        files = pair(tmp_path, [34200.0, 57000.0])
        with pytest.raises(ValueError, match="contains no messages"):
            lobster.load_aligned(files, lobster.TradingWindow(40000.0, 41000.0))

    @pytest.mark.parametrize("states,label", [(2, "short"), (4, "long")])
    def test_a_pair_of_unequal_length_is_refused(self, tmp_path, states, label):
        files = pair(tmp_path, [34200.0, 34201.0, 34202.0], states=states)
        with pytest.raises(ValueError, match="not aligned"):
            lobster.load_aligned(files, lobster.NASDAQ_REGULAR_HOURS)

    def test_a_file_without_a_trailing_newline_still_counts(self, tmp_path):
        files = pair(tmp_path, [34200.0, 34201.0])
        path = files.orderbook_path
        path.write_text(path.read_text().rstrip("\n"))
        messages, book = lobster.load_aligned(files, lobster.NASDAQ_REGULAR_HOURS)
        assert len(book) == len(messages) == 2
