"""A catalogue of book transitions, one per branch of ``prop.lobUpdate``.

Each example is a book before, one message, and the book after, with the branch it
pins named alongside.  The set is chosen to *tile* the update rule rather than to tell
a sequence of stories: $N_v$ finite or infinite, $N_p$ biting or not, $N = 0$ against
$N \\ge 1$, a remainder or none, and where a remainder lands.  That is what makes it
possible to argue the catalogue is complete, which a list of plausible scenarios never
can be.

The expected states are **derived from the notation, not captured from the code**.  A
fixture recorded by running the implementation certifies nothing beyond that the
implementation has not changed.

The catalogue is consumed three ways: by the tests, which run every book variant
through it; by the notebook, which draws it; and by
``documentation/order-flow-to-order-book.md``, which renders the ladders as text.

**Encoding.** A book state is written here as one ``{price: signed volume}`` map, with
bid volumes positive and ask volumes negative.  That is a convenience for writing
fixtures compactly and for drawing them on one axis; it is *not* how a book is held.
The book itself keeps two sides of non-negative sizes, and nothing in this module's
sign convention should leak into it.
"""

from __future__ import annotations

from dataclasses import dataclass

from unito26.lob.messages import (
    BUY,
    SELL,
    Message,
    is_market_price,
    limit_order,
    market_order,
    withdrawal,
)
from unito26.lob.orderbook import AggregateBook

__all__ = [
    "WorkedExample",
    "CATALOGUE",
    "SECTION_8_BOOK",
    "to_sides",
    "signed_state",
    "reflect",
    "check",
]

#: The book at ``t-`` of section 8 of the notation, in ticks: bid 10.00 x 100,
#: 9.99 x 200, 9.98 x 150; ask 10.02 x 120, 10.03 x 180.
SECTION_8_BOOK = {1000: 100, 999: 200, 998: 150, 1002: -120, 1003: -180}


@dataclass(frozen=True)
class WorkedExample:
    """One transition: a book, a message, and the book it becomes."""

    name: str
    branch: str
    """The case of ``prop.lobUpdate`` this example pins, in the notation's symbols."""
    before: dict[int, int]
    message: Message
    after: dict[int, int]
    unfilled: int = 0
    """Shares the message neither executed nor rested.  Non-zero in one case only."""

    @property
    def transition(self) -> tuple:
        """The example stripped of its prose: what it actually asserts.

        Reflecting twice returns the transition but not the label, so this is what an
        involution test compares.
        """
        return (self.before, self.message, self.after, self.unfilled)


def to_sides(state: dict[int, int]) -> tuple[dict[int, int], dict[int, int]]:
    """Split a signed state into the two non-negative sides the book actually holds."""
    bids = {price: volume for price, volume in state.items() if volume > 0}
    asks = {price: -volume for price, volume in state.items() if volume < 0}
    return bids, asks


def signed_state(book: AggregateBook) -> dict[int, int]:
    """The inverse of :func:`to_sides`: a book's state in the catalogue's encoding.

    Goes through ``levels_map`` rather than ``book.bids``, because not every book keeps
    its volumes in a dict.
    """
    state = dict(book.levels_map(BUY))
    state.update({price: -volume for price, volume in book.levels_map(SELL).items()})
    return state


