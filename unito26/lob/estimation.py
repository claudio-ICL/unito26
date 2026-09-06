"""Estimators and their uncertainty, for series sampled at events.

Nothing here knows about a book.  What it knows is the shape of the data the imbalance
study produces: rows sampled at event times rather than on a clock, overlapping windows,
an outcome on a lattice with a large atom, and regressors with heavier tails than the
outcome.  Every routine below exists because a textbook default fails on one of those.

Three themes run through it.

*Overlap.*  Rows sampled at events and scored over a forecast horizon share raw data, so
an i.i.d. standard error understates.  :func:`hac_variance` and :func:`block_indices`
are the two answers, and they answer different questions -- see :func:`effective_sample`.

*The lattice.*  An outcome that is zero on nine rows in ten has an ``R^2`` dominated by a
handful of moves.  :func:`log_score_skill` replaces it with a proper scoring rule over
three classes, and :func:`participation_ratio` and :func:`hill_tail_index` are what
``R^2`` is reported beside so that its failure is visible rather than assumed.

*Nesting.*  Comparing a model with a strict submodel degenerates the usual tests, because
under the null the extra coefficients are zero and the forecast difference has zero mean
*and* zero variance.  :func:`clark_west` is the adjustment; the bootstrap alternative is
to impose the null when resampling.

``statsmodels`` is not a dependency of the course environment, so the linear algebra is
hand-rolled.  ``scipy.stats.kendalltau`` is, and is not reimplemented.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

__all__ = [
    "OLSFit",
    "ols",
    "hac_variance",
    "effective_sample",
    "politis_white_block_length",
    "block_indices",
    "bootstrap_means",
    "kendall_tau_b",
    "ThreeClassModel",
    "log_score_skill",
    "incremental_log_score_skill",
    "brier_skill",
    "reliability",
    "participation_ratio",
    "hill_tail_index",
    "clark_west",
    "purged_folds",
]

DOWN, FLAT, UP = 0, 1, 2
CLASSES = 3


# ---- least squares and its uncertainty ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class OLSFit:
    """A fitted linear model and what is needed to put an interval on it.

    ``design`` carries its own intercept column, if it is to have one: a fit that inserts
    one silently cannot express a regression through the origin, and the mechanical
    regression of section 6 is one.
    """

    coefficients: np.ndarray
    residuals: np.ndarray
    design: np.ndarray
    gram_inverse: np.ndarray
    """``(X'X)^{-1}``, kept because every variance estimate below is a sandwich around it."""

    @property
    def sample_size(self) -> int:
        return self.residuals.size

    @property
    def r_squared(self) -> float:
        """Fraction of the outcome's variance about *its own mean* that the fit explains.

        Reported throughout the imbalance study as a diagnostic that fails, never as the
        headline: on a lattice outcome with a large atom it measures the fit of the few
        rows that move, weighted by the square of how far they moved.
        """
        fitted = self.design @ self.coefficients
        outcome = fitted + self.residuals
        centred = outcome - outcome.mean()
        total = float(centred @ centred)
        return float("nan") if total == 0 else 1.0 - float(self.residuals @ self.residuals) / total

    def variance(self) -> np.ndarray:
        """The i.i.d. covariance ``s^2 (X'X)^{-1}``.  Understates under overlap."""
        residual_variance = float(self.residuals @ self.residuals) / (
            self.sample_size - self.coefficients.size
        )
        return residual_variance * self.gram_inverse


def ols(design: np.ndarray, outcome: np.ndarray) -> OLSFit:
    """Least squares by the pseudo-inverse, which is stable where the normal equations are not."""
    design = np.asarray(design, dtype=float)
    outcome = np.asarray(outcome, dtype=float)
    if design.ndim != 2 or design.shape[0] != outcome.size:
        raise ValueError(f"design {design.shape} does not match {outcome.size} outcomes")
    coefficients, *_ = np.linalg.lstsq(design, outcome, rcond=None)
    return OLSFit(
        coefficients=coefficients,
        residuals=outcome - design @ coefficients,
        design=design,
        gram_inverse=np.linalg.pinv(design.T @ design),
    )


def hac_variance(fit: OLSFit, lag: int) -> np.ndarray:
    """Newey-West covariance of the coefficients, truncated at ``lag``.

    The lag is set from the *forecast horizon* and not from the regressor's window.  Under
    a correctly specified conditional mean the score ``x_t e_t`` inherits its serial
    correlation from the overlap of the outcomes; a long lookback makes the regressor
    persistent without by itself making the score autocorrelated.  Use of the order of four
    times the mean event count within the horizon -- the *mean*, the count distribution
    being right-skewed -- plus what the depth process contributes, and report at ``lag``,
    ``2 lag`` and ``lag / 2``.

    The plug-in ``4 (n/100)^{2/9}`` is blind to all of that: 12 rows at ``n = 14,000`` and
    21 at ``n = 180,000``, whatever the horizon.
    """
    if lag < 0:
        raise ValueError(f"lag must be non-negative, got {lag}")
    scores = fit.design * fit.residuals[:, None]
    middle = scores.T @ scores
    for shift in range(1, lag + 1):
        weight = 1.0 - shift / (lag + 1.0)
        cross = scores[shift:].T @ scores[:-shift]
        middle = middle + weight * (cross + cross.T)
    return fit.gram_inverse @ middle @ fit.gram_inverse


def effective_sample(fit: OLSFit, lag: int, coefficient: int) -> float:
    """``n * V_ols / V_hac`` **for one named coefficient**.

    Not a property of a row set: it differs across the columns of a single fit, because
    different regressors carry different amounts of the overlap.  Descriptive only -- the
    intervals in the imbalance study come from the bootstrap, and this never supplies
    degrees of freedom for them.
    """
    iid = fit.variance()[coefficient, coefficient]
    robust = hac_variance(fit, lag)[coefficient, coefficient]
    return float("nan") if robust <= 0 else fit.sample_size * iid / robust


# ---- the block bootstrap -----------------------------------------------------------------


def politis_white_block_length(series: np.ndarray) -> float:
    """Automatic block length for the stationary bootstrap, after Politis and White (2004).

    Returned in units of *rows*.  The imbalance study converts it to a duration before
    using it, because rows are event-sampled: a fixed row count maps to a wildly variable
    stretch of time, and it is the time that carries the dependence.
    """
    series = np.asarray(series, dtype=float)
    series = series[np.isfinite(series)]
    n = series.size
    if n < 8:
        return 1.0
    centred = series - series.mean()
    variance = float(centred @ centred) / n
    if variance <= 0:
        return 1.0
    horizon = max(5, int(np.ceil(np.sqrt(np.log10(n)))))
    limit = min(n - 1, int(np.ceil(2 * np.sqrt(np.log10(n) * n / np.log10(n)))), 5 * int(np.sqrt(n)))
    correlations = np.array(
        [float(centred[k:] @ centred[:-k]) / (n * variance) for k in range(1, limit + 1)]
    )
    threshold = 2.0 * np.sqrt(np.log10(n) / n)
    cutoff = limit
    for k in range(correlations.size - horizon + 1):
        if np.all(np.abs(correlations[k : k + horizon]) < threshold):
            cutoff = k + 1
            break
    lags = np.arange(1, 2 * cutoff + 1)
    lags = lags[lags <= correlations.size]
    weights = _flat_top(lags / cutoff)
    g = float(np.sum(weights * lags * correlations[lags - 1] * 2))
    d = 2 * (1 + 2 * float(np.sum(weights * correlations[lags - 1]))) ** 2
    if d <= 0:
        return 1.0
    return float(min(n ** (1 / 3), max(1.0, (2 * g**2 / d) ** (1 / 3) * n ** (1 / 3))))


def _flat_top(ratio: np.ndarray) -> np.ndarray:
    """The trapezoidal lag window: one below 1/2, tapering to zero at 1."""
    return np.clip(2 * (1 - np.abs(ratio)), 0.0, 1.0)


def block_indices(
    times: np.ndarray, block_duration: float, rng: np.random.Generator
) -> np.ndarray:
    """Row indices of one stationary-bootstrap resample, in contiguous blocks of *time*.

    Blocks of rows are the wrong unit here.  Rows arrive in clusters, so a fixed row count
    spans a duration that varies by an order of magnitude, and it is the duration that has
    to exceed the dependence length.  Each block starts at a uniformly drawn row and takes
    every row within ``block_duration`` of it; blocks are drawn until the resample is at
    least as long as the original, then truncated.

    One call per replicate, and the *same* indices are used for every predictor and every
    metric in that replicate, so that differences bootstrap as paired quantities.
    """
    times = np.asarray(times, dtype=float)
    n = times.size
    if block_duration <= 0:
        raise ValueError(f"block_duration must be positive, got {block_duration}")
    ends = np.searchsorted(times, times + block_duration, side="right")
    picked = []
    total = 0
    while total < n:
        start = int(rng.integers(n))
        picked.append(np.arange(start, ends[start]))
        total += ends[start] - start
    return np.concatenate(picked)[:n]


def bootstrap_means(
    times: np.ndarray, scores: np.ndarray, block_duration: float, replicates: int, rng
) -> np.ndarray:
    """Resampled means of every column of ``scores``, sharing one index set per replicate.

    The fast path for the metrics that *are* means of a per-row score -- the signed
    covariance, an accuracy, a Brier score.  Statistics that are not means need
    :func:`block_indices` and a recomputation per replicate, which is the expensive path
    and is used only where it is needed.
    """
    rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
    scores = np.atleast_2d(np.asarray(scores, dtype=float).T).T
    out = np.empty((replicates, scores.shape[1]))
    for replicate in range(replicates):
        rows = block_indices(times, block_duration, rng)
        out[replicate] = scores[rows].mean(axis=0)
    return out


# ---- rank and lattice diagnostics --------------------------------------------------------


def kendall_tau_b(x: np.ndarray, y: np.ndarray) -> float:
    """Kendall's tau-b, tie-corrected.  The **statistic only**.

    ``scipy`` also returns a p-value whose null is i.i.d. sampling; on overlapping
    event-sampled rows that null is anticonservative by orders of magnitude, so it is not
    returned and not to be read off ``scipy`` directly.
    """
    return float(stats.kendalltau(x, y, variant="b").statistic)


@dataclass(frozen=True, slots=True)
class ThreeClassModel:
    """``P(down, flat, up)`` per quantile bin of a predictor, shrunk toward climatology.

    Three properties of the log-score skill this implements, each of which the naive
    version gets wrong:

    *It is not bounded below.*  One held-out row in a bin whose training frequency for its
    class is zero sends the score to minus infinity, and empty ``up``/``down`` cells are
    guaranteed at the extreme quantiles of a signed flow.  Hence the shrinkage, with
    ``prior_weight`` stated rather than tuned, toward a climatology that is itself floored
    away from zero -- a class absent from the whole training fold would otherwise take the
    *baseline* to minus infinity as well, and the skill with it.

    The baseline is the same estimator with a single bin, which is what "climatology"
    means here and is what makes a constant predictor score exactly zero: its one bin *is*
    that estimator.

    *It is not zero under the null in finite sample.*  A ``k``-bin three-class model
    carries an expected out-of-sample excess of about ``k (J-1) / (2 n_train)`` nats, which
    at ``k = 10`` and ``n_train = 10,000`` is a skill of about ``-1.2e-3`` against a
    climatological entropy of 0.82 nats -- the size of the effects being measured.

    *It is comparable across predictors only at a fixed ``k``*, a predictor supporting
    finer bins winning on resolution alone; and across configurations only in sign and
    rank, the climatological entropy moving with the atom.
    """

    edges: np.ndarray
    probabilities: np.ndarray
    climatology: np.ndarray

    @classmethod
    def fit(
        cls, predictor: np.ndarray, outcome: np.ndarray, bins: int, prior_weight: float
    ) -> "ThreeClassModel":
        predictor = np.asarray(predictor, dtype=float)
        outcome = np.asarray(outcome, dtype=int)
        overall = np.bincount(outcome, minlength=CLASSES).astype(float)
        target = (overall + prior_weight / CLASSES) / (outcome.size + prior_weight)
        edges = np.unique(np.quantile(predictor, np.linspace(0, 1, bins + 1)[1:-1]))
        assigned = np.searchsorted(edges, predictor, side="right")
        counts = np.zeros((edges.size + 1, CLASSES))
        np.add.at(counts, (assigned, outcome), 1.0)
        totals = counts.sum(axis=1, keepdims=True)
        probabilities = (counts + prior_weight * target) / (totals + prior_weight)
        climatology = (overall + prior_weight * target) / (outcome.size + prior_weight)
        return cls(edges=edges, probabilities=probabilities, climatology=climatology)

    def predict(self, predictor: np.ndarray) -> np.ndarray:
        return self.probabilities[np.searchsorted(self.edges, predictor, side="right")]

    def cross_entropy(self, predictor: np.ndarray, outcome: np.ndarray) -> float:
        """Mean negative log-likelihood in nats.  Lower is better."""
        outcome = np.asarray(outcome, dtype=int)
        chosen = self.predict(np.asarray(predictor, dtype=float))[
            np.arange(outcome.size), outcome
        ]
        return float(-np.mean(np.log(chosen)))

    def climatological_entropy(self, outcome: np.ndarray) -> float:
        outcome = np.asarray(outcome, dtype=int)
        return float(-np.mean(np.log(self.climatology[outcome])))


def log_score_skill(
    train_predictor: np.ndarray,
    train_outcome: np.ndarray,
    test_predictor: np.ndarray,
    test_outcome: np.ndarray,
    bins: int,
    prior_weight: float,
) -> float:
    """``1 - L_model / L_climatology``, both scored out of fold.

    Model *and* climatology come from the same training fold and are both scored on the
    held-out one.  An in-fold climatology biases the skill down, a climatology borrowed
    from another regime biases it up, and the book's depth drifts between folds.  Fitted
    this way a constant predictor scores exactly zero, which is the test that pins the
    convention.
    """
    model = ThreeClassModel.fit(train_predictor, train_outcome, bins, prior_weight)
    baseline = model.climatological_entropy(test_outcome)
    if baseline <= 0:
        return float("nan")
    return 1.0 - model.cross_entropy(test_predictor, test_outcome) / baseline


def incremental_log_score_skill(
    train_base: np.ndarray,
    train_extra: np.ndarray,
    train_outcome: np.ndarray,
    test_base: np.ndarray,
    test_extra: np.ndarray,
    test_outcome: np.ndarray,
    bins: int,
    prior_weight: float,
) -> float:
    """Skill of a two-predictor binned model over the one-predictor model it **nests**.

    The lattice-aware form of the nested test, and the confirmatory statistic of the
    imbalance study.  ``train_base`` is binned on its own; the joint model bins the pair
    into product cells and shrinks each cell toward *the base model's* probability for the
    base bin it sits in -- not toward climatology.  That is what makes the statistic
    exactly zero when the extra predictor adds nothing, so it needs no separate null.

    Preferred to the ``b2 = 0`` coefficient test for two reasons.  The outcome is an atom
    of over nine tenths with a heavy-tailed remainder, which a linear magnitude slope reads
    badly; and a binned joint model does not force the extra predictor's contribution to be
    linear, where ``b2`` forces it onto an equally weighted boxcar.

    The product grid costs resolution: ``bins`` squared cells on one training fold.  Use
    fewer bins here than for a single predictor, and compare only at a fixed ``bins``.
    """
    base = ThreeClassModel.fit(train_base, train_outcome, bins, prior_weight)
    train_outcome = np.asarray(train_outcome, dtype=int)

    base_cell = np.searchsorted(base.edges, np.asarray(train_base, dtype=float), side="right")
    extra_edges = np.unique(
        np.quantile(np.asarray(train_extra, dtype=float), np.linspace(0, 1, bins + 1)[1:-1])
    )
    extra_cell = np.searchsorted(extra_edges, np.asarray(train_extra, dtype=float), side="right")
    width = extra_edges.size + 1
    cell = base_cell * width + extra_cell

    counts = np.zeros((base.probabilities.shape[0] * width, CLASSES))
    np.add.at(counts, (cell, train_outcome), 1.0)
    totals = counts.sum(axis=1, keepdims=True)
    target = np.repeat(base.probabilities, width, axis=0)
    joint = (counts + prior_weight * target) / (totals + prior_weight)

    test_outcome = np.asarray(test_outcome, dtype=int)
    test_cell = (
        np.searchsorted(base.edges, np.asarray(test_base, dtype=float), side="right") * width
        + np.searchsorted(extra_edges, np.asarray(test_extra, dtype=float), side="right")
    )
    rows = np.arange(test_outcome.size)
    richer = float(-np.mean(np.log(joint[test_cell][rows, test_outcome])))
    simpler = base.cross_entropy(test_base, test_outcome)
    return float("nan") if simpler <= 0 else 1.0 - richer / simpler


def brier_skill(probabilities: np.ndarray, outcome: np.ndarray, climatology: np.ndarray) -> float:
    """Multi-class Brier skill of a probabilistic forecast against a constant one."""
    outcome = np.asarray(outcome, dtype=int)
    indicator = np.zeros((outcome.size, CLASSES))
    indicator[np.arange(outcome.size), outcome] = 1.0
    model = float(np.mean(np.sum((np.asarray(probabilities) - indicator) ** 2, axis=1)))
    reference = float(np.mean(np.sum((np.asarray(climatology) - indicator) ** 2, axis=1)))
    return float("nan") if reference <= 0 else 1.0 - model / reference


def reliability(
    probabilities: np.ndarray, outcome: np.ndarray, klass: int, bins: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Forecast probability against realised frequency, for one class.

    Returns ``(mean forecast, realised frequency, count)`` per bin of the forecast.  A
    calibrated model lies on the diagonal; the departure from it is what a skill score
    aggregates away.
    """
    forecast = np.asarray(probabilities)[:, klass]
    realised = (np.asarray(outcome, dtype=int) == klass).astype(float)
    edges = np.unique(np.quantile(forecast, np.linspace(0, 1, bins + 1)))
    assigned = np.clip(np.searchsorted(edges[1:-1], forecast, side="right"), 0, edges.size - 2)
    groups = np.arange(max(assigned.max() + 1, 1))
    means = np.array([forecast[assigned == g].mean() if (assigned == g).any() else np.nan
                      for g in groups])
    rates = np.array([realised[assigned == g].mean() if (assigned == g).any() else np.nan
                      for g in groups])
    counts = np.array([int((assigned == g).sum()) for g in groups])
    return means, rates, counts


def participation_ratio(values: np.ndarray) -> float:
    """``(sum x^2)^2 / sum x^4``: how many observations an ``R^2`` is really built on.

    A sum of squares spread evenly over ``n`` rows gives ``n``; one dominated by a single
    row gives 1.  Reported beside every ``R^2`` in the study, on the **regressors** as well
    as on the outcome, since ``OFI`` minus its last term is at least as heavy-tailed as the
    outcome -- a cancellation at the touch contributes a whole queue.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    squares = float(np.sum(values**2))
    quads = float(np.sum(values**4))
    return float("nan") if quads <= 0 else squares**2 / quads


def hill_tail_index(values: np.ndarray, upper: int) -> float:
    """Hill estimate of the tail index from the ``upper`` largest absolute values.

    Below 2 the variance does not exist, and neither does the population quantity an
    ``R^2`` estimates.  That is the point of reporting it beside one.
    """
    magnitudes = np.sort(np.abs(np.asarray(values, dtype=float)))
    magnitudes = magnitudes[np.isfinite(magnitudes) & (magnitudes > 0)]
    if magnitudes.size <= upper or upper < 2:
        return float("nan")
    tail = magnitudes[-upper:]
    return float(1.0 / np.mean(np.log(tail / magnitudes[-upper - 1])))


def clark_west(
    outcome: np.ndarray, restricted: np.ndarray, unrestricted: np.ndarray
) -> np.ndarray:
    """The Clark-West adjusted loss difference, per row; its mean is the statistic.

    Comparing nested forecasts degenerates the usual test: under the null the extra
    coefficients are zero, so the forecast difference has zero mean *and* zero variance,
    and the difference in squared errors is biased against the larger model by the noise
    in estimating coefficients that do not belong.  The adjustment adds back exactly that.

    Returned per row so that the mean can be bootstrapped with the same block indices as
    every other statistic in the record.
    """
    outcome = np.asarray(outcome, dtype=float)
    restricted = np.asarray(restricted, dtype=float)
    unrestricted = np.asarray(unrestricted, dtype=float)
    return (
        (outcome - restricted) ** 2
        - (outcome - unrestricted) ** 2
        + (restricted - unrestricted) ** 2
    )


def purged_folds(
    times: np.ndarray, folds: int, purge: float
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Blocked rolling-origin folds, with a purge and embargo of ``purge`` seconds.

    A row at ``t`` reads data over ``(t - w, t + h]``, so two rows share raw data whenever
    they are within ``w + h`` of each other: the purge is that **sum**, and it is set by
    the largest candidate window rather than by the one being scored.

    This handles the overlap and not the dependence that actually matters, which is the
    state: the book's depth mean-reverts over seconds and every predictor reads it.  For
    tuning a window the study evaluates on a disjoint block of *seeds* instead, an
    unlimited supply of independent paths being what a simulation has and a market does
    not.
    """
    times = np.asarray(times, dtype=float)
    if folds < 2:
        raise ValueError(f"folds must be at least 2, got {folds}")
    bounds = np.quantile(times, np.linspace(0, 1, folds + 1))
    out = []
    for fold in range(folds):
        low, high = bounds[fold], bounds[fold + 1]
        test = np.flatnonzero((times >= low) & (times < high) if fold < folds - 1
                              else (times >= low))
        train = np.flatnonzero((times < low - purge) | (times > high + purge))
        out.append((train, test))
    return out
