"""Example parametrizations, frozen as records.

These are *examples*, not defaults.  A default invites a reader to skip the choice, and
the choice is the subject; an example invites them to open it and see what a specification
looks like.  Nothing here is computed at import time: each constant is a list of records
in the sense of :class:`unito26.lob.frames.FrameSerializable`, and the loaders below are
the only way in.

**Where the flow numbers came from.**  The excitation matrix was written by hand for its
*shape*, encoding three things calibrations on exchange data agree about:

* market orders excite the limit-order flow heavily, as liquidity providers replenish
  what was just consumed;
* limit orders barely excite the market-order flow -- the relation is close to one-way;
* market buys excite sell-side withdrawals, liquidity pulled ahead of an informed buyer,
  which is the mechanism behind the adverse-selection term of section 7.

Every diagonal carries self-excitation, which is the order-splitting story: a large parent
order arrives as a burst of children.  The matrix was then rescaled to a branching ratio of
0.6.  That rescaling is separable from the shape because the spectral radius is homogeneous
of degree one in the excitation, so doubling every entry doubles it.

**Where the baselines came from.**  Not chosen directly.  What is chosen is the stationary
intensity ``lambda* = (I - Gamma)^{-1} mu``, since that is what sets the composition of the
flow and hence the book; the baselines are then read off as ``mu = (I - Gamma) lambda*``,
which is admissible exactly when it is non-negative componentwise.  The target holds a total
rate of 30.19 events per second, a limit-to-consuming ratio
``lambda_L / (lambda_M + lambda_W) = 1``, and the market-to-withdrawal split of the shape.
The binding component is the market-order baseline, market orders being heavily excited and
small in share; here it is 0.773 of a total baseline of 12.81.

The ratio of one is not a rounding.  Below it the book is consumed faster than it is
replenished and a side empties from time to time; above it the resting depth grows through
a session, and the contemporaneous coefficient ``1 / (2 Sbar)`` stops being a coefficient.
Exactly one is where the touch depth is stationary -- 924 shares on average across twenty
seeds, with a cross-seed spread of 143 -- and it is reached from an empty book in about
3,900 seconds, which is what sets the warm-up a study needs.

``EXAMPLE_MARK_PARAMS`` then sets how far the resting size spreads, and it is the parameter
that decides how the book fails.  At 0.15 the mean offset is between five and six ticks:
39% of arriving limit orders rest within three ticks of the touch, a side empties on 26
rows in a million, and the largest single-event mid move over twenty hour-long sessions is
15.5 ticks.  Sharpening it concentrates the book -- 58% within three ticks at 0.25 -- but
puts the size on the touch queue and nothing behind it, so a side that does clear jumps a
long way: the same twenty seeds then produce a 159-tick move.

tests/lob/test_serialization.py asserts those properties of what loads, so they remain
checked although the code that produced them is gone.
"""

from __future__ import annotations

from unito26.lob.hawkes import HawkesParams
from unito26.lob.simulate import MarkParams

__all__ = [
    "EXAMPLE_ORDER_FLOW_PARAMS",
    "EXAMPLE_MARK_PARAMS",
    "SHALLOW_MARK_PARAMS",
    "DEEP_MARK_PARAMS",
    "example_order_flow_params",
    "example_mark_params",
    "shallow_mark_params",
    "deep_mark_params",
]

#: A six-type flow with the asymmetry described above, at a branching ratio of 0.6.
#: ``Component`` is the type being excited, ``Cause`` the type exciting it.
EXAMPLE_ORDER_FLOW_PARAMS: list[dict] = [
    {"Component": 0, "Cause": 0, "BaseIntensity": 0.7728491131,
     "Kernel": 18.1397185244, "Decay": 60.0},
    {"Component": 0, "Cause": 1, "BaseIntensity": None,
     "Kernel": 4.0310485610, "Decay": 60.0},
    {"Component": 0, "Cause": 2, "BaseIntensity": None,
     "Kernel": 1.0077621403, "Decay": 60.0},
    {"Component": 0, "Cause": 3, "BaseIntensity": None,
     "Kernel": 1.0077621403, "Decay": 60.0},
    {"Component": 0, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 0, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 1, "Cause": 0, "BaseIntensity": None,
     "Kernel": 4.0310485610, "Decay": 60.0},
    {"Component": 1, "Cause": 1, "BaseIntensity": 0.7728491131,
     "Kernel": 18.1397185244, "Decay": 60.0},
    {"Component": 1, "Cause": 2, "BaseIntensity": None,
     "Kernel": 1.0077621403, "Decay": 60.0},
    {"Component": 1, "Cause": 3, "BaseIntensity": None,
     "Kernel": 1.0077621403, "Decay": 60.0},
    {"Component": 1, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 1, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 2, "Cause": 0, "BaseIntensity": None,
     "Kernel": 20.1552428049, "Decay": 60.0},
    {"Component": 2, "Cause": 1, "BaseIntensity": None,
     "Kernel": 14.1086699634, "Decay": 60.0},
    {"Component": 2, "Cause": 2, "BaseIntensity": 3.3972704543,
     "Kernel": 18.1397185244, "Decay": 60.0},
    {"Component": 2, "Cause": 3, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 2, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 2, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 3, "Cause": 0, "BaseIntensity": None,
     "Kernel": 14.1086699634, "Decay": 60.0},
    {"Component": 3, "Cause": 1, "BaseIntensity": None,
     "Kernel": 20.1552428049, "Decay": 60.0},
    {"Component": 3, "Cause": 2, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 3, "Cause": 3, "BaseIntensity": 3.3972704543,
     "Kernel": 18.1397185244, "Decay": 60.0},
    {"Component": 3, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 3, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 4, "Cause": 0, "BaseIntensity": None,
     "Kernel": 6.0465728414, "Decay": 60.0},
    {"Component": 4, "Cause": 1, "BaseIntensity": None,
     "Kernel": 16.1241942439, "Decay": 60.0},
    {"Component": 4, "Cause": 2, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 4, "Cause": 3, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 4, "Cause": 4, "BaseIntensity": 2.2330251699,
     "Kernel": 18.1397185244, "Decay": 60.0},
    {"Component": 4, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 5, "Cause": 0, "BaseIntensity": None,
     "Kernel": 16.1241942439, "Decay": 60.0},
    {"Component": 5, "Cause": 1, "BaseIntensity": None,
     "Kernel": 6.0465728414, "Decay": 60.0},
    {"Component": 5, "Cause": 2, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 5, "Cause": 3, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 5, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.0155242805, "Decay": 60.0},
    {"Component": 5, "Cause": 5, "BaseIntensity": 2.2330251699,
     "Kernel": 18.1397185244, "Decay": 60.0},
]

#: Sizes lognormal about exp(4) and rounded to a round lot, quotes within a few ticks.
EXAMPLE_MARK_PARAMS: list[dict] = [
    {"DepthDecay": 0.15, "MeanLogSize": 4.0,
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
