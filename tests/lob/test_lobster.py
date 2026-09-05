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
from unito26.lob.messages import ReportedDepth

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
