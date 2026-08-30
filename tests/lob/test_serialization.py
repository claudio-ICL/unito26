"""Round trips through the schema-checked frames, and the frozen examples.

The book round trip runs on every rung, because a variant that keeps an index beside its
dict is exactly the one a careless reconstruction leaves quietly wrong.
"""

import numpy as np
import pandas as pd
import pandera.errors
import pytest

from unito26.lob import config, frames
from unito26.lob.hawkes import HawkesParams
from unito26.lob.messages import BUY, SELL, ReportedDepth
from unito26.lob.orderbook import AXIS_B_VARIANTS
from unito26.lob.simulate import EventType, MarkParams

PRICE_UNIT = 100


class TestMarkParams:
    def test_round_trip(self):
        marks = MarkParams(depth_decay=0.45, mean_log_size=4.0, sigma_log_size=0.8, lot=10)
        assert frames.mark_params_from_frame(frames.mark_params_to_frame(marks)) == marks

    def test_a_decay_outside_the_unit_interval_is_rejected(self):
        frame = frames.mark_params_to_frame(MarkParams(0.45, 4.0, 0.8, 10))
        frame.loc[0, "DepthDecay"] = 1.5
        with pytest.raises(pandera.errors.SchemaError):
            frames.mark_params_from_frame(frame)

    def test_certainty_at_the_touch_is_allowed(self):
        # p = 1 puts every order at the touch, which is a parametrisation, not an error.
        marks = MarkParams(1.0, 4.0, 0.8, 10)
        assert frames.mark_params_from_frame(frames.mark_params_to_frame(marks)) == marks

    def test_a_missing_column_is_rejected(self):
        frame = frames.mark_params_to_frame(MarkParams(0.45, 4.0, 0.8, 10)).drop(columns=["Lot"])
        with pytest.raises(pandera.errors.SchemaError):
            frames.mark_params_from_frame(frame)


