"""Regressing the mid-price change on the imbalances.

Two regressions, and the distinction between them is the subject.  The
**contemporaneous** one puts the change in ``P^m`` over ``(t - w, t]`` on ``OFI_{t,w}``:
Cont, Kukanov and Stoikov's regression, and a statement about price *formation*.  The
**predictive** one puts the change over ``(t, t + h]`` on ``OFI_{t,w}`` and ``I^n_t``: a
statement about *forecasting*.  The alignment functions below are what keeps the two
apart, and getting one of their edges wrong turns the second silently into the first.

Pure analysis.  It simulates nothing and folds nothing: it takes a ``MarketSession`` and
returns records.  Sessions are built with ``from_occupied_levels`` and read through the
``Covered`` flags, because the frame route writes NaN where coverage fails while the
online route writes the book's true value with the flag at zero -- so a module that reads
the values alone gives different answers to the two routes.

Windows here are seconds and need not be whole.  ``SessionStatistics`` refuses a
fractional window because a window is part of a *column name* there; these results are
long form, where a window is a value in a column.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob.frames import FrameSerializable
from unito26.lob.messages import GridDepth, Horizon, Window
from unito26.lob.session import MarketSession, rolling_sum, window_start
from unito26.lob.statistics import _span

__all__ = [
    "AlignedSeries",
    "aligned_mid_price",
    "aligned_order_flow",
    "backward_sum",
    "backward_change",
    "forward_change",
    "forward_change_to_next_event",
    "Predictors",
    "predictors",
    "outcome_classes",
    "signed_covariance",
    "signed_covariance_terms",
    "sign_accuracy",
    "NestedFit",
    "nested_fit",
    "lag_buckets",
    "joint_f",
    "tune_window",
    "RegressionResults",
    "NestedFits",
]


@dataclass(frozen=True, slots=True)
class AlignedSeries:
    """A clock, the values read on it, and which segment each row belongs to.

    The three travel together because they are one object.  Two adjacent float arrays are
    exactly the pair a caller exchanges in silence, and the segment index is not a third
    array to be forgotten: a difference that spans a boundary is undefined, not zero.

    A segment ends wherever a side of the book empties, since ``P^m`` does not exist there
    and neither does ``e_n``.  At the example parametrization no side ever empties, so
    there is one segment and the mask removes nothing -- which is why it is written and
    asserted rather than omitted.  It costs one comparison per row, and it is what fails
    loudly if a rung of a ladder wanders out of the regime.
    """

    times: np.ndarray
    values: np.ndarray
    segments: np.ndarray

    def __post_init__(self) -> None:
        if not (self.times.shape == self.values.shape == self.segments.shape):
            raise ValueError(
                f"times {self.times.shape}, values {self.values.shape} and segments "
                f"{self.segments.shape} must agree"
            )

    def __len__(self) -> int:
        return self.times.size


def _segments(session: MarketSession) -> np.ndarray:
    """A segment index that increments wherever the book is not two-sided.

    Read off ``Spread``, which is NaN exactly where a side is missing: the mid-price is
    then undefined too, so a difference across such a row is not a price change.
    """
    broken = ~np.isfinite(session.stats["Spread"].to_numpy(dtype=float))
    return np.cumsum(broken)


def aligned_mid_price(session: MarketSession) -> AlignedSeries:
    """``P^m`` in ticks, on the session's clock, with its segments."""
    return AlignedSeries(
        times=session.lobster_book.index.to_numpy(dtype=float),
        values=session.stats["MidPrice"].to_numpy(dtype=float),
        segments=_segments(session),
    )


def aligned_order_flow(session: MarketSession) -> AlignedSeries:
    """``e_n``, the order-flow contribution of each event, with its segments."""
    return AlignedSeries(
        times=session.lobster_book.index.to_numpy(dtype=float),
        values=session.stats["OrderFlowContribution"].to_numpy(dtype=float),
        segments=_segments(session),
    )


# ---- alignment ---------------------------------------------------------------------------