CATALOGUE: tuple[WorkedExample, ...] = (
    WorkedExample(
        name="a passive buy joins an occupied level",
        branch="N = 0, q^inf = q; the remainder lands where volume already rests",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 75, 999, BUY),
        after={1000: 100, 999: 275, 998: 150, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a passive buy rests inside the spread",
        branch="N = 0, q^inf = q; the best bid improves and the spread narrows",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 50, 1001, BUY),
        after={1001: 50, 1000: 100, 999: 200, 998: 150, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a sell takes part of the best bid",
        branch="N_v bites at n = 1, so N = 0: one price prints and the best is unmoved",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 50, 1000, SELL),
        after={1000: 50, 999: 200, 998: 150, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a sell clears the best bid exactly",
        branch="N = 1 with nothing walked -- the converse of section 6 failing",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 100, 1000, SELL),
        after={999: 200, 998: 150, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="section 8 case A: executed in full, no remainder",
        branch="N_p bites before N_v; q^inf = 0, so the ask side is untouched",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 250, 999, SELL),
        after={999: 50, 998: 150, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="section 8 case B: walks the book and rests the remainder",
        branch="q^inf > 0 inside the old spread; ask indices shift, two levels empty",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 400, 999, SELL),
        after={998: 150, 999: -100, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a sell consumes the whole bid side",
        branch="N_v = +inf: the side empties and P^b is undefined",
        before=SECTION_8_BOOK,
        message=limit_order(1.0, 500, 998, SELL),
        after={998: -50, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a market sell larger than the book",
        branch="market-to-limit: the remainder rests at the price last executed against",
        before=SECTION_8_BOOK,
        message=market_order(1.0, 1000, SELL),
        after={998: -550, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a market buy into an empty ask side",
        branch="no fill, so no price to inherit: the remainder cannot rest",
        before={1000: 100},
        message=market_order(1.0, 60, BUY),
        after={1000: 100},
        unfilled=60,
    ),
    WorkedExample(
        name="a withdrawal away from the best",
        branch="a signed delta on one level; the best price does not move",
        before=SECTION_8_BOOK,
        message=withdrawal(1.0, 60, 999, BUY),
        after={1000: 100, 999: 140, 998: 150, 1002: -120, 1003: -180},
    ),
    WorkedExample(
        name="a withdrawal that empties the best bid",
        branch="the best price moves *down* and the spread widens -- only cancellation does this",
        before=SECTION_8_BOOK,
        message=withdrawal(1.0, 100, 1000, BUY),
        after={999: 200, 998: 150, 1002: -120, 1003: -180},
    ),
)


def reflect(example: WorkedExample, centre: int) -> WorkedExample:
    """The same transition with the two sides interchanged.

    Reflecting prices about ``centre`` and flipping every direction is a symmetry of
    the matching rule: the eligibility test ``pi * d <= p * d`` is invariant under
    ``p -> 2c - p``, ``d -> -d``, ties map to ties, and highest-bid and lowest-ask swap
    roles.  So the sell-side half of the catalogue is *generated*, and the fact that it
    passes is itself a test of the claim that ``d`` collapses both sides into one.

    The sentinel prices are the one part of the encoding that is **not** symmetric.
    They are ``0`` and ``sys.maxsize``, not $\\mp\\infty$, so reflecting the number gives
    an ordinary price: a mirrored market sell would become a marketable limit buy and
    quietly test the wrong thing.  A market order is therefore reflected by its
    *meaning* rather than by its price field.

    ``centre`` must be chosen so that every reflected price stays non-negative.  Note
    the reflected book is a different book, not the section 8 book relabelled: no
    centre maps that one to itself, because its two sides have different shapes.
    """
    def mirror(state: dict[int, int]) -> dict[int, int]:
        # Negating the volume is what swaps the side, the sign being this module's
        # encoding of which side a level is on.  Two operations, one minus sign.
        return {2 * centre - price: -volume for price, volume in state.items()}

    message = example.message
    if is_market_price(message.price):
        mirrored = market_order(message.time, message.size, -message.direction)
    else:
        mirrored = Message(
            message.time,
            message.size,
            2 * centre - message.price,
            -message.direction,
            message.kind,
        )
    return WorkedExample(
        name=f"{example.name} (mirrored)",
        branch=example.branch,
        before=mirror(example.before),
        message=mirrored,
        after=mirror(example.after),
        unfilled=example.unfilled,
    )


def check(book_cls: type[AggregateBook], example: WorkedExample, depth: int = 6) -> None:
    """Run one example through one book class and assert it lands where it should.

    Raises rather than returning a verdict: a check whose result can be discarded is a
    check that will be.

    Beyond the state itself this compares the *derived* views against the baseline --
    ``levels`` and the best volumes.  A book that stores volumes somewhere other than
    the two dicts can agree on best prices and on the level map while returning zero to
    every one of those accessors, and nothing else here would notice.
    """
    bids, asks = to_sides(example.before)
    book = book_cls.from_levels(dict(bids), dict(asks))
    result = book.apply(example.message)

    state = signed_state(book)
    if state != example.after:
        raise AssertionError(
            f"{book_cls.__name__} on {example.name!r}:\n"
            f"  expected {dict(sorted(example.after.items()))}\n"
            f"  got      {dict(sorted(state.items()))}\n"
            f"  branch:  {example.branch}"
        )
    if result.unfilled != example.unfilled:
        raise AssertionError(
            f"{book_cls.__name__} on {example.name!r}: expected {example.unfilled} "
            f"shares unfilled, got {result.unfilled}"
        )
    book.check_invariants()

    reference = AggregateBook.from_levels(dict(bids), dict(asks))
    reference.apply(example.message)
    for direction in (BUY, SELL):
        if book.levels(direction, depth) != reference.levels(direction, depth):
            raise AssertionError(
                f"{book_cls.__name__} on {example.name!r}: levels on side {direction} "
                f"read {book.levels(direction, depth)}, baseline says "
                f"{reference.levels(direction, depth)}"
            )
    if (book.best_bid_volume, book.best_ask_volume) != (
        reference.best_bid_volume,
        reference.best_ask_volume,
    ):
        raise AssertionError(
            f"{book_cls.__name__} on {example.name!r}: best volumes read "
            f"{(book.best_bid_volume, book.best_ask_volume)}, baseline says "
            f"{(reference.best_bid_volume, reference.best_ask_volume)}"
        )


BEGIN_MARKER = "<!-- begin generated: worked examples -->"
END_MARKER = "<!-- end generated: worked examples -->"

INDEXING_BEGIN_MARKER = "<!-- begin generated: indexing example -->"
INDEXING_END_MARKER = "<!-- end generated: indexing example -->"

#: The book that separates the two indexings: an ask side occupied at every tick and a
#: bid side with a nine-tick hole in it.  Prices in ticks, tau = 1.
INDEXING_BIDS = {99: 40, 90: 60}
INDEXING_ASKS = {101: 10, 102: 20, 103: 30, 104: 40, 105: 50}
INDEXING_REPORTED_DEPTH = 2


def render_markdown() -> str:
    """The catalogue as markdown, ladders included, for the companion document.

    Generated rather than written, so the prose and the fixtures cannot drift apart:
    if an expected state changes, the document changes with it or the test that
    regenerates this section fails.
    """
    from unito26.lob.visualization import ascii_ladder, describe_message

    def ladder(state: dict[int, int]) -> str:
        return ascii_ladder(AggregateBook.from_levels(*to_sides(state)))

    blocks = [
        "### The catalogue of transitions",
        "",
        "One example per branch of `prop.lobUpdate`, which is what makes it possible to",
        "argue the set is complete rather than merely plausible.",
        "Each is a fixture in `unito26.lob.worked_examples`,",
        "run against every book variant by the test suite,",
        "with the expected state derived from the notation rather than captured from a run.",
        "The sell-side mirror of each is generated by reflecting prices and flipping $d$.",
        "",
    ]
    for number, example in enumerate(CATALOGUE, start=1):
        blocks += [
            f"**{number}. {example.name.capitalize()}** &mdash; "
            f"`{describe_message(example.message)}`.",
            "",
            f"*Branch:* {example.branch}.",
            "",
            "```",
            ladder(example.before),
            "",
            "    ---- becomes ----",
            "",
            ladder(example.after),
            "```",
            "",
        ]
        if example.unfilled:
            blocks += [
                f"{example.unfilled} shares are reported as `unfilled`: "
                "they neither executed nor rested.",
                "",
            ]
    return "\n".join(blocks).rstrip() + "\n"


def render_indexing_markdown() -> str:
    """The grid-versus-reported evaluation of ``I^n``, worked both ways.

    Generated for the same reason the catalogue is: the numbers appear in the document
    and in ``tests/lob/test_market_session.py``, and two statements of one fact diverge
    on the first edit that touches only one of them.
    """
    from unito26.lob.messages import BUY, SELL, GridDepth, ReportedDepth
    from unito26.lob.orderbook import AggregateBook
    from unito26.lob.replay import MarketSession

    depth = ReportedDepth(INDEXING_REPORTED_DEPTH)
    levels = (GridDepth(2), GridDepth(3))
    book = AggregateBook.from_levels(INDEXING_BIDS, INDEXING_ASKS)
    session = MarketSession.from_occupied_levels(
        AggregateBook.from_levels(INDEXING_BIDS, INDEXING_ASKS),
        [limit_order(1.0, 1, min(INDEXING_BIDS) - 10, BUY)], depth, levels, 1,
    )
    frame = session.stats_from_frame()

    ask_window = [p for p in sorted(INDEXING_ASKS) if p <= min(INDEXING_ASKS) + 1]
    bid_window = [p for p in sorted(INDEXING_BIDS, reverse=True) if p >= max(INDEXING_BIDS) - 1]
    by_price = sum(INDEXING_BIDS[p] for p in bid_window) - sum(INDEXING_ASKS[p] for p in ask_window)
    by_price /= sum(INDEXING_BIDS[p] for p in bid_window) + sum(INDEXING_ASKS[p] for p in ask_window)
    reported_bids = sorted(INDEXING_BIDS, reverse=True)[:depth]
    reported_asks = sorted(INDEXING_ASKS)[:depth]
    by_column = sum(INDEXING_BIDS[p] for p in reported_bids) - sum(INDEXING_ASKS[p] for p in reported_asks)
    by_column /= sum(INDEXING_BIDS[p] for p in reported_bids) + sum(INDEXING_ASKS[p] for p in reported_asks)

    lines = [
        f"Tick $\\tau = 1$.  Asks occupied at "
        f"{', '.join(str(p) for p in sorted(INDEXING_ASKS))}; bids at "
        f"{' and '.join(str(p) for p in sorted(INDEXING_BIDS, reverse=True))} and nowhere between.",
        "",
        f"A file of reported depth {depth} holds:",
        "",
        "| " + " | ".join(session.lobster_book.columns) + " |",
        "| " + " | ".join("---" for _ in session.lobster_book.columns) + " |",
        "| " + " | ".join(str(v) for v in session.lobster_book.iloc[0]) + " |",
        "",
        "| side | reported levels | grid span |",
        "| --- | --- | --- |",
        f"| ask | {', '.join(str(p) for p in reported_asks)} | {book.grid_span(SELL, depth)} |",
        f"| bid | {', '.join(str(p) for p in reported_bids)} | {book.grid_span(BUY, depth)} |",
        "",
        f"The bid side spans {book.grid_span(BUY, depth)} grid positions on "
        f"{len(reported_bids)} reported levels; the ask side spans "
        f"{book.grid_span(SELL, depth)}.  So:",
        "",
        "| quantity | value |",
        "| --- | --- |",
        f"| $I^2$, selecting by price | {by_price:+.6f} |",
        f"| $I^2$, slicing by column | {by_column:+.6f} |",
        f"| $I^2$ recoverable from the file | "
        f"{bool(frame['QueueImbalance2Covered'].iloc[0])} |",
        f"| $I^3$ recoverable from the file | "
        f"{bool(frame['QueueImbalance3Covered'].iloc[0])} |",
        "",
        f"The column-sliced answer pairs the touch at {max(INDEXING_BIDS)} with a level "
        f"{max(INDEXING_BIDS) - min(INDEXING_BIDS)} ticks away and reports it as a "
        "top-of-book signal.  And $I^3$ fails on the **ask** side, which ran out at "
        f"{reported_asks[-1]}, while the bid had "
        f"{book.grid_span(BUY, depth)} positions of room to spare.",
    ]
    return "\n".join(lines) + "\n"


def write_into(path: str, render=render_markdown, begin=BEGIN_MARKER, end=END_MARKER) -> bool:
    """Replace a generated block in a markdown file.  True when the file changed."""
    import pathlib

    file = pathlib.Path(path)
    text = file.read_text()
    start = text.index(begin) + len(begin)
    stop = text.index(end)
    updated = text[:start] + "\n\n" + render() + "\n" + text[stop:]
    if updated == text:
        return False
    file.write_text(updated)
    return True


if __name__ == "__main__":  # pragma: no cover
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "documentation/order-flow-to-order-book.md"
    if "grid-levels" in target:
        changed = write_into(
            target, render_indexing_markdown, INDEXING_BEGIN_MARKER, INDEXING_END_MARKER
        )
    else:
        changed = write_into(target)
    print(f"{'rewrote' if changed else 'unchanged'}: {target}")
