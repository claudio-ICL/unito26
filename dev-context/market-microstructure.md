# Dev context — Market microstructure

## Goal

Develop an introductory strand on **market microstructure**, bringing an
industry perspective on how markets actually work at the level of orders,
quotes, and execution.

## Scope

The strand is built as a **ladder of toy problems of increasing complexity**, each rung
a complete, tested artefact. The organising idea, and the thing students should leave
with, is the break between **aggregation and identity**:

- the aggregate `{price: volume}` book is a *sufficient statistic for the public book* —
  the transition depends on `min(q, V[pi])`, which is blind to how `V[pi]` splits into
  orders;
- it stops being sufficient the moment a question concerns a **named** order: where am I
  in the queue, will I be filled, whose fill was that, what is account X's PnL;
- the two perspectives that force order-level state are the **trader** (queue position
  drives fill probability and adverse selection) and the **venue** (fill attribution).

Cancellation is a *consequence*, not the cause: a withdrawal naming `(price, size)` is one
more aggregate delta and breaks nothing. That is why quantity-addressed withdrawal sits
just *before* the break in the ladder — it looks as though it should force identity, and
it does not.

The ladder: **L0** one side, submissions only · **L1** two sides, matching · **L2** market
orders and exhausted sides · **L3** quantity-addressed withdrawal (the near miss) ·
**L4** identity, the order-level book · **L5** queue position, fill attribution, PnL.

**L6 — reconstructing the real LOBSTER book from its message file — is the aspiration the
ladder points at, and is deliberately not built.** Its edge cases are documented so the
remaining leap is legible from wherever we stop.

## Status

**Batch 1 (L0–L3, plus the whole performance ladder) is built and tested**: 63 tests.

Built:

- `unito26/lob/messages.py` — the `(t, q, p, d)` tuple, tick grid, fills, level deltas
- `unito26/lob/orderbook.py` — `AggregateBook` plus the four performance variants
- `unito26/lob/replay.py` — the fold and the snapshot taps
- `unito26/lob/hawkes.py` — multivariate Hawkes with exact simulation
- `unito26/lob/simulate.py` — marks: event type to order, against a live book
- `unito26/lob/lobster.py` — read-only loader and descriptive statistics

Still to do:

- **Batch 2 (L4–L5)**: the order-level book appended to the *same* `orderbook.py`, with
  three removal-by-name strategies benchmarked, `to_levels()`, the bridge test, and
  entries 6–7 of the documentation
- notebooks, one per rung
- L6, as a separate later commit

## Notebooks / code

Reusable code lives in `unito26/lob/`; both book representations share **one file** on
purpose, because the aggregation/identity break is only legible when they sit side by
side and `to_levels()` is the morphism between them.

The synthetic flow is a **multivariate Hawkes process with a common exponential kernel**.
The common decay is what makes the state a `d`-vector rather than a `d x d` matrix, and
it reduces the multivariate case to the scalar Dassios–Zhao exact scheme: O(1) per event,
no rejection, no time grid. That reduction is *derived* rather than quoted, so it is
certified numerically by the random-time-change residual test.

## Measured findings worth teaching

Recorded because two of them contradicted the plan's own predictions:

- with a realistic **shallow** book (~12 occupied levels) the best-price lookup is 12.8%
  of run time and **no optimisation on the ladder helps** (0.93×–1.04×);
- with a **deep** book (~966 levels) it is 92.2% of run time and the same optimisations
  give 2.6×–3.3×;
- so the ladder's lesson is a conditional, not a ranking: whether the bottleneck exists is
  a property of the market, not of the code;
- the array-backed variant first measured 0.18× because it was written without the cursor —
  a real number about a strawman, and a lesson in benchmarking its own design fairly.

## Exercises & exam snippets

Harvested from the implementation, for the multiple-choice format: float tick prices; a
market-order remainder resting at price 0; inverted imbalance sign; a stale heap top used
without popping; a snapshot tap that stores the book instead of a copy; index-keyed rather
than price-keyed deltas; code answering "am I filled?" from aggregate volume;
`(b & -b).bit_length() - 1` on an empty side, wrong by one and never by an exception.

## References

- [`documentation/order-driven-markets-notation.md`](../documentation/order-driven-markets-notation.md)
  — the notation and mechanics, as fixed in the notes (`documentation/tex/notes/orderdriven/`)
  and used by the `market-microstructure` skill.
- [`documentation/order-flow-to-order-book.md`](../documentation/order-flow-to-order-book.md)
  — the mathematics of the implementation, each result tied to the code region carrying it
  and the test certifying it. The starting point for the lecture notes on this part.
- [`documentation/integers-in-binary.md`](../documentation/integers-in-binary.md)
  — the bit vocabulary `BitmapBook` and `TickArrayBook` are written in: an integer as a set
  of positions, two's complement, and `b & -b`. Prerequisite for entry 4 of the above.
- [`.claude/plans/order-book-from-order-stream.md`](../.claude/plans/order-book-from-order-stream.md)
  — the agreed plan, kept so the code can be reviewed against it.