def backward_sum(series: AlignedSeries, window: Window) -> np.ndarray:
    """``sum`` of the values over ``(t - w, t]``, NaN where any of them is.

    Two sums rather than one: a NaN inside a cumulative sum poisons every window after it,
    where counting the undefined rows confines it to the windows that contain one.

    The NaN rule has two clauses and neither is a run-off.  A window reaching before row 0
    sums the rows it has, rather than going undefined; the opening seconds of a session are
    NaN *through* ``e_0``, which is undefined because ``e_n`` reads two states.  So a row
    is dropped when its window contains an undefined ``e_n`` -- row 0, every empty-side
    row, **and the row after one**.
    """
    window = _span("window", window)
    start = window_start(series.times, window)
    missing = rolling_sum(start, np.isnan(series.values).astype(float))
    return np.where(missing > 0, np.nan, rolling_sum(start, np.nan_to_num(series.values)))


def backward_change(series: AlignedSeries, window: Window) -> np.ndarray:
    """``P^m_t`` minus ``P^m`` at the row *before* the window opened.

    The base is ``window_start(t) - 1`` and not ``window_start(t)``.  At the latter the
    event opening the window sits inside ``OFI`` while its own price effect sits outside
    the change, the telescoping the mechanical regression rests on breaks, and the slope is
    biased toward zero by an amount that grows as ``w`` shrinks.

    NaN where the window reaches row 0, there being no earlier state to difference against.
    """
    window = _span("window", window)
    start = window_start(series.times, window)
    base = start - 1
    out = np.where(base >= 0, series.values - series.values[np.maximum(base, 0)], np.nan)
    return np.where(series.segments == series.segments[np.maximum(base, 0)], out, np.nan)


def forward_change(series: AlignedSeries, horizon: Horizon) -> np.ndarray:
    """``P^m`` at ``t + h`` minus ``P^m`` at ``t``, NaN where no row lies strictly after.

    The two edges take different conventions and each is deliberate.  Ties **at** ``t + h``
    belong to the outcome: it is measured at that instant, so the last row bearing the
    timestamp is the right one, and ``searchsorted(..., "right") - 1`` picks it.  The
    hazard is at the *base*, where several rows may share the timestamp ``t`` -- ``P^m_n``
    is then one of several states at one clock reading, and the regressor must read the
    same one.  So the base is the row itself, by index, and never by a lookup on its time.
    """
    horizon = _span("horizon", horizon)
    ahead = np.searchsorted(series.times, series.times + horizon, side="right") - 1
    rows = np.arange(series.times.size)
    valid = (ahead > rows) & (series.segments[np.maximum(ahead, 0)] == series.segments)
    return np.where(valid, series.values[np.maximum(ahead, 0)] - series.values, np.nan)


def forward_change_to_next_event(series: AlignedSeries) -> np.ndarray:
    """``P^m_{n+1} - P^m_n``: the shortest horizon there is, one event.

    Not a special case of :func:`forward_change` with a small ``h``: the horizon is the
    *event* rather than a duration, so it does not shrink to nothing as the flow speeds up.
    """
    out = np.full(series.times.size, np.nan)
    same = series.segments[1:] == series.segments[:-1]
    out[:-1] = np.where(same, np.diff(series.values), np.nan)
    return out


# ---- predictors ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Predictors:
    """The four statistics compared, on one row set.

    One row set or no comparison.  Two predictors evaluated on the rows each of them
    happens to define are two samples answering two questions, and a reading in which they
    swap places between metrics is the symptom.
    """

    order_flow_imbalance: np.ndarray
    last_contribution: np.ndarray
    queue_imbalance: np.ndarray
    normalised_imbalance: np.ndarray
    mean_depth: np.ndarray
    defined: np.ndarray
    """Rows where every predictor is defined: the common row set, and a **gate**."""


def predictors(session: MarketSession, window: Window, levels: GridDepth) -> Predictors:
    """``OFI_{t,w}``, ``e_n``, ``I^n_t`` and the depth-normalised ``OFI``.

    The depth divisor is the study's own recomputation of ``AverageDepth``, and it has to
    be: the declared column exists only for the *whole* windows named in the specification,
    and these are floats.  A test asserts the two agree where both exist, without which the
    package would carry two mean depths.

    ``AverageDepth`` counts rows with a finite ``TouchDepth`` while ``OFI``'s row set also
    excludes the row after an empty side, so within one window the two averages run over
    slightly different rows.  Recorded here because it is the kind of discrepancy that gets
    simplified away.
    """
    flow = aligned_order_flow(session)
    imbalance = session.stats[f"QueueImbalance{levels}"].to_numpy(dtype=float)
    covered = session.stats[f"QueueImbalance{levels}Covered"].to_numpy(dtype=float) > 0

    window = _span("window", window)
    start = window_start(flow.times, window)
    depth = session.stats["TouchDepth"].to_numpy(dtype=float)
    measured = np.isfinite(depth).astype(float)
    rows = rolling_sum(start, measured)
    # A window with no finite TouchDepth has no mean depth.  Guarding the divisor rather
    # than the result: np.where evaluates both branches.
    mean_depth = np.divide(
        rolling_sum(start, np.nan_to_num(depth)), 2 * rows,
        out=np.full(rows.shape, np.nan), where=rows > 0,
    )

    ofi = backward_sum(flow, window)
    last = flow.values
    normalised = ofi / mean_depth

    defined = (
        np.isfinite(ofi)
        & np.isfinite(last)
        & np.isfinite(imbalance)
        & covered
        & np.isfinite(mean_depth)
    )
    return Predictors(
        order_flow_imbalance=ofi,
        last_contribution=last,
        queue_imbalance=np.where(covered, imbalance, np.nan),
        normalised_imbalance=normalised,
        mean_depth=mean_depth,
        defined=defined,
    )


