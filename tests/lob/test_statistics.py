"""The declaration: one statement of the column names, their order and their kind.

Everything about a statistics frame is read off ``SessionStatistics``: the schemas, the
coverage flags, and the positions the fold writes into.  These tests pin the declaration
itself, because the reconciliation between the two statistics routes cannot -- it compares
columns by name and so is blind to a transposed pair whose values happen to agree on the
fixtures, which four of the twelve gap columns do.
"""

import pytest

from unito26.lob.messages import GridDepth, SweepSize
from unito26.lob.statistics import GAP_COLUMNS, SessionStatistics

SPEC = SessionStatistics((GridDepth(1), GridDepth(5)), (SweepSize(100),), (10,))


class TestTheDeclaredOrder:
    """Written out rather than generated: a generated expectation would restate the code."""

    def test_the_row_is_declared_in_the_order_the_fold_writes_it(self):
        assert list(SPEC.row_schema().columns) == [
            "Spread", "MidPrice", "MicroPrice",
            "QueueImbalance1", "QueueImbalance1Covered",
            "QueueImbalance5", "QueueImbalance5Covered",
            "SweepCostBuy100", "SweepCostBuy100Covered",
            "SweepCostSell100", "SweepCostSell100Covered",
            "OrderFlowContribution", "TouchDepth",
        ] + GAP_COLUMNS

    def test_the_frame_adds_the_rolling_columns_after_the_row(self):
        assert list(SPEC.statistics_schema().columns) == list(SPEC.row_schema().columns) + [
            "OrderFlowImbalance10", "OrderFlowImbalance10Covered", "AverageDepth10",
        ]

    def test_the_trades_frame_is_the_three_counters_then_the_vwaps(self):
        assert list(SPEC.trades_schema().columns) == [
            "Volume", "SignedVolume", "TradedValue", "VWAP10", "VWAPBuy10", "VWAPSell10",
        ]

    def test_a_window_orders_its_columns_by_the_window(self):
        spec = SessionStatistics((GridDepth(1),), (SweepSize(100),), (10, 2))
        assert [c for c in spec.statistics_schema().columns if c.startswith("AverageDepth")] == [
            "AverageDepth2", "AverageDepth10"
        ]


class TestTheKindIsAFieldNotASpelling:
    def test_a_flag_is_constrained_to_zero_or_one(self):
        column = SPEC.row_schema().columns["QueueImbalance1Covered"]
        assert not column.nullable
        assert column.checks

    def test_a_value_may_be_missing(self):
        assert SPEC.row_schema().columns["MicroPrice"].nullable

    def test_the_flags_are_exactly_the_covered_columns(self):
        flagged = {c.name for c in SPEC.declaration() if c.covered}
        assert flagged == {c for c in SPEC.statistics_schema().columns if c.endswith("Covered")}


class TestTheLayoutIsDerivedFromTheDeclaration:
    """The fold indexes by these integers.  Each must land on the column it names."""

    def at(self, offset):
        return list(SPEC.row_schema().columns)[offset]

    def test_the_touch_statistics_land_where_they_are_named(self):
        assert self.at(SPEC.layout.spread) == "Spread"
        assert self.at(SPEC.layout.mid_price) == "MidPrice"
        assert self.at(SPEC.layout.micro_price) == "MicroPrice"
        assert self.at(SPEC.layout.order_flow) == "OrderFlowContribution"
        assert self.at(SPEC.layout.touch_depth) == "TouchDepth"

    def test_each_family_lands_on_its_value_with_its_flag_next(self):
        for offset, n in zip(SPEC.layout.imbalance, SPEC.imbalance_levels):
            assert self.at(offset) == f"QueueImbalance{n}"
            assert self.at(offset + 1) == f"QueueImbalance{n}Covered"
        for (buy, sell), size in zip(SPEC.layout.sweep, SPEC.sweep_sizes):
            assert self.at(buy) == f"SweepCostBuy{size}"
            assert self.at(buy + 1) == f"SweepCostBuy{size}Covered"
            assert self.at(sell) == f"SweepCostSell{size}"
            assert self.at(sell + 1) == f"SweepCostSell{size}Covered"

    def test_the_gaps_are_the_tail_the_writer_fills_by_slice(self):
        assert list(SPEC.row_schema().columns)[SPEC.layout.gaps] == GAP_COLUMNS

    def test_the_buffer_is_sized_to_the_row_and_the_gaps_reach_its_end(self):
        assert SPEC.layout.gaps.stop == len(SPEC.row_schema().columns)


class TestDegenerateSpecifications:
    def test_a_specification_may_name_no_levels_and_no_sizes(self):
        spec = SessionStatistics((), (), (1,))
        assert spec.layout.imbalance == ()
        assert spec.layout.sweep == ()
        assert list(spec.row_schema().columns)[:3] == ["Spread", "MidPrice", "MicroPrice"]

    @pytest.mark.parametrize("field", ["imbalance_levels", "sweep_sizes", "windows"])
    def test_a_fractional_parameter_is_refused(self, field):
        argument = {"imbalance_levels": (), "sweep_sizes": (), "windows": (1,)}
        with pytest.raises(ValueError, match="whole number"):
            SessionStatistics(**{**argument, field: (1.5,)})