class TestHawkesParams:
    #: Asymmetric, with four distinct kernel entries: a symmetric fixture round-trips
    #: under transposition and so certifies nothing about the orientation.
    PARAMS = HawkesParams(baseline=[0.3, 0.7], excitation=[[1.0, 2.0], [3.0, 4.0]], decay=60.0)

    def test_round_trip(self):
        back = frames.hawkes_params_from_frame(frames.hawkes_params_to_frame(self.PARAMS))
        assert np.allclose(back.baseline, self.PARAMS.baseline)
        assert np.allclose(back.excitation, self.PARAMS.excitation)
        assert back.decay == self.PARAMS.decay

    def test_row_order_does_not_matter(self):
        """`from_frame` pivots rather than reshaping.  Reshaping a shuffled frame in row
        order transposes it silently, and no schema can constrain row order."""
        shuffled = frames.hawkes_params_to_frame(self.PARAMS).sample(frac=1.0, random_state=0)
        back = frames.hawkes_params_from_frame(shuffled)
        assert np.allclose(back.excitation, self.PARAMS.excitation)

    def test_the_off_diagonal_encoding_is_pinned(self):
        """The only assertion that catches a transpose: a round trip cannot see one, and
        neither can the branching ratio, which is transpose-invariant."""
        frame = frames.hawkes_params_to_frame(self.PARAMS)
        row = frame[(frame["Component"] == 0) & (frame["Cause"] == 1)].iloc[0]
        assert row["Kernel"] == 2.0  # excitation[0][1]; a transpose would give 3.0

    def test_the_baseline_sits_on_the_diagonal_and_is_null_off_it(self):
        frame = frames.hawkes_params_to_frame(self.PARAMS)
        diagonal = frame["Component"] == frame["Cause"]
        assert frame.loc[diagonal, "BaseIntensity"].tolist() == [0.3, 0.7]
        assert frame.loc[~diagonal, "BaseIntensity"].isna().all()

    def test_two_decays_are_rejected(self):
        frame = frames.hawkes_params_to_frame(self.PARAMS)
        frame.loc[0, "Decay"] = 30.0
        with pytest.raises(ValueError, match="shared by every pair"):
            frames.hawkes_params_from_frame(frame)

    def test_an_incomplete_grid_is_rejected(self):
        frame = frames.hawkes_params_to_frame(self.PARAMS).iloc[:3]
        with pytest.raises(ValueError):
            frames.hawkes_params_from_frame(frame)


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestBookFrame:
    def round_trip(self, book_cls, bids, asks, depth):
        book = book_cls.from_levels(bids, asks)
        row = frames.book_to_lobster_row(book, PRICE_UNIT, ReportedDepth(depth))
        frame = frames.lobster_book_schema(ReportedDepth(depth)).validate(
            pd.DataFrame([row], columns=frames.lobster_book_columns(ReportedDepth(depth)))
        )
        back = frames.book_from_lobster_row(book_cls, frame.iloc[0], PRICE_UNIT, ReportedDepth(depth))
        return book, back, frame

    def test_case_b_round_trips(self, book_cls):
        book, back, _ = self.round_trip(book_cls, {998: 150}, {999: 100, 1002: 120, 1003: 180}, 3)
        assert back.levels_map(BUY) == book.levels_map(BUY)
        assert back.levels_map(SELL) == book.levels_map(SELL)

    def test_interior_gaps_survive(self, book_cls):
        book, back, _ = self.round_trip(book_cls, {100: 5, 97: 6, 93: 7}, {110: 8}, 3)
        assert back.levels_map(BUY) == book.levels_map(BUY)

    def test_a_short_ask_side_pads_with_its_own_sentinel(self, book_cls):
        _, back, frame = self.round_trip(book_cls, {100: 5, 99: 6}, {110: 8}, 3)
        # The two sentinels have opposite signs; a filter for one lets the other through.
        assert frame["AskPrice2"].iloc[0] == frames.ASK_PADDING
        assert frame["AskSize2"].iloc[0] == 0
        assert back.levels_map(SELL) == {110: 8}

    def test_a_short_bid_side_pads_with_its_own_sentinel(self, book_cls):
        _, back, frame = self.round_trip(book_cls, {100: 5}, {110: 8, 111: 9, 112: 1}, 3)
        assert frame["BidPrice2"].iloc[0] == frames.BID_PADDING
        assert back.levels_map(BUY) == {100: 5}

    def test_an_empty_side_round_trips_to_nothing(self, book_cls):
        _, back, _ = self.round_trip(book_cls, {}, {110: 8}, 2)
        assert back.levels_map(BUY) == {}
        assert back.levels_map(SELL) == {110: 8}

    def test_an_off_grid_price_is_refused(self, book_cls):
        _, _, frame = self.round_trip(book_cls, {100: 5}, {110: 8}, 1)
        frame.loc[frame.index[0], "AskPrice1"] = 11001
        with pytest.raises(ValueError, match="not a multiple"):
            frames.book_from_lobster_row(book_cls, frame.iloc[0], PRICE_UNIT, ReportedDepth(1))


class TestFrozenExamples:
    def test_the_flow_reserialises_to_the_frozen_constant(self):
        params = config.example_order_flow_params()
        assert frames.to_json(frames.hawkes_params_to_frame(params)) == config.EXAMPLE_ORDER_FLOW_PARAMS

    def test_the_marks_reserialise_to_the_frozen_constant(self):
        marks = config.example_mark_params()
        assert frames.to_json(frames.mark_params_to_frame(marks)) == config.EXAMPLE_MARK_PARAMS

    def test_the_documented_properties_survive_the_freezing(self):
        """The construction that produced these numbers is gone, so what it was built to
        achieve is asserted here instead."""
        params = config.example_order_flow_params()
        assert params.branching_ratio == pytest.approx(0.8)
        replenishment = params.excitation[EventType.LIMIT_SELL, EventType.MARKET_BUY]
        reverse = params.excitation[EventType.MARKET_BUY, EventType.LIMIT_SELL]
        assert replenishment > 5 * reverse

    def test_the_two_regimes_differ_in_depth(self):
        assert config.shallow_mark_params().depth_decay > config.deep_mark_params().depth_decay
