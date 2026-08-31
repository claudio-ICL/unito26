"""Multivariate Hawkes processes with a common exponential kernel.

Order flow is not Poisson: it clusters, and the clustering is the phenomenon.  This
module generates the *timing and type* of order-book events; turning an event type
into an order ``(t, q, p, d)`` is the job of :mod:`unito26.lob.simulate`.

The model.  For ``d`` event types the conditional intensity of type ``i`` is

.. math::

    \\lambda_i(t) = \\mu_i + \\sum_j \\alpha_{ij}
                    \\sum_{t^j_k < t} e^{-\\beta (t - t^j_k)},

with ``alpha[i, j] >= 0`` read as "type *j* excites type *i*".  The decay ``beta`` is
common to every pair.  That is a modelling choice bought for tractability, and it is
what everything below rests on.

Why the exponential kernel.  Writing

.. math::

    S_j(t) = \\sum_{t^j_k < t} e^{-\\beta(t - t^j_k)},
    \\qquad \\lambda(t) = \\mu + A \\, S(t),

the vector ``S`` decays deterministically between events and jumps by one in
coordinate ``j`` when a type-``j`` event occurs.  So ``(N, S)`` is a
piecewise-deterministic Markov process and the whole history is carried in ``d`` floats.
Recomputing the intensity by summing over all past events would be O(n^2) over a run;
the recursion is O(1) per event.  This is the aggregate order book's idea -- carry the
sufficient summary rather than the history -- in a different setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd
import pandera.pandas as pa

from unito26.lob.frames import FrameSerializable

__all__ = ["HawkesParams", "ExponentialHawkes", "OgataThinningHawkes", "compensators_at_events"]


@dataclass(frozen=True, slots=True)
class HawkesParams(FrameSerializable):
    """Parameters of a ``d``-type Hawkes process with a common exponential decay.

    Attributes
    ----------
    baseline
        ``mu``, shape ``(d,)``.  The immigration intensity of each type.
    excitation
        ``A``, shape ``(d, d)``.  ``excitation[i, j]`` is the jump in type ``i``'s
        intensity caused by an event of type ``j``.  Note the index order: *row is
        excited, column is exciting*.
    decay
        ``beta > 0``, shared by every pair.
    """

    baseline: np.ndarray
    excitation: np.ndarray
    decay: float

    def __post_init__(self) -> None:
        # A frozen dataclass cannot assign to its own fields, so coercion to arrays
        # goes through object.__setattr__.  This is the standard escape hatch and the
        # price of getting immutability and hashable-by-construction parameters.
        object.__setattr__(self, "baseline", np.asarray(self.baseline, dtype=float))
        object.__setattr__(self, "excitation", np.asarray(self.excitation, dtype=float))
        object.__setattr__(self, "decay", float(self.decay))

        if self.baseline.ndim != 1:
            raise ValueError(f"baseline must be a vector, got shape {self.baseline.shape}")
        d = self.baseline.size
        if self.excitation.shape != (d, d):
            raise ValueError(
                f"excitation must be ({d}, {d}) to match baseline, got {self.excitation.shape}"
            )
        if self.decay <= 0:
            raise ValueError(f"decay must be positive, got {self.decay}")
        if np.any(self.baseline < 0):
            raise ValueError("baseline intensities must be non-negative")
        if np.any(self.excitation < 0):
            raise ValueError(
                "excitation must be non-negative: the exact scheme relies on the total "
                "intensity decaying monotonically between events"
            )
        if self.baseline.sum() <= 0:
            raise ValueError(
                "the total baseline intensity must be positive, otherwise the process "
                "can die out and never restart"
            )
        if self.branching_ratio >= 1:
            raise ValueError(
                f"branching ratio is {self.branching_ratio:.4f}, must be < 1 for a "
                "stationary process; as it approaches 1 the process explodes"
            )

    @property
    def dimension(self) -> int:
        """Number of event types, ``d``."""
        return self.baseline.size

    @property
    def branching_matrix(self) -> np.ndarray:
        """``Gamma = A / beta``.  ``Gamma[i, j]`` is the expected number of type-``i``
        events directly triggered by one type-``j`` event."""
        return self.excitation / self.decay

    @property
    def branching_ratio(self) -> float:
        """Spectral radius of the branching matrix.  Stationarity needs it below 1.

        Calibrations on high-frequency order flow report values around 0.7-0.9: most
        order flow is triggered by other order flow.
        """
        return float(np.max(np.abs(np.linalg.eigvals(self.branching_matrix))))

    def stationary_intensity(self) -> np.ndarray:
        """Long-run mean intensity ``(I - Gamma)^{-1} mu``, per type."""
        identity = np.eye(self.dimension)
        return np.linalg.solve(identity - self.branching_matrix, self.baseline)

    # ---- serialization ---------------------------------------------------------------

    @classmethod
    def schema(cls) -> pa.DataFrameSchema:
        """Long form: one row per ``(Component, Cause)`` pair.

        ``BaseIntensity`` is nullable because the baseline is a vector carried on the
        diagonal; pandera drops nulls before running a check, so the non-negativity
        constraint applies to the diagonal alone.
        """
        return pa.DataFrameSchema(
            {
                "Component": pa.Column("Int64", pa.Check.ge(0), coerce=True),
                "Cause": pa.Column("Int64", pa.Check.ge(0), coerce=True),
                "BaseIntensity": pa.Column(float, pa.Check.ge(0.0), nullable=True, coerce=True),
                "Kernel": pa.Column(float, pa.Check.ge(0.0), coerce=True),
                "Decay": pa.Column(float, pa.Check.gt(0.0), coerce=True),
            },
            strict=True,
        )

    def to_frame(self) -> pd.DataFrame:
        """``Component`` is the type being excited and ``Cause`` the type exciting it,
        matching ``excitation[i, j]``.  The baseline sits on the diagonal and is null off
        it; the decay is a scalar and repeats."""
        dimension = self.dimension
        index = pd.MultiIndex.from_product(
            [range(dimension), range(dimension)], names=("Component", "Cause")
        )
        baseline = np.full((dimension, dimension), np.nan)
        np.fill_diagonal(baseline, self.baseline)
        frame = pd.DataFrame(
            {
                "BaseIntensity": baseline.flatten(),
                "Kernel": self.excitation.flatten(),
                "Decay": float(self.decay),
            },
            index=index,
        ).reset_index()
        return self.schema().validate(frame)

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> "HawkesParams":
        """Rebuild by pivoting on ``(Component, Cause)``.

        Reshaping in row order would transpose a frame whose rows arrived in a different
        order, and no schema can constrain row order.
        """
        frame = cls.schema().validate(frame)
        decays = frame["Decay"].unique()
        if len(decays) != 1:
            raise ValueError(f"the decay is shared by every pair; frame carries {list(decays)}")

        kernel = frame.pivot(index="Component", columns="Cause", values="Kernel")
        dimension = len(kernel)
        if kernel.shape != (dimension, dimension) or kernel.isna().to_numpy().any():
            raise ValueError(
                f"the (Component, Cause) grid must be complete and square, got {kernel.shape}"
            )

        diagonal = frame[frame["Component"] == frame["Cause"]].sort_values("Component")
        if len(diagonal) != dimension:
            raise ValueError(
                f"expected {dimension} diagonal rows carrying the baseline, got {len(diagonal)}"
            )
        return cls(
            baseline=diagonal["BaseIntensity"].to_numpy(dtype=float),
            excitation=kernel.to_numpy(dtype=float),
            decay=float(decays[0]),
        )


class _HawkesState:
    """The Markov state ``(t, S)`` shared by both simulation schemes.

    Subclasses differ only in :meth:`step`: the state and the bookkeeping are the
    model, the step is the algorithm.
    """

    def __init__(self, params: HawkesParams, rng: np.random.Generator | int | None = None):
        self.params = params
        self.rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        self.time = 0.0
        self.decayed_counts = np.zeros(params.dimension)  # S
        # Column sums of A: the jump in the *total* intensity caused by each type.
        self._total_jump = params.excitation.sum(axis=0)
        self._baseline_total = float(params.baseline.sum())

    @property
    def intensities(self) -> np.ndarray:
        """``lambda(t) = mu + A S(t)`` at the current time."""
        return self.params.baseline + self.params.excitation @ self.decayed_counts

    @property
    def total_intensity(self) -> float:
        """``Lambda(t) = sum_i lambda_i(t)``, computed via the column sums."""
        return self._baseline_total + float(self._total_jump @ self.decayed_counts)

    def _advance(self, elapsed: float) -> None:
        """Decay the state forward by ``elapsed``, without an event."""
        self.time += elapsed
        self.decayed_counts *= np.exp(-self.params.decay * elapsed)

    def _draw_type_and_jump(self) -> int:
        """Choose which type fired, with probability ``lambda_i / Lambda``, and jump."""
        intensities = self.intensities
        cumulative = np.cumsum(intensities)
        threshold = self.rng.random() * cumulative[-1]
        # side="left" gives the inverse-CDF index; the clamp guards the rounding case
        # where the uniform draw lands just past the last cumulative entry.
        event_type = min(int(np.searchsorted(cumulative, threshold)), self.params.dimension - 1)
        self.decayed_counts[event_type] += 1.0
        return event_type

    def step(self) -> tuple[float, int]:
        raise NotImplementedError

    def events(self, horizon: float) -> Iterator[tuple[float, int]]:
        """Yield ``(time, event_type)`` until ``horizon``.

        A generator rather than a list: the stream is consumed by a fold, and nothing
        downstream needs it materialised.
        """
        while True:
            time, event_type = self.step()
            if time > horizon:
                return
            yield time, event_type


class ExponentialHawkes(_HawkesState):
    """Exact simulation, by the Dassios-Zhao decomposition applied to the total intensity.

    Because every ``alpha_ij >= 0`` and the decay is common, the *total* intensity
    ``Lambda(t) = sum_i lambda_i(t)`` is itself a one-dimensional exponentially
    decaying process: it relaxes at rate ``beta`` towards ``mu_bar = sum_i mu_i`` and
    jumps by the column sum ``c_j = sum_i alpha_ij`` on a type-``j`` event.  So the
    scalar exact scheme applies to ``Lambda`` directly, and the type is drawn
    afterwards with probability ``lambda_i / Lambda``.

    Given ``Lambda_n``, the intensity just after the last event, the compensator over
    the next ``s`` splits into two increasing pieces::

        Lambda_bar(s) = mu_bar * s   +   (Lambda_n - mu_bar) (1 - e^{-beta s}) / beta
                        \\ baseline /     \\--------- excited part ---------/

    A point process with compensator ``L1 + L2`` is the superposition of two
    independent ones, so the next inter-arrival is the minimum of two closed-form draws.
    The excited part carries the finite total mass ``(Lambda_n - mu_bar) / beta``, and
    ``S2 = inf`` is the event that it expires without firing.

    O(1) per event, exact, with no rejection step, no discretisation bias and no time
    grid.
    """

    def step(self) -> tuple[float, int]:
        beta = self.params.decay
        excess = self.total_intensity - self._baseline_total  # (Lambda_n - mu_bar) >= 0

        u1, u2 = self.rng.random(2)

        # Baseline part: a homogeneous Poisson arrival at rate mu_bar.  Always finite.
        wait_baseline = -np.log(u1) / self._baseline_total

        # Excited part: invert its compensator in closed form.  The inversion has no
        # solution precisely when the remaining excitation mass runs out first.
        if excess <= 0.0:
            wait_excited = np.inf
        else:
            remaining = 1.0 + beta * np.log(u2) / excess
            wait_excited = -np.log(remaining) / beta if remaining > 0.0 else np.inf

        self._advance(min(wait_baseline, wait_excited))
        return self.time, self._draw_type_and_jump()


class OgataThinningHawkes(_HawkesState):
    """Simulation by Ogata's thinning, kept as the cross-check on the exact scheme.

    The upper bound is free: with ``alpha >= 0`` the intensity is non-increasing
    between events, so the total intensity right after the last event bounds it until
    the next one.  Propose at the bound, accept with probability
    ``Lambda(t') / Lambda_bar``, and tighten the bound on every rejection.

    Slower than :class:`ExponentialHawkes`, and it does not need the kernel to be
    common-``beta``, which is what makes it a control on the exact scheme rather than a
    restatement of it.
    """

    def step(self) -> tuple[float, int]:
        bound = self.total_intensity
        while True:
            self._advance(-np.log(self.rng.random()) / bound)
            accepted = self.total_intensity
            if self.rng.random() * bound <= accepted:
                return self.time, self._draw_type_and_jump()
            # Rejected: the intensity has decayed further, so the bound tightens.
            bound = accepted


def compensators_at_events(
    params: HawkesParams, times: np.ndarray, types: np.ndarray
) -> np.ndarray:
    """Compensator of every component, evaluated at every event time.

    Integrating the intensity gives, for component ``i``,

    .. math::

        \\Lambda_i(T) = \\mu_i T
            + \\sum_j \\frac{\\alpha_{ij}}{\\beta} \\big(N_j(T) - S_j(T)\\big),

    because ``int_0^T S_j = (N_j(T) - S_j(T)) / beta``.  The same two summary
    statistics that drive the simulation also close the compensator in one line.

    Returns an ``(n, d)`` array whose row ``k`` is ``Lambda(times[k])``, using the
    state just before the event at ``times[k]``.  This is an independent implementation
    of the mathematics: the residual test uses it to certify the simulator, so it must
    not share code with it.
    """
    times = np.asarray(times, dtype=float)
    types = np.asarray(types, dtype=int)
    d = params.dimension
    beta = params.decay

    decayed = np.zeros(d)  # S, decayed to just before the current event
    counts = np.zeros(d)  # N, events strictly before the current one
    previous_time = 0.0
    out = np.empty((times.size, d))

    for k, (time, event_type) in enumerate(zip(times, types)):
        decayed *= np.exp(-beta * (time - previous_time))
        out[k] = params.baseline * time + params.excitation @ ((counts - decayed) / beta)
        decayed[event_type] += 1.0
        counts[event_type] += 1.0
        previous_time = time

    return out
