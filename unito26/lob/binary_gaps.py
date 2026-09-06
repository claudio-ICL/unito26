"""An integer as a set of bit positions, and the gaps between them.

The vocabulary the bitmap-backed books are written in.  ``documentation/integers-in-binary.md``
derives the identities; this module is the working set.

A *gap* is a run of zeros lying strictly between ones, so trailing zeros are never a gap:
``0b100`` has none.  Several functions below therefore require an odd argument, and say so.
"""

__all__ = [
    "count_trailing_zeros",
    "discard_trailing_zeros",
    "discard_trailing_ones",
    "measure_largest_binary_gap",
    "count_binary_gaps",
]


def count_trailing_zeros(n: int) -> int:
    """Zeros to the right of the lowest set bit of ``n > 0``.

    Undefined at zero, which has no lowest set bit: the loop below would never end.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    count = 0
    while (n & 1) == 0:
        count += 1
        n >>= 1
    return count


def discard_trailing_zeros(n: int) -> int:
    """``n`` shifted right until it is odd.  Zero maps to zero."""
    while n > 0 and (n & 1) == 0:
        n >>= 1
    return n


def discard_trailing_ones(n: int) -> int:
    """``n`` shifted right until its lowest bit is zero."""
    while (n & 1) == 1:
        n >>= 1
    return n


def measure_largest_binary_gap(n: int) -> int:
    """Length of the longest run of zeros between ones.  Requires ``n`` odd.

    ``n |= n >> 1`` floods each gap one bit per pass, and ``n & (n + 1)`` is zero exactly
    when ``n`` has become a solid block of ones, so the number of passes is the width of
    the widest gap.  On an even ``n`` the trailing zeros flood too and are counted as a
    gap they are not: normalise with :func:`discard_trailing_zeros` first.
    """
    count = 0
    while (n & (n + 1)) != 0:
        count += 1
        n |= n >> 1
    return count


def count_binary_gaps(n: int) -> int:
    """Number of runs of zeros between ones.

    Each pass strips one trailing run of ones and the run of zeros above it, so it
    consumes exactly one gap.
    """
    n = discard_trailing_ones(discard_trailing_zeros(n))
    count = 0
    while n > 0:
        count += 1
        n = discard_trailing_ones(discard_trailing_zeros(n))
    return count
