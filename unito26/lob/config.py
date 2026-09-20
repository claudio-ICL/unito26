"""Example parametrizations, frozen as records.

These are *examples*, not defaults.  A default invites a reader to skip the choice, and
the choice is the subject; an example invites them to open it and see what a specification
looks like.  Nothing here is computed at import time: each constant is a list of records
in the sense of :class:`unito26.lob.frames.FrameSerializable`, and the loaders below are
the only way in.

**The mechanism the kernel encodes.**  A queue survives because what depletes it calls
forth what refills it.  So whenever an event depletes one side -- a market sell eating the
bid, or a withdrawal pulling it -- the kernel excites *limit orders on that side* far more
than it excites further withdrawals from it: the ratio is 19 to 1, on both sides and after
both kinds of depleting event.  That is a local, conditional restoring force, and it is
what keeps a side from emptying.  It is not the same thing as balancing the average rates,
which is a global condition and a slow one.

The rest of the shape follows from that.  Market orders self-excite, which is the
order-splitting story: a large parent order arrives as a burst of children.  Limit orders
barely excite market orders, so the relation is close to one-way.  Withdrawals excite
little of anything, since a cancellation that begot cancellations is the behaviour the
mechanism above exists to suppress.  The matrix is then rescaled to a branching ratio of
0.6, which is separable from the shape because the spectral radius is homogeneous of
degree one in the excitation.

Read off the branching matrix, the shape says: one market order begets 1.42 direct events,
a withdrawal 1.04, a limit order 0.20.

**Where the baselines came from.**  Not chosen directly.  What is chosen is the stationary
intensity ``lambda* = (I - Gamma)^{-1} mu``, since that is what sets the composition of the
flow and hence the book; the baselines are then read off as ``mu = (I - Gamma) lambda*``,
which is admissible exactly when it is non-negative componentwise.  The target holds a
total rate of 30.19 events per second and a limit-to-consuming ratio of 0.965.

The binding component is now the *limit-order* baseline, and that is a consequence of the
mechanism rather than an accident: tying the limit-order rate to the depleting rates makes
limit orders overwhelmingly endogenous, so little of their rate is left for immigration.
Here ``mu`` is 0.140 against a stationary 7.41, a margin of 6.3% of the smallest component.
Below a ratio of about 0.945 it goes negative and the target is unreachable at this
branching ratio.  That is the constraint that sets how far the composition can be pushed,
and it is why 0.6 and the replenishment strength cannot both be raised freely.

**Why the ratio is 0.965 and not one.**  A ratio of one balances the flow in *counts*, and
that is not the same as balancing it in *size*.  A withdrawal takes ``min(drawn size, size
resting at the chosen level)`` and a market order cannot consume more than exists, so every
truncated removal is capacity thrown away.  At a ratio of one the book gains a little of the
limit-order inflow for ever; the depth is not stationary there but *marginally
non-stationary*, growing ever more slowly as the levels fatten and truncation vanishes, so
that a measurement stopping after two or three hours reads the transient as a plateau.  One
is the critical point.  The stationary ratio is below it, and 0.965 is where twenty seeds
show no detectable drift: the slope of the depth profile across the six tenths of a session
is +0.8% per tenth with ``t = 0.98``, ``p = 0.34``, and the last-tenth-to-first-tenth ratio
has a 95% interval of [0.97, 1.16].

``EXAMPLE_MARK_PARAMS`` then sets how far the resting size spreads, and it is the parameter
that decides how the book fails.  Concentration, non-emptiness and a moving mid are three
corners of one trade: with the spread pinned at a tick the mid moves only by clearing a
touch queue, which is also how a side empties, and only occupied depth *behind* the touch
separates the two.  Sharpening the offset puts the size on the touch queue and nothing
behind it, so a side that does clear jumps a long way.  At 0.08 the profile is flat enough
to leave depth behind the touch: over twenty hour-long sessions and 2.17 million rows no
side ever empties, and the largest single-event mid move is 6.5 ticks.

The touch holds 460 shares on average across twenty seeds, with a cross-seed spread of 32,
and reaches 95% of that from an empty book in about 900 seconds -- which is what sets the
warm-up a study needs.

tests/lob/test_serialization.py asserts those properties of what loads, so they remain
checked although the code that produced them is gone.
"""

from __future__ import annotations

from unito26.lob.hawkes import HawkesParams
from unito26.lob.simulate import MarkParams

__all__ = [
    "EXAMPLE_ORDER_FLOW_PARAMS",
    "TRENDING_ORDER_FLOW_PARAMS",
    "TRENDING_MARK_PARAMS",
    "EXAMPLE_MARK_PARAMS",
    "SHALLOW_MARK_PARAMS",
    "DEEP_MARK_PARAMS",
    "example_order_flow_params",
    "trending_order_flow_params",
    "trending_mark_params",
    "example_mark_params",
    "shallow_mark_params",
    "deep_mark_params",
]

