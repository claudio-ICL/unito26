"""Round trips through the schema-checked frames, and the frozen examples.

The book round trip runs on every rung, because a variant that keeps an index beside its
dict is the one a careless reconstruction leaves quietly wrong.
"""

import json

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
        assert MarkParams.from_frame(marks.to_frame()) == marks

    def test_the_record_and_json_forms_round_trip(self):
        marks = MarkParams(0.45, 4.0, 0.8, 10)
        assert MarkParams.from_records(marks.to_records()) == marks
        assert MarkParams.from_json(marks.to_json(2)) == marks

    def test_a_decay_outside_the_unit_interval_is_rejected(self):
        frame = MarkParams(0.45, 4.0, 0.8, 10).to_frame()
        frame.loc[0, "DepthDecay"] = 1.5
        with pytest.raises(pandera.errors.SchemaError):
            MarkParams.from_frame(frame)

    def test_certainty_at_the_touch_is_allowed(self):
        # p = 1 puts every order at the touch, which is a parametrisation, not an error.
        marks = MarkParams(1.0, 4.0, 0.8, 10)
        assert MarkParams.from_frame(marks.to_frame()) == marks

    def test_a_missing_column_is_rejected(self):
        frame = MarkParams(0.45, 4.0, 0.8, 10).to_frame().drop(columns=["Lot"])
        with pytest.raises(pandera.errors.SchemaError):
            MarkParams.from_frame(frame)


class TestHawkesParams:
    #: Asymmetric, with four distinct kernel entries: a symmetric fixture round-trips
    #: under transposition and so certifies nothing about the orientation.
    PARAMS = HawkesParams(baseline=[0.3, 0.7], excitation=[[1.0, 2.0], [3.0, 4.0]], decay=60.0)

    def test_round_trip(self):
        back = HawkesParams.from_frame(self.PARAMS.to_frame())
        assert np.allclose(back.baseline, self.PARAMS.baseline)
        assert np.allclose(back.excitation, self.PARAMS.excitation)
        assert back.decay == self.PARAMS.decay

    def test_the_record_form_round_trips(self):
        back = HawkesParams.from_records(self.PARAMS.to_records())
        assert np.allclose(back.excitation, self.PARAMS.excitation)
        assert np.allclose(back.baseline, self.PARAMS.baseline)

    def test_the_off_diagonal_baseline_is_a_json_null(self):
        records = json.loads(self.PARAMS.to_json(0))
        off_diagonal = [r for r in records if r["Component"] != r["Cause"]]
        assert all(r["BaseIntensity"] is None for r in off_diagonal)
        assert HawkesParams.from_json(self.PARAMS.to_json(0)).decay == 60.0

    def test_the_json_file_round_trips(self, tmp_path):
        path = tmp_path / "flow.json"
        self.PARAMS.write_json(path, 2)
        assert np.allclose(HawkesParams.read_json(path).excitation, self.PARAMS.excitation)

    def test_row_order_does_not_matter(self):
        """`from_frame` pivots rather than reshaping.  Reshaping a shuffled frame in row
        order transposes it silently, and no schema can constrain row order."""
        shuffled = self.PARAMS.to_frame().sample(frac=1.0, random_state=0)
        back = HawkesParams.from_frame(shuffled)
        assert np.allclose(back.excitation, self.PARAMS.excitation)

    def test_the_off_diagonal_encoding_is_pinned(self):
        """The only assertion that catches a transpose: a round trip cannot see one, and
        neither can the branching ratio, which is transpose-invariant."""
        frame = self.PARAMS.to_frame()
        row = frame[(frame["Component"] == 0) & (frame["Cause"] == 1)].iloc[0]
        assert row["Kernel"] == 2.0  # excitation[0][1]; a transpose would give 3.0

    def test_the_baseline_sits_on_the_diagonal_and_is_null_off_it(self):
        frame = self.PARAMS.to_frame()
        diagonal = frame["Component"] == frame["Cause"]
        assert frame.loc[diagonal, "BaseIntensity"].tolist() == [0.3, 0.7]
        assert frame.loc[~diagonal, "BaseIntensity"].isna().all()

    def test_two_decays_are_rejected(self):
        frame = self.PARAMS.to_frame()
        frame.loc[0, "Decay"] = 30.0
        with pytest.raises(ValueError, match="shared by every pair"):
            HawkesParams.from_frame(frame)

    def test_an_incomplete_grid_is_rejected(self):
        frame = self.PARAMS.to_frame().iloc[:3]
        with pytest.raises(ValueError):
            HawkesParams.from_frame(frame)


