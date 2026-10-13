"""The forward means of a Hawkes process, estimated across independent paths.

:class:`unito26.lob.hawkes.HawkesParams` states two conditional expectations in closed form:
the mean state and the expected counts a horizon ``h`` after a time ``s``, given the state
``Z(s+) = z``.  This module estimates them, so that each formula can be set against a
quantity that does not use it.

Three objects do it.  A :class:`Fan` is the sampling: independent paths continued from one
state, with the clock moved to zero.  A :class:`ForwardStatistic` is the reading: what one
path contributes on a clock of horizons, together with the expectation that the mean of the
readings estimates.  A :class:`SampleMean` is that mean and its standard error.

The paths of a fan are independent of one another, and that is all the standard error
uses.  The readings of one path at two horizons are not independent, and neither are two
statistics read on one fan: the scores along a clock rise and fall together.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Self

import numpy as np

from unito26.lob.hawkes import Clock, ExponentialHawkes, HawkesParams, decayed_counts_at
from unito26.lob.messages import Horizon

__all__ = [
    "SampleMean",
    "Fan",
    "ForwardStatistic",
    "ForwardState",
    "ForwardCounts",
    "Contracted",
]


@dataclass(frozen=True, slots=True)
class SampleMean:
    """The mean of independent draws, and its standard error."""

    mean: np.ndarray
    standard_error: np.ndarray

    @classmethod
    def from_sample(cls, sample: np.ndarray) -> Self:
        """From draws stacked along the first axis, one per row."""
        sample = np.asarray(sample, dtype=float)
        return cls(
            mean=sample.mean(axis=0),
            standard_error=sample.std(axis=0, ddof=1) / np.sqrt(sample.shape[0]),
        )

    def z_scores(self, formula: np.ndarray) -> np.ndarray:
        """``(mean - formula) / standard error``.

        Where every draw is the same the standard error is zero and there is no score: the
        entry is ``nan`` if the mean is the formula and infinite otherwise.  The counts at a
        horizon of zero are the case, so a clock of horizons starts after zero.
        """
        with np.errstate(divide="ignore", invalid="ignore"):
            return (self.mean - np.asarray(formula, dtype=float)) / self.standard_error


@dataclass(frozen=True, slots=True)
class Fan:
    """Independent paths continued from one state, ``Z(0+) = z``, with the clock moved to
    zero.

    The rates of the state depend neither on the time nor on the counts, so the paths after
    any time ``s`` at which ``Z(s+) = z`` have the law of these, with ``s`` subtracted.
    """

    params: HawkesParams
    state: np.ndarray
    horizon: Horizon
    paths: tuple[tuple[np.ndarray, np.ndarray], ...]
    """The event times and types of each path on ``(0, horizon]``."""

    @classmethod
    def sample(
        cls,
        params: HawkesParams,
        state: np.ndarray,
        horizon: Horizon,
        size: int,
        rng: np.random.Generator | int | None = None,
    ) -> Self:
        """``size`` paths on ``(0, horizon]``, drawn one after another from ``rng``.

        Two fans are independent when they are drawn from different seeds, or from one
        generator in turn.  The same seed twice gives two fans that share their draws.
        """
        rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
        state = np.array(state, dtype=float)
        paths = []
        for _ in range(size):
            events = list(ExponentialHawkes.from_state(params, state, rng).events(horizon))
            paths.append(
                (
                    np.array([time for time, _ in events], dtype=float),
                    np.array([event_type for _, event_type in events], dtype=int),
                )
            )
        return cls(params=params, state=state, horizon=horizon, paths=tuple(paths))

    @property
    def size(self) -> int:
        return len(self.paths)

    def covers(self, clock: Clock) -> Clock:
        """``clock``, refused if it leaves ``[0, horizon]``: past the horizon a path has no
        events because none were drawn, not because none occurred."""
        clock = np.asarray(clock, dtype=float)
        if clock.size and (clock.min() < 0.0 or clock.max() > self.horizon):
            raise ValueError(
                f"the clock runs over [{clock.min()}, {clock.max()}] and the fan over "
                f"[0, {self.horizon}]"
            )
        return Clock(clock)


class ForwardStatistic(ABC):
    """A statistic of the path after ``s``, read on a clock of horizons, and the conditional
    expectation given ``Z(s+) = z`` that its mean across a fan estimates.

    A subclass states the two; the estimate and its scores against the formula follow.
    """

    @abstractmethod
    def read(self, fan: Fan, clock: Clock) -> np.ndarray:
        """The statistic on every path of ``fan``: an array whose first axis is the paths
        and whose second is the clock."""

    @abstractmethod
    def expectation(self, fan: Fan, clock: Clock) -> np.ndarray:
        """The formula for the mean of :meth:`read`, a row per horizon."""

    def sample_mean(self, fan: Fan, clock: Clock) -> SampleMean:
        return SampleMean.from_sample(self.read(fan, clock))

    def z_scores(self, fan: Fan, clock: Clock) -> np.ndarray:
        """The scores of the estimate against the formula, a row per horizon."""
        return self.sample_mean(fan, clock).z_scores(self.expectation(fan, clock))


class ForwardState(ForwardStatistic):
    """``Z(s+h)``, whose mean is ``e^{K h} z + Phi(h) mu``.  Read before the jump of an
    event that falls on the clock, ``Z`` being left-continuous."""

    def read(self, fan: Fan, clock: Clock) -> np.ndarray:
        clock = fan.covers(clock)
        return np.stack(
            [
                decayed_counts_at(fan.params.decay, times, types, fan.state, clock)
                for times, types in fan.paths
            ]
        )

    def expectation(self, fan: Fan, clock: Clock) -> np.ndarray:
        return fan.params.forward_mean_state_terms(fan.state, clock).total


class ForwardCounts(ForwardStatistic):
    """``N(s+h) - N(s)``, whose mean is ``h mu + A Phi(h) z + A (int_0^h Phi) mu``.  An
    event that falls on the clock is counted, ``N`` being right-continuous."""

    def read(self, fan: Fan, clock: Clock) -> np.ndarray:
        clock = fan.covers(clock)
        counts = np.empty((fan.size, clock.size, fan.params.dimension))
        for path, (times, types) in enumerate(fan.paths):
            for event_type in range(fan.params.dimension):
                counts[path, :, event_type] = np.searchsorted(
                    times[types == event_type], clock, side="right"
                )
        return counts

    def expectation(self, fan: Fan, clock: Clock) -> np.ndarray:
        return fan.params.forward_mean_counts_terms(fan.state, clock).total


@dataclass(frozen=True, slots=True)
class Contracted(ForwardStatistic):
    """A statistic contracted with a vector, path by path: the counts with the pressure are
    the signed count.  The standard error is then that of the contraction, which the
    standard errors of the components do not give."""

    statistic: ForwardStatistic
    vector: np.ndarray

    def read(self, fan: Fan, clock: Clock) -> np.ndarray:
        return self.statistic.read(fan, clock) @ np.asarray(self.vector, dtype=float)

    def expectation(self, fan: Fan, clock: Clock) -> np.ndarray:
        return self.statistic.expectation(fan, clock) @ np.asarray(self.vector, dtype=float)