#: A six-type flow with the asymmetry described above, at a branching ratio of 0.6.
#: ``Component`` is the type being excited, ``Cause`` the type exciting it.
EXAMPLE_ORDER_FLOW_PARAMS: list[dict] = [
    {"Component": 0, "Cause": 0, "BaseIntensity": 0.5126447854,
     "Kernel": 1.5541514008, "Decay": 4.0},
    {"Component": 0, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.3453669780, "Decay": 4.0},
    {"Component": 0, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.0518050467, "Decay": 4.0},
    {"Component": 0, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.0518050467, "Decay": 4.0},
    {"Component": 0, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 0, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 1, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.3453669780, "Decay": 4.0},
    {"Component": 1, "Cause": 1, "BaseIntensity": 0.5126447854,
     "Kernel": 1.5541514008, "Decay": 4.0},
    {"Component": 1, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.0518050467, "Decay": 4.0},
    {"Component": 1, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.0518050467, "Decay": 4.0},
    {"Component": 1, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 1, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 2, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 2, "Cause": 1, "BaseIntensity": None,
     "Kernel": 3.2809862906, "Decay": 4.0},
    {"Component": 2, "Cause": 2, "BaseIntensity": 0.1402833873,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 2, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 2, "Cause": 4, "BaseIntensity": None,
     "Kernel": 3.2809862906, "Decay": 4.0},
    {"Component": 2, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 3, "Cause": 0, "BaseIntensity": None,
     "Kernel": 3.2809862906, "Decay": 4.0},
    {"Component": 3, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 3, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 3, "Cause": 3, "BaseIntensity": 0.1402833873,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 3, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 3, "Cause": 5, "BaseIntensity": None,
     "Kernel": 3.2809862906, "Decay": 4.0},
    {"Component": 4, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 4, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 4, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 4, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 4, "Cause": 4, "BaseIntensity": 4.1410981517,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 4, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 5, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 5, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 5, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 5, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 5, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.1726834890, "Decay": 4.0},
    {"Component": 5, "Cause": 5, "BaseIntensity": 4.1410981517,
     "Kernel": 0.1726834890, "Decay": 4.0},
]

#: Sizes lognormal about exp(4) and rounded to a round lot, quotes within a few ticks.

#: The same flow, in the regime where excitation follows the *pressure* partition instead
#: of the queue: an event excites the types that push the price the same way it did.
#: Signed endogenous fraction +0.554 against the example's -0.351.
TRENDING_ORDER_FLOW_PARAMS: list[dict] = [
    {"Component": 0, "Cause": 0, "BaseIntensity": 0.4591361692,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 0, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 0, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.0045009037, "Decay": 4.0},
    {"Component": 0, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.0045009037, "Decay": 4.0},
    {"Component": 0, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 0, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 1, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 1, "Cause": 1, "BaseIntensity": 0.4591361692,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 1, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.0045009037, "Decay": 4.0},
    {"Component": 1, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.0045009037, "Decay": 4.0},
    {"Component": 1, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 1, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 2, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 2, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 2, "Cause": 2, "BaseIntensity": 4.0173011153,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 2, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 2, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 2, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 3, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 3, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 3, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 3, "Cause": 3, "BaseIntensity": 4.0173011153,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 3, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 3, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 4, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 4, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 4, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 4, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 4, "Cause": 4, "BaseIntensity": 1.9496606913,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 4, "Cause": 5, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 5, "Cause": 0, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 5, "Cause": 1, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 5, "Cause": 2, "BaseIntensity": None,
     "Kernel": 0.9001807356, "Decay": 4.0},
    {"Component": 5, "Cause": 3, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 5, "Cause": 4, "BaseIntensity": None,
     "Kernel": 0.0150030123, "Decay": 4.0},
    {"Component": 5, "Cause": 5, "BaseIntensity": 1.9496606913,
     "Kernel": 0.9001807356, "Decay": 4.0},
]

#: The trending regime is studied with a sharper offset than the example uses.  That is not
#: a free choice: a book flat enough to be resilient is resilient mechanically too, and
#: flattening this one drives its predictive sign back to the example's.
TRENDING_MARK_PARAMS: list[dict] = [
    {"DepthDecay": 0.15, "MeanLogSize": 4.0,
     "SigmaLogSize": 0.8, "Lot": 10},
]

EXAMPLE_MARK_PARAMS: list[dict] = [
    {"DepthDecay": 0.08, "MeanLogSize": 4.0,
     "SigmaLogSize": 0.8, "Lot": 10},
]

#: Orders cluster tightly at the touch, so few levels are ever occupied.
SHALLOW_MARK_PARAMS: list[dict] = [
    {"DepthDecay": 0.45, "MeanLogSize": 4.0,
     "SigmaLogSize": 0.8, "Lot": 10},
]

#: Orders spread far from the touch, so the occupied levels pile up.
DEEP_MARK_PARAMS: list[dict] = [
    {"DepthDecay": 0.02, "MeanLogSize": 4.0,
     "SigmaLogSize": 0.8, "Lot": 10},
]


def example_order_flow_params() -> HawkesParams:
    return HawkesParams.from_records(EXAMPLE_ORDER_FLOW_PARAMS)


def example_mark_params() -> MarkParams:
    return MarkParams.from_records(EXAMPLE_MARK_PARAMS)


def shallow_mark_params() -> MarkParams:
    return MarkParams.from_records(SHALLOW_MARK_PARAMS)


def deep_mark_params() -> MarkParams:
    return MarkParams.from_records(DEEP_MARK_PARAMS)


def trending_order_flow_params() -> HawkesParams:
    """The momentum regime: excitation follows the pressure partition."""
    return HawkesParams.from_records(TRENDING_ORDER_FLOW_PARAMS)


def trending_mark_params() -> MarkParams:
    """The marks the trending regime is studied with."""
    return MarkParams.from_records(TRENDING_MARK_PARAMS)