# ---- the records ---------------------------------------------------------------------------


_KEYS = {
    "Configuration": pa.Column(str, coerce=True),
    "Predictor": pa.Column(str, coerce=True),
    "Window": pa.Column(float, pa.Check.gt(0.0), coerce=True),
    "Horizon": pa.Column(float, pa.Check.gt(0.0), nullable=True, coerce=True),
    "Seed": pa.Column("Int64", pa.Check.ge(0), coerce=True),
}


@dataclass(frozen=True, slots=True)
class RegressionResults(FrameSerializable):
    """The long-form result table, keyed on configuration, predictor, ``w``, ``h`` and seed.

    The serializable object is the **table** and not a row.  Every other
    ``FrameSerializable`` here is one object to one frame -- ``MarkParams.from_frame``
    raises on more than one row -- so a one-row result class could not carry a long-form
    set at all.

    ``SurvivingRows`` is a gate rather than a diagnostic: away from the opening ``w`` of a
    session it is 1 by construction at the example parametrization, since no ``e_n`` is
    undefined there.  A rung reporting less has left the regime, and the run says so
    instead of quietly conditioning on a two-sided book.
    """

    table: pd.DataFrame

    @classmethod
    def schema(cls) -> pa.DataFrameSchema:
        return pa.DataFrameSchema(
            {
                **_KEYS,
                "EventsPerWindow": pa.Column(float, coerce=True),
                "EventsPerTimescale": pa.Column(float, coerce=True),
                "WindowOccupancy": pa.Column(float, coerce=True),
                "Rows": pa.Column("Int64", pa.Check.ge(0), coerce=True),
                "EffectiveRows": pa.Column(float, nullable=True, coerce=True),
                "SurvivingRows": pa.Column(float, pa.Check.in_range(0.0, 1.0), coerce=True),
                "Slope": pa.Column(float, nullable=True, coerce=True),
                "SlopeError": pa.Column(float, nullable=True, coerce=True),
                "RSquared": pa.Column(float, nullable=True, coerce=True),
                "ParticipationRatio": pa.Column(float, nullable=True, coerce=True),
                "SignedCovariance": pa.Column(float, nullable=True, coerce=True),
                "SignedCovarianceLow": pa.Column(float, nullable=True, coerce=True),
                "SignedCovarianceHigh": pa.Column(float, nullable=True, coerce=True),
                "LogScoreSkill": pa.Column(float, nullable=True, coerce=True),
                "BrierSkill": pa.Column(float, nullable=True, coerce=True),
                "KendallTau": pa.Column(float, nullable=True, coerce=True),
                "SignAccuracy": pa.Column(float, nullable=True, coerce=True),
                "Coverage": pa.Column(float, nullable=True, coerce=True),
                "BaseRate": pa.Column(float, nullable=True, coerce=True),
            },
            strict=True,
        )

    def to_frame(self) -> pd.DataFrame:
        return self.schema().validate(self.table.reset_index(drop=True))

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "RegressionResults":
        return cls(table=cls.schema().validate(frame.reset_index(drop=True)))


