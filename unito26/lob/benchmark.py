"""Timing and memory for the book variants, kept out of the tests on purpose.

The tests assert that the variants agree; how *fast* and how *large* they are is a
different question with a different failure mode, and one that belongs in a notebook
where the numbers can be read rather than in a suite that must pass.  Putting these
helpers in the package rather than in ``tests/`` is what lets the notebook import them.

Two regimes, because the ladder's answer is conditional on which one the market is in:
a shallow book, where flow concentrates within a few ticks of the touch, and a deep one.
The whole lesson of the ladder is that an optimisation targets a bottleneck, and whether
that bottleneck exists is a property of the market rather than of the code.
"""

from __future__ import annotations

import sys
import timeit
import tracemalloc
from dataclasses import dataclass

from unito26.lob.messages import Message, is_market_price
from unito26.lob.orderbook import AggregateBook
from unito26.lob.replay import run
from unito26.lob.simulate import MarkParams, OrderFlowSimulator

__all__ = [
    "Session",
    "session",
    "SHALLOW",
    "DEEP",
    "time_variants",
    "best_price_share",
    "deep_sizeof",
    "measure_memory",
]

#: Orders cluster tightly at the touch, so few levels are ever occupied.
SHALLOW = MarkParams(depth_decay=0.45)
#: Orders spread far from the touch, so the occupied levels pile up.
DEEP = MarkParams(depth_decay=0.02)


@dataclass(frozen=True)
class Session:
    """A materialised stream, so every variant is measured on identical input."""

    name: str
    messages: list[Message]

    @property
    def prices(self) -> list[int]:
        """The range the stream visits, for the books that must be sized in advance."""
        return [m.price for m in self.messages if not is_market_price(m.price)]

    def occupied_levels(self) -> int:
        """``L`` at the end of the run: what the best-price scan actually costs."""
        book = AggregateBook()
        run(book, self.messages)
        return len(book.bids) + len(book.asks)


def session(name: str, marks: MarkParams, horizon: float = 400.0, seed: int = 0) -> Session:
    """Simulate one stream and materialise it."""
    simulator = OrderFlowSimulator(rng=seed, marks=marks)
    book = AggregateBook()
    simulator.warm_up(book, horizon=30.0)
    messages = []
    for message in simulator.stream(book, horizon=horizon):
        book.apply(message)
        messages.append(message)
    return Session(name=name, messages=messages)


def time_variants(variants, session: Session, repeat: int = 3) -> dict[str, float]:
    """Seconds to fold the whole session, best of ``repeat``, per variant.

    Best-of rather than mean: the distribution's left tail is the machine doing only
    our work, and everything above it is interference we are not trying to measure.
    """
    timings = {}
    for cls in variants:
        times = timeit.repeat(
            lambda cls=cls: run(cls.for_prices(session.prices), session.messages),
            number=1,
            repeat=repeat,
        )
        timings[cls.__name__] = min(times)
    return timings


def best_price_share(cls, session: Session) -> float:
    """Fraction of run time spent inside ``best_price``, by cProfile.

    The number that says whether the ladder has anything to win at all.
    """
    import cProfile
    import pstats

    book = cls.for_prices(session.prices)
    profiler = cProfile.Profile()
    profiler.enable()
    run(book, session.messages)
    profiler.disable()
    stats = pstats.Stats(profiler)
    total = stats.total_tt
    # Cumulative, not own, time.  `best_price` scans by calling `max`, and cProfile
    # bills a builtin to itself -- so the method's own time is nearly nothing while the
    # work it is responsible for sits one frame below it.  Measuring the wrong one of
    # these reports 3% where the truth is ten times that.
    inside = sum(
        entry[3] for key, entry in stats.stats.items() if key[2] == "best_price"
    )
    return inside / total if total else 0.0


def deep_sizeof(obj, seen: set[int] | None = None) -> int:
    """Bytes held by an object *and everything it owns*.

    Written out rather than imported because the thing worth showing is why it is
    needed: ``sys.getsizeof`` reports the container and not its contents, so a dict of
    a thousand levels measures the same as an empty one.  Two caveats it does not
    correct for, and should not: small integers are shared, so counting them twice
    overstates; and anything reached twice is counted once, which is why ``seen`` exists.
    """
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return 0
    seen.add(id(obj))
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for key, value in obj.items():
            size += deep_sizeof(key, seen) + deep_sizeof(value, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            size += deep_sizeof(item, seen)
    elif hasattr(obj, "__dict__"):
        size += deep_sizeof(vars(obj), seen)
    return size


def measure_memory(variants, session: Session) -> dict[str, dict[str, int]]:
    """Static and allocated size of each variant after folding the session.

    Both, because neither alone is honest: the static walk misses what was allocated
    and released along the way, and the tracemalloc peak misses nothing but attributes
    everything, including the stream itself.
    """
    measurements = {}
    for cls in variants:
        tracemalloc.start()
        book = cls.for_prices(session.prices)
        run(book, session.messages)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        measurements[cls.__name__] = {
            "resident": deep_sizeof(book),
            "traced_current": current,
            "traced_peak": peak,
        }
    return measurements
