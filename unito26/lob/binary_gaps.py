"""An integer as a set of bit positions, and the gaps between them.

The vocabulary the bitmap-backed books are written in.  ``documentation/integers-in-binary.md``
derives the identities; this module is the working set.

A *gap* is a run of zeros lying strictly between ones, so trailing zeros are never a gap:
``0b100`` has none.  The functions that cut a window out of an integer return it shifted
down to an odd value, which is what :func:`measure_largest_binary_gap` requires.
"""

__all__ = [
    "count_trailing_zeros",
    "discard_trailing_zeros",
    "keep_highest_set_bits",
    "keep_lowest_set_bits",
    "measure_largest_binary_gap",
    "count_binary_gaps",
]


def count_trailing_zeros(n: int) -> int:
    """Zeros to the right of the lowest set bit of ``n > 0``.

    ``n & -n`` isolates that bit, so its ``bit_length`` is one more than the count.
    Undefined at zero, which has no lowest set bit.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    return (n & -n).bit_length() - 1


def discard_trailing_zeros(n: int) -> int:
    """``n`` shifted right until it is odd.  Zero maps to zero."""
    return n >> count_trailing_zeros(n) if n else 0


def keep_highest_set_bits(n: int, count: int) -> int:
    """The ``count`` highest set bits of ``n`` -- all of them, if it has no more -- shifted
    down so the lowest of them is bit 0.  Requires ``count >= 1``.

    ``(n >> k).bit_count()`` is the number of set bits at or above position ``k``, and it
    falls as ``k`` rises.  The cut is the largest ``k`` at which it still reaches ``count``,
    so bisection finds it without visiting the bits one at a time.
    """
    if n.bit_count() <= count:
        return discard_trailing_zeros(n)
    low, high = 0, n.bit_length() - 1  # (n >> low).bit_count() >= count throughout
    while low < high:
        mid = (low + high + 1) // 2
        if (n >> mid).bit_count() >= count:
            low = mid
        else:
            high = mid - 1
    return n >> low


def keep_lowest_set_bits(n: int, count: int) -> int:
    """The ``count`` lowest set bits of ``n`` -- all of them, if it has no more -- shifted
    down so the lowest of them is bit 0.

    ``m & (m - 1)`` clears the lowest set bit of ``m``, so ``count`` passes clear exactly
    the bits to keep, and ``n ^ rest`` recovers them.
    """
    rest = n
    for _ in range(count):
        rest &= rest - 1
    return discard_trailing_zeros(n ^ rest)


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

    Each run of ones has exactly one lowest bit, a set bit whose lower neighbour is clear,
    and ``n & ~(n << 1)`` keeps those and nothing else.  Every run but the highest has a
    gap above it, so the gaps are one fewer than the runs.
    """
    if not n:
        return 0
    return (n & ~(n << 1)).bit_count() - 1
