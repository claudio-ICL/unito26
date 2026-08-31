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
0.8, inside the 0.7-0.9 range calibrations report.  That rescaling is separable from the
shape because the spectral radius is homogeneous of degree one in the excitation, so
doubling every entry doubles it.

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

#: A six-type flow with the asymmetry described above, at a branching ratio of 0.8.
#: ``Component`` is the type being excited, ``Cause`` the type exciting it.
EXAMPLE_ORDER_FLOW_PARAMS: list[dict] = [
    {"Component": 0, "Cause": 0, "BaseIntensity": 0.3,
     "Kernel": 24.1862913658, "Decay": 60.0},
    {"Component": 0, "Cause": 1, "BaseIntensity": None,
     "Kernel": 5.3747314146, "Decay": 60.0},
    {"Component": 0, "Cause": 2, "BaseIntensity": None,
     "Kernel": 1.3436828537, "Decay": 60.0},
    {"Component": 0, "Cause": 3, "BaseIntensity": None,
     "Kernel": 1.3436828537, "Decay": 60.0},
    {"Component": 0, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 0, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 1, "Cause": 0, "BaseIntensity": None,
     "Kernel": 5.3747314146, "Decay": 60.0},
    {"Component": 1, "Cause": 1, "BaseIntensity": 0.3,
     "Kernel": 24.1862913658, "Decay": 60.0},
    {"Component": 1, "Cause": 2, "BaseIntensity": None,
     "Kernel": 1.3436828537, "Decay": 60.0},
    {"Component": 1, "Cause": 3, "BaseIntensity": None,
     "Kernel": 1.3436828537, "Decay": 60.0},
    {"Component": 1, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 1, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 2, "Cause": 0, "BaseIntensity": None,
     "Kernel": 26.8736570732, "Decay": 60.0},
    {"Component": 2, "Cause": 1, "BaseIntensity": None,
     "Kernel": 18.8115599512, "Decay": 60.0},
    {"Component": 2, "Cause": 2, "BaseIntensity": 2.0,
     "Kernel": 24.1862913658, "Decay": 60.0},
    {"Component": 2, "Cause": 3, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 2, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 2, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 3, "Cause": 0, "BaseIntensity": None,
     "Kernel": 18.8115599512, "Decay": 60.0},
    {"Component": 3, "Cause": 1, "BaseIntensity": None,
     "Kernel": 26.8736570732, "Decay": 60.0},
    {"Component": 3, "Cause": 2, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 3, "Cause": 3, "BaseIntensity": 2.0,
     "Kernel": 24.1862913658, "Decay": 60.0},
    {"Component": 3, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 3, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 4, "Cause": 0, "BaseIntensity": None,
     "Kernel": 8.0620971219, "Decay": 60.0},
    {"Component": 4, "Cause": 1, "BaseIntensity": None,
     "Kernel": 21.4989256585, "Decay": 60.0},
    {"Component": 4, "Cause": 2, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 4, "Cause": 3, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 4, "Cause": 4, "BaseIntensity": 1.2,
     "Kernel": 24.1862913658, "Decay": 60.0},
    {"Component": 4, "Cause": 5, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 5, "Cause": 0, "BaseIntensity": None,
     "Kernel": 21.4989256585, "Decay": 60.0},
    {"Component": 5, "Cause": 1, "BaseIntensity": None,
     "Kernel": 8.0620971219, "Decay": 60.0},
    {"Component": 5, "Cause": 2, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 5, "Cause": 3, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 5, "Cause": 4, "BaseIntensity": None,
     "Kernel": 2.6873657073, "Decay": 60.0},
    {"Component": 5, "Cause": 5, "BaseIntensity": 1.2,
     "Kernel": 24.1862913658, "Decay": 60.0},
]

#: Sizes lognormal about exp(4) and rounded to a round lot, quotes clustered at the touch.
EXAMPLE_MARK_PARAMS: list[dict] = [
    {"DepthDecay": 0.45, "MeanLogSize": 4.0,
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
