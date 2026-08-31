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

**Batch 1 (L0–L3, plus the whole performance ladder) is built and tested.**

Built:

- `unito26/lob/messages.py` — the `(t, q, p, d)` tuple, tick grid, fills, level deltas,
  and the `GridDepth` / `ReportedDepth` types that keep the two level counts apart
- `unito26/lob/orderbook.py` — `AggregateBook` plus the four performance variants; the
  derived quantities of §4, and the occupied-level and gap statistics
- `unito26/lob/binary_gaps.py` — an integer as a set of bit positions
- `unito26/lob/frames.py` — pandera schemas and the round trips to validated DataFrames
- `unito26/lob/config.py` — example parametrizations, frozen as serialized frames
- `unito26/lob/replay.py` — the fold, and the `MarketSession` it produces
- `unito26/lob/hawkes.py` — multivariate Hawkes with exact simulation
- `unito26/lob/simulate.py` — marks: event type to order, against a live book
- `unito26/lob/lobster.py` — read-only loader and descriptive statistics

The simulator no longer offers a submission-only mode: the ladder's early rungs are a
conceptual progression, not a runtime switch.

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

From the `MarketSession` work (`notebooks/simulated-market-session.ipynb`, 16.7k messages).
Three of these contradict the predictions written into the plan, which is the useful half:

- **the gap statistics are where the bitmap books earn their keep.** Against the dict
  baseline: shallow book (18 occupied levels) 1.9×/1.35× for `BitmapBook`/`TickArrayBook`,
  deep book (241 levels) **2.2×/5.8×**. Same conditional as the best-price ladder — the
  optimisation targets a bottleneck, and whether it exists is a property of the market;
- **`TickArrayBook` is the *slowest* rung at `occupied_levels(depth=10)`** — 1.04s against
  the baseline's 0.59s. Walking the occupancy bits one at a time with `bits ^= 1 << index`
  builds a fresh arbitrary-precision integer per level, and on a wide band that costs more
  than a dict lookup. The fusion that wins on the gap statistics loses here;
- **`from_top_of_book` and `from_occupied_levels(1)` tie** (0.216 vs 0.217 on the baseline),
  where the plan predicted the four-lookup route would lose. This was a flaw in the
  experiment rather than a fact about the books: both routes computed the same *statistics*
  per message, and that dominated the two-versus-four best-price lookups. With the
  statistics switched off the two still tie (0.016 vs 0.015), so the tie is real and the
  first measurement could not have shown it;
- **`from_delta_log` beats dense recording where reaching ten occupied levels is
  expensive** — on `TickArrayBook` 0.053 against 0.097, on `BitmapBook` 0.055 against
  0.063, and it loses on the dict-backed rungs. Recording the log costs a further 0.011 to
  0.014, which is what tips the dict-backed cases against it. The prediction that a
  reconstruction must always lose was wrong: the rebuild does no matching at all;
- `CachedBestBook` is fastest on every recording strategy;
- **the column-sliced imbalance differs from the grid-indexed one on 23% of rows, and by
  as much as 1.58** — on a scale that only spans 2. Not a perturbation: a different
  statistic;
- **coverage is sharp.** At reported depth 1 only `I^1` is recoverable; at depth 2, `I^2` is
  recoverable everywhere and `I^3` on 0.3% of rows; at depth 10 everything asked for. How
  deep a file you need is a question about the market, not the code.

From the second pass over the same work (register, serialization on the classes, and the
fold). Two of these contradict the plan again:

- **the preallocated buffer wins by moving the cost, not by removing it.** Writing each
  row into a contiguous array costs *more* in the fold than appending a Python list
  (0.114 against 0.096 on the baseline) and much less at the end (0.019 against 0.085),
  because `pd.DataFrame` no longer infers a dtype and copies from 16.7k separate lists.
  Net 0.133 against 0.180, about 1.35×;
