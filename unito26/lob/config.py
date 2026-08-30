"""Example parametrizations, frozen.

These are *examples*, not defaults.  A default invites a reader to skip the choice, and
the choice is the whole subject; an example invites them to open it and see what a
specification looks like.  Nothing here is computed at import time -- each constant is a
serialized frame, and the loaders below are the only way in.

**Where the flow numbers came from.**  The excitation matrix was written by hand for its
*shape*, encoding three things calibrations on exchange data agree about:

* market orders excite the limit-order flow heavily, as liquidity providers replenish
  what was just consumed;
* limit orders barely excite the market-order flow -- the relation is strikingly one-way;
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

from unito26.lob import frames
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
EXAMPLE_ORDER_FLOW_PARAMS = (
    '{"Component":{"0":0,"1":0,"2":0,"3":0,"4":0,"5":0,"6":1,"7":1,"8":1,"9":1,"10":1,"11":1,"12":2,"13":2,"14":2,"15":2,"16":2,"17":2,"18":3,"19":3,"20":3,"21":3,"22":3,"23":3,"24":4,"25":4,"26":4,"27":4,"28":4,"29":4,"30":5,"31":5,"32":5,"33":5,"34":5,"35":5},"Cause":{"0":0,"1":1,"2":2,"3":3,"4":4,"5":5,"6":0,"7":1,"8":2,"9":3,"10":4,"11":5,"12":0,"13":1,"14":2,"15":3,"16":4,"17":5,"18":0,"19":1,"20":2,"21":3,"22":4,"23":5,"24":0,"25":1,"26":2,"27":3,"28":4,"29":5,"30":0,"31":1,"32":2,"33":3,"34":4,"35":5},"BaseIntensity":{"0":0.3,"1":null,"2":null,"3":null,"4":null,"5":null,"6":null,"7":0.3,"8":null,"9":null,"10":null,"11":null,"12":null,"13":null,"14":2.0,"15":null,"16":null,"17":null,"18":null,"19":null,"20":null,"21":2.0,"22":null,"23":null,"24":null,"25":null,"26":null,"27":null,"28":1.2,"29":null,"30":null,"31":null,"32":null,"33":null,"34":null,"35":1.2},"Kernel":{"0":24.1862913658,"1":5.3747314146,"2":1.3436828537,"3":1.3436828537,"4":2.6873657073,"5":2.6873657073,"6":5.3747314146,"7":24.1862913658,"8":1.3436828537,"9":1.3436828537,"10":2.6873657073,"11":2.6873657073,"12":26.8736570732,"13":18.8115599512,"14":24.1862913658,"15":2.6873657073,"16":2.6873657073,"17":2.6873657073,"18":18.8115599512,"19":26.8736570732,"20":2.6873657073,"21":24.1862913658,"22":2.6873657073,"23":2.6873657073,"24":8.0620971219,"25":21.4989256585,"26":2.6873657073,"27":2.6873657073,"28":24.1862913658,"29":2.6873657073,"30":21.4989256585,"31":8.0620971219,"32":2.6873657073,"33":2.6873657073,"34":2.6873657073,"35":24.1862913658},"Decay":{"0":60.0,"1":60.0,"2":60.0,"3":60.0,"4":60.0,"5":60.0,"6":60.0,"7":60.0,"8":60.0,"9":60.0,"10":60.0,"11":60.0,"12":60.0,"13":60.0,"14":60.0,"15":60.0,"16":60.0,"17":60.0,"18":60.0,"19":60.0,"20":60.0,"21":60.0,"22":60.0,"23":60.0,"24":60.0,"25":60.0,"26":60.0,"27":60.0,"28":60.0,"29":60.0,"30":60.0,"31":60.0,"32":60.0,"33":60.0,"34":60.0,"35":60.0}}'
)

#: Sizes lognormal about exp(4) and rounded to a round lot, quotes clustered at the touch.
EXAMPLE_MARK_PARAMS = (
    '{"DepthDecay":{"0":0.45},"MeanLogSize":{"0":4.0},"SigmaLogSize":{"0":0.8},"Lot":{"0":10}}'
)

#: Orders cluster tightly at the touch, so few levels are ever occupied.
SHALLOW_MARK_PARAMS = (
    '{"DepthDecay":{"0":0.45},"MeanLogSize":{"0":4.0},"SigmaLogSize":{"0":0.8},"Lot":{"0":10}}'
)

#: Orders spread far from the touch, so the occupied levels pile up.
DEEP_MARK_PARAMS = (
    '{"DepthDecay":{"0":0.02},"MeanLogSize":{"0":4.0},"SigmaLogSize":{"0":0.8},"Lot":{"0":10}}'
)


def example_order_flow_params() -> HawkesParams:
    return frames.hawkes_params_from_frame(frames.from_json(EXAMPLE_ORDER_FLOW_PARAMS))


def example_mark_params() -> MarkParams:
    return frames.mark_params_from_frame(frames.from_json(EXAMPLE_MARK_PARAMS))


def shallow_mark_params() -> MarkParams:
    return frames.mark_params_from_frame(frames.from_json(SHALLOW_MARK_PARAMS))


def deep_mark_params() -> MarkParams:
    return frames.mark_params_from_frame(frames.from_json(DEEP_MARK_PARAMS))
