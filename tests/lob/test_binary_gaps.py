"""The bit vocabulary, against a brute-force reference over the binary strings."""

import pytest

from unito26.lob.binary_gaps import (
    count_binary_gaps,
    count_trailing_zeros,
    discard_trailing_ones,
    discard_trailing_zeros,
    measure_largest_binary_gap,
)

CASES = range(1, 5000)


def runs(n: int) -> list[int]:
    """Lengths of the zero runs lying strictly between ones."""
    return [len(run) for run in bin(n)[2:].strip("0").split("1") if run]


@pytest.mark.parametrize("n", CASES)
def test_gap_count_matches_the_string_reference(n):
    assert count_binary_gaps(n) == len(runs(n))


@pytest.mark.parametrize("n", CASES)
def test_largest_gap_matches_the_string_reference(n):
    # Normalised input: trailing zeros are not a gap, and this function counts them.
    assert measure_largest_binary_gap(discard_trailing_zeros(n)) == max(runs(n), default=0)


def test_trailing_zeros_are_not_a_gap():
    assert runs(0b100) == []
    assert measure_largest_binary_gap(0b100) == 2, "why the input must be normalised first"
    assert measure_largest_binary_gap(discard_trailing_zeros(0b100)) == 0


def test_zero_has_no_lowest_set_bit():
    with pytest.raises(ValueError):
        count_trailing_zeros(0)
    assert count_binary_gaps(0) == 0
    assert discard_trailing_zeros(0) == 0


@pytest.mark.parametrize("power", range(12))
def test_a_power_of_two_has_no_gap(power):
    assert count_binary_gaps(1 << power) == 0
    assert measure_largest_binary_gap(discard_trailing_zeros(1 << power)) == 0


@pytest.mark.parametrize("width", range(1, 12))
def test_a_block_of_ones_has_no_gap(width):
    solid = (1 << width) - 1
    assert count_binary_gaps(solid) == 0
    assert discard_trailing_ones(solid) == 0


@pytest.mark.parametrize("n", CASES)
def test_both_statistics_survive_reversing_the_bit_string(n):
    """The bid side reads downward from the top bit and the ask side upward, and they
    share an implementation.  That is only sound because these two are reversal-invariant.
    """
    forward = discard_trailing_zeros(n)
    reversed_bits = int(bin(forward)[2:][::-1], 2)
    assert count_binary_gaps(reversed_bits) == count_binary_gaps(forward)
    assert measure_largest_binary_gap(reversed_bits) == measure_largest_binary_gap(forward)