@dataclass(frozen=True, slots=True)
class NestedFits(FrameSerializable):
    """The nested fit, on the same five keys but without a single predictor.

    It produces ``b1``, ``b2``, their standard errors *and their covariance*, the joint
    ``F`` over the lag buckets and the incremental skill, none of which fits a table keyed
    by one predictor name.  A pseudo-predictor row would lose the covariance, which is the
    one number a reader needs to test anything about ``b1 + b2``.
    """

    table: pd.DataFrame

    @classmethod
    def schema(cls) -> pa.DataFrameSchema:
        keys = {name: column for name, column in _KEYS.items() if name != "Predictor"}
        return pa.DataFrameSchema(
            {
                **keys,
                "Rows": pa.Column("Int64", pa.Check.ge(0), coerce=True),
                "LastCoefficient": pa.Column(float, nullable=True, coerce=True),
                "WindowCoefficient": pa.Column(float, nullable=True, coerce=True),
                "LastError": pa.Column(float, nullable=True, coerce=True),
                "WindowError": pa.Column(float, nullable=True, coerce=True),
                "Covariance": pa.Column(float, nullable=True, coerce=True),
                "BucketF": pa.Column(float, nullable=True, coerce=True),
                "BucketDegreesOfFreedom": pa.Column("Int64", pa.Check.ge(0), coerce=True),
                "IncrementalSkill": pa.Column(float, nullable=True, coerce=True),
                "IncrementalSkillLow": pa.Column(float, nullable=True, coerce=True),
                "IncrementalSkillHigh": pa.Column(float, nullable=True, coerce=True),
            },
            strict=True,
        )

    def to_frame(self) -> pd.DataFrame:
        return self.schema().validate(self.table.reset_index(drop=True))

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "NestedFits":
        return cls(table=cls.schema().validate(frame.reset_index(drop=True)))


# ---- the metrics ---------------------------------------------------------------------------


def outcome_classes(change: np.ndarray) -> np.ndarray:
    """``down``, ``flat``, ``up`` as 0, 1, 2 -- the three classes the log score is over."""
    return np.sign(np.asarray(change, dtype=float)).astype(int) + 1


def signed_covariance_terms(predictor: np.ndarray, change: np.ndarray) -> np.ndarray:
    """The three per-row terms of ``Cov(sign(x), dP)``, for a paired bootstrap.

    The covariance form and not the raw ``E[sign(x) dP]``.  Under independence the product
    is ``E[sign x] E[dP]``, which is zero only if a factor is, and the model has no anchor
    for the price level: per seed ``E[dP]`` is a random drift with a standard deviation of
    about 0.002 ticks an event, larger than the effects being reported.  Any predictor with
    a non-zero mean sign inherits it, and since the drift is a random effect *across* seeds
    it widens every interval too.

    Returned as ``(sign * change, sign, change)`` so that a resample of the three means
    gives the covariance, and so that differences between predictors share one index set.
    """
    sign = np.sign(np.asarray(predictor, dtype=float))
    change = np.asarray(change, dtype=float)
    return np.column_stack([sign * change, sign, change])


def signed_covariance(predictor: np.ndarray, change: np.ndarray) -> float:
    """``E[sign(x) dP] - E[sign(x)] E[dP]``, in ticks per event.

    Uses every row, conditions on nothing and weights by magnitude.  Reported **gross**:
    subtracting a half-spread per row from a per-row quantity guarantees a negative number
    by arithmetic and models nothing, so the honest line is that this is not a strategy.
    """
    terms = signed_covariance_terms(predictor, change).mean(axis=0)
    return float(terms[0] - terms[1] * terms[2])


def sign_accuracy(predictor: np.ndarray, change: np.ndarray) -> tuple[float, float, float]:
    """``(accuracy, coverage, base rate)`` on the rows where both signs are non-zero.

    The three travel together because the accuracy alone is unreadable.  Conditioning on a
    non-zero *move* selects on the outcome by a rule correlated with the regressor;
    conditioning on a non-zero *predictor* gives each predictor its own sample.  Accuracies
    under different conditioning are not comparable, and a point or two of difference at a
    handful of seeds is noise.
    """
    predicted = np.sign(np.asarray(predictor, dtype=float))
    realised = np.sign(np.asarray(change, dtype=float))
    scored = (predicted != 0) & (realised != 0)
    if not scored.any():
        return float("nan"), 0.0, float("nan")
    hits = float(np.mean(predicted[scored] == realised[scored]))
    base = float(max(np.mean(realised[scored] > 0), np.mean(realised[scored] < 0)))
    return hits, float(np.mean(scored)), base


