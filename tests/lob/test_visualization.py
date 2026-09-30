"""Smoke tests for the point-process figures: each builds, and draws what it says."""

import numpy as np
import pytest

from unito26.lob import config
from unito26.lob.hawkes import Clock, ExponentialHawkes, decayed_counts_at
from unito26.lob.visualization import (
    exponential_qq_figure,
    intensity_figure,
    monte_carlo_figure,
    raster_figure,
)

LABELS = ["type 1", "type 2"]


@pytest.fixture
def path():
    events = list(ExponentialHawkes(config.asymmetric_pair_params(), rng=0).events(20.0))
    times = np.array([t for t, _ in events])
    types = np.array([k for _, k in events])
    return times, types


def test_the_intensity_figure_draws_a_line_and_a_strip_per_type(path):
    params = config.asymmetric_pair_params()
    times, types = path
    clock = Clock(np.linspace(0.0, 20.0, 400))
    states = decayed_counts_at(params.decay, times, types, np.zeros(2), clock)
    intensities = params.baseline + states @ params.excitation.T
    figure = intensity_figure(clock, intensities, times, types, LABELS)
    assert len(figure.data) == 4
    assert sum(trace.x.size for trace in figure.data[1::2]) == times.size


def test_the_raster_has_a_row_per_path_and_every_event(path):
    figure = raster_figure({"first": path, "second": path}, LABELS)
    assert len(figure.data) == 4
    assert sum(trace.x.size for trace in figure.data) == 2 * path[0].size


def test_the_monte_carlo_band_straddles_the_mean():
    rng = np.random.default_rng(0)
    x = np.linspace(0.0, 1.0, 11)
    samples = rng.normal(size=(500, 11, 2)) + x[None, :, None]
    figure = monte_carlo_figure(x, samples, np.stack([x, x], axis=1), LABELS)
    band, mean, formula = figure.data[:3]
    error = samples[:, :, 0].std(axis=0, ddof=1) / np.sqrt(500)
    assert len(figure.data) == 6
    assert band.y[:11] - mean.y == pytest.approx(2 * error)
    assert mean.y - band.y[11:][::-1] == pytest.approx(2 * error)
    assert np.array_equal(formula.y, x)


def test_the_qq_bands_contain_an_exponential_sample():
    rng = np.random.default_rng(1)
    figure = exponential_qq_figure({"a": rng.exponential(size=5000)}, levels=200)
    simultaneous, pointwise, diagonal, points = figure.data
    bounded = simultaneous.x.size // 2
    upper = simultaneous.y[:bounded]
    lower = simultaneous.y[bounded:][::-1]
    inside = points.y[:bounded]
    assert 0 < bounded < points.y.size
    assert np.all((lower <= inside) & (inside <= upper))
    assert np.all(pointwise.y[:bounded] <= upper + 1e-12)
