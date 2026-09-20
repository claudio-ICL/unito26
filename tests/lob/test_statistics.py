"""The declaration: one statement of the column names, their order and their kind.

Everything about a statistics frame is read off ``SessionStatistics``: the schemas, the
coverage flags, and the positions the fold writes into.  These tests pin the declaration
itself, because the reconciliation between the two statistics routes cannot -- it compares
columns by name and so is blind to a transposed pair whose values happen to agree on the
fixtures, which four of the twelve gap columns do.
"""

import pandas as pd
import pandera.errors as pe
import pytest

from unito26.lob.messages import GridDepth, SweepSize
from unito26.lob.statistics import GAP_COLUMNS, Dependence, SessionStatistics

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


class TestCoverageIsAFieldNotASpelling:
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


class TestDependenceIsAFieldNotASpelling:
    """What a statistic reads decides what regrouping the rows does to it."""

    def test_a_statistic_of_one_configuration_says_so(self):
        for name in ("Spread", "MidPrice", "QueueImbalance1", "SweepCostBuy100Covered"):
            assert _declared(name).dependence is Dependence.CONFIGURATION

    def test_the_order_flow_contribution_reads_two(self):
        assert _declared("OrderFlowContribution").dependence is Dependence.INCREMENT

    def test_a_rolling_column_reads_a_window(self):
        for name in ("OrderFlowImbalance10", "AverageDepth10", "VWAP10", "VWAPBuy10"):
            assert _declared(name).dependence is Dependence.WINDOW

    def test_the_traded_quantities_are_extensive(self):
        for name in ("Volume", "SignedVolume", "TradedValue"):
            assert _declared(name).dependence is Dependence.EXTENSIVE

    def test_every_declared_column_carries_one(self):
        for column in SPEC.declaration() + SPEC.trade_declaration():
            assert isinstance(column.dependence, Dependence)


class TestThePositionalSchemasAreNotTheClockedOnes:
    """The same columns, laid out over a file's rows rather than over a clock."""

    def test_the_clocked_schema_wants_a_named_float_index(self):
        assert SPEC.statistics_schema().index.name == "TimeStamp"
        assert SPEC.positional_statistics_schema().index.name is None

    def test_a_positional_frame_is_refused_by_the_clocked_schema(self):
        frame = _statistics_frame(pd.RangeIndex(2))
        SPEC.positional_statistics_schema().validate(frame)
        with pytest.raises(pe.SchemaError):
            SPEC.statistics_schema().validate(frame)

    def test_a_clocked_frame_is_refused_by_the_positional_schema(self):
        frame = _statistics_frame(pd.Index([1.0, 2.0], name="TimeStamp"))
        SPEC.statistics_schema().validate(frame)
        with pytest.raises(pe.SchemaError):
            SPEC.positional_statistics_schema().validate(frame)

    def test_the_columns_are_the_same_ones(self):
        assert list(SPEC.statistics_schema().columns) == list(
            SPEC.positional_statistics_schema().columns
        )


def _declared(name):
    for column in SPEC.declaration() + SPEC.trade_declaration():
        if column.name == name:
            return column
    raise AssertionError(f"{name} is not declared")


def _statistics_frame(index):
    return pd.DataFrame(
        {column.name: [0.0, 1.0] for column in SPEC.declaration()}, index=index
    )