- **`TickArrayBook.write_lobster_row` is not faster than the inherited version.** Writing
  numpy int64 scalars one at a time costs what building the list costs, so the override
  earns nothing on its own; the rung stays the slowest at depth 10 for the reason already
  recorded above;
- **`apply` returning nothing costs about a third of `apply` recording** (0.009 against
  0.027 over 16.7k messages). Small beside the recording of rows, and the larger saving in
  proportion: the result object costs about twice the update it describes;
- **computing the statistics online costs about 60× computing them vectorized** (0.588
  against 0.010). The earlier notebook compared a computation against a read-off and
  measured nothing; folding twice, with and without the statistics, is what makes the
  difference measurable;
- **batching the four gap statistics into one read of the side flattened the axis-B
  table.** `BitmapBook` against the baseline on a deep book is now 0.038 against 0.044,
  where the per-statistic version gave 2.2×. What is left is finding the occupied levels,
  which every rung must do; the bit tricks act only on what happens after that. The
  optimisation that made the ladder look good was partly the absence of an easier one.

## Exercises & exam snippets

Harvested from the implementation, for the multiple-choice format: float tick prices; a
market-order remainder resting at price 0; inverted imbalance sign; a stale heap top used
without popping; a recorder that stores the book instead of a copy; index-keyed rather
than price-keyed deltas; code answering "am I filled?" from aggregate volume;
`(b & -b).bit_length() - 1` on an empty side, wrong by one and never by an exception.

From the LOBSTER-frame work, all of them live bugs or near-misses in this codebase:

- **index-sliced imbalance** — `.iloc[:, :n]` against the price mask. Both run, both
  return a plausible number in `[-1,1]`, and the wrong one is what most published code
  does. The best snippet in the set;
- **the padding sentinel** — a mean spread near 10⁹, and the plausible fix
  `book[book.BidPrice1 > 0]`, which filters the bid correctly and the ask not at all
  because the two sentinels have opposite signs;
- **units** — `book.spread` against `AskPrice1 - BidPrice1`: which one is in ticks?
- **`skipna`** — two imbalance computations differing only by `min_count=1`; one returns
  NaN on an uncovered window, the other a plausible number;
- **the bid `diff` sign** — a gap counter right on the ask and negative on the bid;
- **`from_lobster_row` on a padded row**, which builds a level at the sentinel price with
  volume 0, and `set_volume`'s zero rule silently removes it. "Why does this bug *not*
  bite?" tests the removal invariant, and is a better question than "find the bug";
- **a type-7 halt message** replayed as an order at price −1.

## References

- [`documentation/order-driven-markets-notation.md`](../documentation/order-driven-markets-notation.md)
  — the notation and mechanics, as fixed in the notes (`documentation/tex/notes/orderdriven/`)
  and used by the `market-microstructure` skill.
- [`documentation/order-flow-to-order-book.md`](../documentation/order-flow-to-order-book.md)
  — the mathematics of the implementation, each result tied to the code region carrying it
  and the test certifying it. The starting point for the lecture notes on this part.
- [`documentation/grid-levels-and-lobster-levels.md`](../documentation/grid-levels-and-lobster-levels.md)
  — the two ways to count a level: the grid indexing the notes use and the occupied-level
  indexing a LOBSTER file uses, why gaps make them differ, and the coverage condition that
  says when `I^n` is recoverable from a file at all.
- [`documentation/integers-in-binary.md`](../documentation/integers-in-binary.md)
  — the bit vocabulary `BitmapBook` and `TickArrayBook` are written in: an integer as a set
  of positions, two's complement, and `b & -b`. Prerequisite for entry 4 of the above.
- [`.claude/plans/order-book-from-order-stream.md`](../.claude/plans/order-book-from-order-stream.md)
  — the agreed plan for batch 1, kept so the code can be reviewed against it.
- [`.claude/plans/lobster-frames-and-market-session.md`](../.claude/plans/lobster-frames-and-market-session.md)
  — the plan for the serialization, the gap statistics and `MarketSession`.