@pytest.mark.parametrize("book_cls", AXIS_B_VARIANTS, ids=lambda c: c.__name__)
class TestBookFrame:
    def round_trip(self, book_cls, bids, asks, depth):
        depth = ReportedDepth(depth)
        book = book_cls.from_levels(bids, asks)
        row = book.to_lobster_row(PRICE_UNIT, depth)
        frame = frames.lobster_book_schema(depth).validate(
            pd.DataFrame([row], columns=frames.lobster_book_columns(depth))
        )
        back = book_cls.from_lobster_row(frame.iloc[0], PRICE_UNIT, depth)
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
            book_cls.from_lobster_row(frame.iloc[0], PRICE_UNIT, ReportedDepth(1))

    @pytest.mark.parametrize(
        "bids,asks,depth",
        [
            ({998: 150}, {999: 100, 1002: 120, 1003: 180}, 3),
            ({100: 5, 97: 6, 93: 7}, {110: 8}, 4),
            ({100: 5}, {110: 8, 111: 9}, 3),
            ({}, {110: 8}, 2),
            ({100: 5}, {}, 2),
        ],
    )
    def test_writing_in_place_matches_building_a_row(self, book_cls, bids, asks, depth):
        """`write_lobster_row` is overridden on the array-backed rung; the two must not
        drift apart, padding on either side included."""
        depth = ReportedDepth(depth)
        book = book_cls.from_levels(bids, asks)
        out = np.zeros((1, 4 * depth), dtype=np.int64)
        book.write_lobster_row(out, 0, PRICE_UNIT, depth)
        assert out[0].tolist() == book.to_lobster_row(PRICE_UNIT, depth)


class TestFrozenExamples:
    def test_the_flow_reserialises_to_the_frozen_records(self):
        assert config.example_order_flow_params().to_records() == config.EXAMPLE_ORDER_FLOW_PARAMS

    def test_the_marks_reserialise_to_the_frozen_records(self):
        assert config.example_mark_params().to_records() == config.EXAMPLE_MARK_PARAMS

    def test_the_documented_properties_survive_the_freezing(self):
        """The construction that produced these numbers is gone, so what it was built to
        achieve is asserted here instead."""
        params = config.example_order_flow_params()
        assert params.branching_ratio == pytest.approx(0.6)
        replenishment = params.excitation[EventType.LIMIT_SELL, EventType.MARKET_BUY]
        reverse = params.excitation[EventType.MARKET_BUY, EventType.LIMIT_SELL]
        assert replenishment > 5 * reverse

    def test_the_flow_composition_is_the_declared_one(self):
        """The baselines were read off a target stationary intensity, so the target is
        what has to be asserted; the baselines themselves carry no interpretation."""
        stationary = config.example_order_flow_params().stationary_intensity()
        limit = stationary[[EventType.LIMIT_BUY, EventType.LIMIT_SELL]].sum()
        consuming = stationary.sum() - limit
        assert stationary.sum() == pytest.approx(30.1878, abs=1e-3)
        assert limit / consuming == pytest.approx(0.98, abs=1e-6)

    def test_the_baselines_are_admissible(self):
        """``mu = (I - Gamma) lambda*`` is a baseline only where it is non-negative, and
        the market-order component is the one that binds."""
        params = config.example_order_flow_params()
        assert (params.baseline > 0).all()
        assert params.baseline.argmin() in (EventType.MARKET_BUY, EventType.MARKET_SELL)

    def test_the_three_depth_regimes_are_distinct(self):
        assert (
            config.shallow_mark_params().depth_decay
            > config.example_mark_params().depth_decay
            > config.deep_mark_params().depth_decay
        )