# ---- the central experiment -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NestedFit:
    """``dP = a + b1 e_n + b2 (OFI - e_n) + eps``, and the two things it gets wrong.

    ``OFI - e_n`` is a **reparametrisation, not an orthogonalisation**: ``e_n`` and the
    events before it are positively correlated under clustering.  By Frisch-Waugh the
    *test* of ``b2 = 0`` is still the right test of whether the window adds anything, but
    ``b1`` is not "the ``e_n`` effect" and the specification is not scale-invariant at the
    level of the coefficients.

    And ``b2 = 0`` is a one-degree-of-freedom *linear* restriction, which forces the
    window's contribution onto an equally weighted boxcar.  The theory says the true
    weighting is exponential and type-dependent, so ``b2`` near zero is entirely consistent
    with the window carrying information the boxcar cannot express.  That is why
    :func:`lag_bucket_fit` exists and why the joint ``F`` over buckets, not this, is the
    honest test against the alternative the model actually predicts.
    """

    last: float
    window: float
    last_error: float
    window_error: float
    covariance: float
    fit: object


def nested_fit(last: np.ndarray, imbalance: np.ndarray, change: np.ndarray, lag: int) -> NestedFit:
    from unito26.lob.estimation import hac_variance, ols

    design = np.column_stack([np.ones(last.size), last, imbalance - last])
    fitted = ols(design, change)
    robust = hac_variance(fitted, lag)
    return NestedFit(
        last=float(fitted.coefficients[1]),
        window=float(fitted.coefficients[2]),
        last_error=float(np.sqrt(robust[1, 1])),
        window_error=float(np.sqrt(robust[2, 2])),
        covariance=float(robust[1, 2]),
        fit=fitted,
    )


def lag_buckets(series: AlignedSeries, window: Window, buckets: int) -> np.ndarray:
    """``OFI`` split into ``buckets`` contiguous lag ranges covering ``(t - w, t]``.

    The multi-degree-of-freedom form of the nested test.  Its ``F`` is more powerful
    against an exponentially weighted alternative than the single boxcar coefficient is,
    and the *shape* of the fitted bucket coefficients measures the boxcar-versus-
    exponential mismatch directly rather than inferring it.
    """
    window = _span("window", window)
    if buckets < 1:
        raise ValueError(f"buckets must be at least 1, got {buckets}")
    edges = np.linspace(0.0, window, buckets + 1)
    cumulative = np.column_stack([backward_sum(series, Window(edge)) for edge in edges[1:]])
    return np.column_stack([cumulative[:, 0], np.diff(cumulative, axis=1)])


def joint_f(design: np.ndarray, change: np.ndarray, tested: slice, lag: int) -> tuple[float, int]:
    """Wald ``F`` that the coefficients in ``tested`` are jointly zero, on a HAC covariance."""
    from unito26.lob.estimation import hac_variance, ols

    fitted = ols(design, change)
    robust = hac_variance(fitted, lag)
    coefficients = fitted.coefficients[tested]
    block = robust[tested, tested]
    degrees = coefficients.size
    statistic = float(coefficients @ np.linalg.solve(block, coefficients)) / degrees
    return statistic, degrees


# ---- tuning the window ---------------------------------------------------------------------


def tune_window(
    criterion,
    candidates: np.ndarray,
    flow: AlignedSeries,
    mid: AlignedSeries,
    horizon: Horizon,
) -> tuple[np.ndarray, float]:
    """Score every candidate window on the row set of the **largest** candidate.

    A criterion whose evaluation set moves with its argument is not well posed: the longest
    window loses the most opening rows, so a criterion scored on each candidate's own rows
    compares different samples.  Scoring on the common set costs a prefix and nothing else
    at the example parametrization, where the row sets differ only in the opening ``w``.

    Returns the whole curve and its argmax, never the argmax alone.  The surface is
    quadratically flat near its optimum, so a point estimate is noisy and a regression on
    argmaxes is weak on top of being censored where the optimum leaves the admissible band.
    The evidence for the scaling law is the *collapse* of the curves, not their peaks.

    The contemporaneous criterion is refused: its ``R^2`` decreases monotonically in ``w``,
    so its argmax is the smallest point of any grid, whatever the kernel.
    """
    candidates = np.sort(np.asarray(candidates, dtype=float))
    widest = backward_sum(flow, Window(float(candidates[-1])))
    outcome = forward_change(mid, horizon)
    common = np.isfinite(widest) & np.isfinite(outcome)
    scores = np.array(
        [criterion(backward_sum(flow, Window(float(w)))[common], outcome[common])
         for w in candidates]
    )
    return scores, float(candidates[int(np.nanargmax(scores))])
