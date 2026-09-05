# Dev context — Market microstructure

## Goal

Develop an introductory strand on **market microstructure**, bringing an
industry perspective on how markets actually work at the level of orders,
quotes, and execution.

## Scope

The strand is built as a **ladder of toy problems of increasing complexity**, each rung
a complete, tested artefact. The organising idea, and the thing students should leave
with, is the break between **aggregation and identity**:

- the aggregate `{price: size}` book is a *sufficient statistic for the public book* —
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
- `unito26/lob/session.py` — the `MarketSession` and the four ways of building one
- `unito26/lob/statistics.py` — the one declaration the columns, their order, their
  coverage flags and the fold's write positions are all read off
- `unito26/lob/delta_log.py` — a session recorded as level changes rather than states
- `unito26/lob/hawkes.py` — multivariate Hawkes with exact simulation
- `unito26/lob/simulate.py` — marks: event type to order, against a live book
- `unito26/lob/lobster.py` — the file pair, the price-unit conversion, the loaders and
  the windowed aligned read; `MarketSession.from_lobster_files` builds a session from
  one. Still short of L6, which reconstructs the book from the messages rather than
  reading the states the file already carries

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

`notebooks/a-session-from-lobster-files.ipynb` is the first session on real data, and the
only place the measurements below can be reproduced, `data/` not being in the repository.

`notebooks/the-cost-of-the-statistics.ipynb` asks what the statistics on the fold cost, and
is the notebook to re-run before changing what `_write_statistics` reads. Two decisions in
`unito26/lob/orderbook.py` rest on it: that `submit` accumulates the traded totals rather
than the fold recording fills, and that the sweep costs reuse `SideStatistics.levels`.

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

From the third pass, which set out to find why `TickArrayBook` was the *slowest* rung in
the session fold and ended up retiring two findings above
(`notebooks/why-the-tick-array-book-is-not-faster.ipynb`).

**The measurement was wrong three ways, and only the third was about the code.**

- **the band was sixty times too wide, because a sentinel leaked into it.** The notebook
  sized it with `p < 10**9`, which removes `MARKET_BUY_PRICE = sys.maxsize` and keeps
  `MARKET_SELL_PRICE = 0`. The two sentinels fail asymmetrically — the buy one is the
  maximum and raises `MemoryError`, the sell one is the minimum and silently widens — so a
  filter written for one lets the other through, which is the same trap as the padding
  sentinels. `for_prices` now drops both itself, so no caller can repeat it;
- **the regime measured was the one where no index can win.** `example_mark_params` gives
  about 13 occupied levels a side; `max()` over 13 dict keys is one C loop. With
  `deep_mark_params` (136 a side) the dict rungs double and the tick array barely moves;
- **bare `apply` is 0.005s of a 0.276s fold.** The matching the ladder was built to time is
  about 2% of the work. The fold's cost is recording, and recording goes through
  `occupied_levels` — which is where the index earns its keep, and where the ladder should
  have been read all along.

**Two findings above are retired.**

- *"`TickArrayBook` is the slowest rung at `occupied_levels(depth=10)`"* — retired. The
  cause was the ask side: `bit_length()` finds the highest set bit in O(1) and the lowest
  only by scanning, so the sell side paid for the span at every lookup. `TickArrayBook` has
  a band, therefore a *ceiling*, so its sell side is now indexed downward from it and the
  best price is the highest set bit on both. On a 40 000-tick band: `best_ask` 1.626 →
  0.121 µs, `occupied_levels(SELL, 10)` 18.58 → 3.16 µs. `BitmapBook` cannot do this — it
  has no upper edge, and that is now the substance of the step between the two rungs;
- *"the gap statistics are where the bitmap books earn their keep"* — retired, and it was
  already half-retired once. Two consecutive occupied prices bound exactly one maximal run
  of empty positions, so the gaps fall out of the walk that produced the levels; that beats
  masking the occupancy integer by about 1.4×, and it flattens `BitmapBook` onto the
  dictionaries. `TickArrayBook` keeps a 3× lead on a deep book, but for a different reason
  than the entry claimed: not how the gaps are counted, but how the levels are *found*.

**Measured and rejected.** Three, and the last is the one worth teaching.

- **the strided padding fill loses.** Filling a row's padding with `target[k::4] = padding`
  instead of a `while` loop costs about a microsecond of numpy overhead, which is four or
  five scalar writes; the crossover is around eight padded cells a side. What works instead
  is not writing the padding at all — the buffer is pre-filled once and a row writes only
  its occupied levels (1.02×/1.56×/3.15× at ten/six/two occupied of ten). **That has a
  trap**: growth allocates with `np.empty`, and a tail that is not repainted hands freed
  memory to the frame as small integers that pass the schema. The pre-fill therefore lives
  inside `_RowBuffer`, at allocation and on every growth;
- **preallocating from `length_hint` is worth 1–2%.** Kept for what is not speed: `claim()`
  leaves the hot path, and for a list the growth path never runs. Note `length_hint` is
  exact for `iter(list)` and zero only for a real generator — a growth test that reaches for
  `iter()` silently tests nothing;
- **occupancy as a hierarchy of words is a crossover in Python, not a win.** The structure
  `BitmapBook`'s docstring credits to C++ — words plus a summary — measured against one
  arbitrary-precision integer with everything else held identical: 0.93× at 893–4 127
  ticks, 1.21× at 16 127, 1.41× at 64 127. In C++ a bitset *is* a `uint64_t[]`, so the
  hierarchy is the implementation and not an optimisation. In Python `int.bit_length()` is
  already O(1), so it buys nothing on the read; what it could buy is on the write, since
  immutable integers make `bits |= 1 << i` copy ⌈width/30⌉ digits. Against that it adds a
  shift, a mask, a list index and an inner loop to every level of every walk. Below a few
  thousand ticks the interpreter overhead exceeds the digit copies. **No sixth rung**: the
  crossover sits above every band this material uses.

**Where it ends up.** Full fold with online statistics, same machine, same streams, the
notebook's own band:

| | before | after |
| --- | --- | --- |
| shallow, `AggregateBook` | 0.318 | 0.193 |
| shallow, `TickArrayBook` | **0.365** | **0.165** |
| deep, `AggregateBook` | 0.905 | 0.401 |
| deep, `TickArrayBook` | 0.415 | 0.185 |

The bold row is the finding this pass started from: the top of the ladder was slower than
the bottom. `TickArrayBook` is now the fastest rung in both regimes. None of the changes was
a better way to find a best price.

**Three more gap statistics**, since the existing two say how many holes a side has and how
long the longest is, but not where: `FirstGapDistance`, `FirstGapSize`,
`LargestGapDistance`. Both routes — from a book and vectorized from the frame — verified to
agree row for row on both regimes. On the deep book the nearest gap is a median of 1 tick
from the touch and the largest spans up to 27 levels.

From the sweep-cost / OFI / VWAP work (`notebooks/the-cost-of-the-statistics.ipynb`, 34.8k
messages, reported depth 10). **Three of these contradict the review that shaped the plan**,
which is why the notebook exists rather than the estimate:

- **the statistics, not the book, are the fold.** Against a fold with them off: the existing
  statistics cost 3.5–3.7×, and adding three sweep sizes and three windows takes it to
  4.3–4.4×. So everything added here is about 20% on top of what was already being read,
  and the whole family is four times the cost of driving the book;
- **windows are free in the fold, as predicted.** `+ sweep` to `+ windows` is 1.22s to 1.24s.
  A window is a reduction over a recorded series and is made once at assembly; if that column
  ever stops being flat, something is being computed per message that should not be;
- **recording would have cost 1.6–3.2% of the fold, not the 8–11% the review measured.**
  `apply` with `record=True` costs +75% to +174% — the review's ratio, confirmed — but
  `apply` is only 1.6–2.1% of the fold here, and the product is what lands. The decision to
  accumulate three integers in the matching loop instead stands either way, and it costs
  nothing measurable; but the *reason* given for it in the plan was three times too large.
  Neither number means anything alone, which is the transferable lesson;
- **reuse and batching are both levers, and which one dominates depends on the
  specification** — where the review said reuse was worth 83–95% and batching "a 2%
  pessimisation at three sizes". On the deep book, sweep cost above the two side walks it
  shares: at **one** size, reusing `SideStatistics.levels` is nearly the whole saving
  (depth 50: 0.0029s → 0.0001s; depth 10: 0.0010s → 0.0003s), because the walk dominates a
  single accumulation. At **ten** sizes, batching is the bigger one (depth 10, reused:
  0.0059s → 0.0023s), because the accumulation dominates the walk. Together at depth 50 and
  ten sizes: 0.0093s → 0.0026s. Batching is not a pessimisation at three sizes here
  (0.0017s → 0.0012s at depth 10);
- **there is no crossover between the two routes.** The statistics cost 0.88–0.96s online
  against 0.046s vectorised over the finished frame — about 20×, at every size measured. The
  online route exists because it is the *fold*, not because it is ever faster. The real
  asymmetry is elsewhere: VWAP has no from-frame route at all;
- **pandera costs 1.3% of the fold here, not 15%.** `lobster_book_schema.validate` is 0.015s
  against a 1.11s fold. The `Int64` coercion the review identified is real and does widen the
  frame — 11.4MB to 12.8MB, one contiguous int64 block becoming one masked column per field
  — but the time it takes is not where this path spends anything;
- **a sweep column on a thin book is mostly empty, and that is the finding to teach.** A
  sweep size is an absolute number of shares. On the deep regime at reported depth 1,
  `SweepCostBuy400` is priced on 7.1% of messages and `SweepCostBuy1600` on **none of them**;
  at depth 10 they reach 99.9% and 71.7%. The `Covered` flag separates "cannot be filled at
  any price", which is an answer, from "the window ended", which is not. Choosing a sweep size
  without looking at this produces a column that is NaN more often than not and reads like a
  bug in the code.

From the LOBSTER loader (`notebooks/a-session-from-lobster-files.ipynb`, the 2012-06-21
sample, eight ticker-days, 3,499,101 book states).

- **Hidden liquidity is a fifth of the prints and all of it is inside the spread.** On AMZN,
  2,445 of 11,419 executions are type 5, carrying 197,507 of 810,755 shares — and **100% of
  that volume prints strictly inside the spread that stood before it**, against 0% of the
  visible volume. So the lit VWAP (22,264.01 ticks) and the whole-tape VWAP (22,263.48) differ
  by less than a tick while describing quite different things, which is why the session counts
  type 4 only and says so rather than splitting the difference;
- **the windowed read is bounded by the rows kept, not by the file.** Five minutes of SPY at
  depth 50 — 77,829 of 1,154,737 rows — is 124 MB of frame and about 4 s, against a 1.4 GB
  file that would not fit comfortably. Skipping still streams the text, so a window at the end
  of a file costs the same memory and more time than one at the start;
- **padding at depth 50 is an opening artefact, not a market state.** All 108 padded rows of
  the AAPL depth-50 file fall in the first 0.64 seconds, before the book has filled to fifty
  levels, and the side holds 40 to 49 levels there. Any window that does not start at 09:30
  contains none, so an assertion about padding written over a later window is vacuous rather
  than passing — which is a trap worth setting for students deliberately;
- **LOBSTER writes a row per resting order consumed, and four fifths of those are queue
  splits.** Grouping visible executions on the exact integer clock: 22.9% of AMZN's trades are
  multi-row and hold 43% of its executions; on INTC it is 48.6% and **86%**, with one trade
  spanning 105 rows. Splitting by whether the rows share a price — a *queue split*, which no
  sequence of aggregate states determines — gives 80% AMZN, 79% GOOG, 82% AAPL, 99% INTC. This
  is the aggregation-versus-identity break arriving as a property of a file, and it is why a
  folded session and a loaded one are not row-wise comparable. See
  [`lobster-execution-granularity.md`](lobster-execution-granularity.md).

## Exercises & exam snippets

Harvested from the implementation, for the multiple-choice format: float tick prices; a
market-order remainder resting at price 0; inverted imbalance sign; a stale heap top used
without popping; a recorder that stores the book instead of a copy; index-keyed rather
than price-keyed deltas; code answering "am I filled?" from aggregate size;
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
  size 0, and `set_size`'s zero rule silently removes it. "Why does this bug *not*
  bite?" tests the removal invariant, and is a better question than "find the bug";
- **a type-7 halt message** replayed as an order at price −1.

From the performance pass, all three live mistakes rather than invented ones:

- **`[m.price for m in messages if m.price < 10 ** 9]`** — sizing a tick band from a
  message stream. It removes one sentinel and keeps the other, and the band comes out sixty
  times too wide with no error and no wrong answer, only a book that is quietly slower. "What
  does this filter miss, and how would you notice?" The answer is that you would not;
- **`length_hint(iter(some_list))`** — a test that wants to exercise a buffer's growth path
  and reaches for `iter()`. It returns the exact remaining length, so the buffer is sized
  ahead and the path under test never runs. The test passes, and would pass just as well if
  the code were deleted;
- **a pre-filled buffer that doubles.** `grown = np.empty(...)`, copy the used rows, and
  forget the tail: rows past the boundary carry freed memory in whatever columns nothing
  writes. Ask for the values it produces — small non-negative integers that pass a
  `Check.ge(0)` schema and read as a crossed book. Better than "find the bug", because the
  bug is a missing line rather than a wrong one.

From the sweep-cost / OFI / VWAP work. Every one of these is a **plausible wrong answer**
rather than an error, and four of them were found by review or by measurement rather than by
a failing test:

- **`np.where(pb[1:] >= pb[:-1], sb[1:], -sb[:-1])` for the bid half of `e_n`.** The best of
  the whole set. It reads as an exact transcription of Cont–Kukanov–Stoikov's indicator, and
  it loses only the case where the price is *unchanged* and **both** indicators fire — which
  is most of the events. A limit buy of 50 joining the best bid gives −50 where the answer is
  +50; a message that changes nothing gives −100 where the answer is 0. It differs on 47.8%
  of a random touch sequence and turns a session OFI of −2065 into +349,755: same sign
  convention, same shape, two orders of magnitude out and the wrong way up. Ask what it
  computes, not where the bug is;
- **`NaN >= NaN` in those indicators.** A padded touch gives a NaN price, both comparisons
  are False, and the expression evaluates to an ordinary **0** where the event is undefined.
  Twelve rows of a 5738-message session, silently. The mask is not implied by the formula and
  has to be written;
- **`0 * nan` in the vectorised sweep.** A padded level has size 0 and price NaN, so
  `taken * price` is NaN where nothing was taken, and a perfectly determined row comes back
  NaN — no warning emitted;
- **masking the sizes as well as the prices** when the sentinels are cleaned. `before`, the
  cumulative size above each level, then goes NaN for every level under a padded one. "Why
  does cleaning *more* of the frame break it?" is a better question than "find the bug";
- **`abs(value / size - mid)` for the sweep cost**, in place of `direction * (…)`. It agrees
  on every uncrossed book — 20,000 random trials — which is exactly why it survives review.
  Handed the wrong side it returns a well-formed tick cost that is silently the other side's;
  on a crossed row, which real LOBSTER files contain and `describe_orderbook` already counts,
  it reports a *gain* as a cost and makes the per-share cost fall in the size;
- **a statement de-dented out of its `if`, in a recorder.** The trade columns were written
  outside `if online_statistics:` in `from_top_of_book` and inside it in
  `from_occupied_levels`, with the comment explaining them left behind at the inner
  indentation. Nothing in the output changed, because the buffer is discarded when the
  statistics are off, so no test could fail — but the notebook times those two recorders
  against each other on exactly that path and reports them as one session recorded two ways,
  so the wasted work was charged to one side of a published comparison. The fix that makes
  it impossible is not the indentation: it is allocating the buffer only where it is used,
  so the stray call meets `None` and raises. "What would you have to write to catch this?"
  is a better question than "find the bug";
- **reading `buffer.array` before `buffer.claim()`.** `claim` may grow the buffer, which
  replaces the array, so the write lands in the copy about to be discarded — or, past the
  boundary, raises `IndexError`. This one was a live bug here, caught by the growth test the
  earlier pass left behind;
- **a rolling window on a float lookback.** `f"{w:g}"` names a column `OFI0.5`, and
  `frame.query("OFI0.5 > 0")` fails in a way that reads as a pandas bug; `1e6` names
  `OFI1e+06`; and two windows differing below `%g` precision name one column, so the frame
  comes back a column short of what was asked for.

From the LOBSTER loader work. The theme is a data pipeline: every one of these produces a
complete, plausible answer, and most of them pass a test suite written from the same sample.

- **`Direction * Size` for signed volume.** It runs, it stays in range, and it is what the
  column is called — and it inverts every signed-flow signal built on it, because LOBSTER
  reports the *resting* side of a fill. The discriminating observation is worth shipping
  with the snippet: written correctly, every visible execution prints on the far side of the
  mid that stood before it; inverted, every one prints on the near side. Ask what the sign
  means, not where the bug is;
- **`Price >= 0` on a message schema.** It passes all eight shipped files and rejects a
  trading halt, which writes `-1` there — and on a halt `Price` is not a price at all but a
  status code, `-1`, `0` or `1`. "Why does this schema pass every test and fail in
  production?" The answer is that the tests were written from the same data as the schema.
  (`OrderID > 0` is the weaker sibling: 2,445 rows of the AMZN sample carry 0, so it fails on
  day one and teaches only that the specification is worth reading);
- **`dtype="int8"` on the `Type` column.** Declaring the dtype is the right instinct;
  narrowing it is not. A corrupt `Type` of 260 becomes 4 — a valid visible execution —
  inside `read_csv`, and the membership check downstream then passes it. The declaration
  meant to catch the corruption is what launders it;
- **a one-row `skiprows` slip on the orderbook file.** It yields a *complete* session: every
  statistic finite, the spread distribution unchanged, no warning, and every timestamp on
  the wrong book state. "How would you notice?" Nothing in the output reveals it, and the
  files carry no key to check against — only a reconciliation with an independent
  computation finds it. The best snippet of the set, because it is a silent failure of a
  data pipeline rather than of a formula;
- **`groupby(messages.Time)` to aggregate executions into trades.** Right answer, unsound
  method: it is exact-bit equality on a float, and it works only because the clock counts
  from midnight. The same nanosecond resolution on a Unix epoch has a float64 spacing of
  238ns and every group merges. "What would have to change for this to stop being correct?"
  is the question, not "is it correct";
- **`unique=True` on the timestamp index.** The constraint a reader adds next, and it rejects
  3% of a LOBSTER session — the tied rows being exactly the queue splits, where one incoming
  order consumed several resting ones at a single instant;
- **mean execution size as mean trade size.** LOBSTER records executions against resting
  orders, not trades; its own demo says so and it is still the easiest number to get wrong.

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
- [`documentation/from-lobster-files-to-a-session.md`](../documentation/from-lobster-files-to-a-session.md)
  — the LOBSTER format itself: the two files and their positional alignment, the padding
  sentinels, the halt convention, the clock, and the constraints a schema written from the
  sample gets wrong. Self-contained, since `data/` is not in the repository.
- [`lobster-execution-granularity.md`](lobster-execution-granularity.md)
  — the one question that file leaves open: LOBSTER writes a row per resting order consumed
  where our fold writes one per message, so a folded session and a loaded one are not
  row-wise comparable. Undecided.
- [`documentation/integers-in-binary.md`](../documentation/integers-in-binary.md)
  — the bit vocabulary `BitmapBook` and `TickArrayBook` are written in: an integer as a set
  of positions, two's complement, and `b & -b`. Prerequisite for entry 4 of the above.
- [`.claude/plans/order-book-from-order-stream.md`](../.claude/plans/order-book-from-order-stream.md)
  — the agreed plan for batch 1, kept so the code can be reviewed against it.
- [`.claude/plans/lobster-frames-and-market-session.md`](../.claude/plans/lobster-frames-and-market-session.md)
  — the plan for the serialization, the gap statistics and `MarketSession`.
- [`.claude/plans/tick-array-book-performance.md`](../.claude/plans/tick-array-book-performance.md)
  — the plan for the third pass: the diagnosis, the five changes, the three rejections, and
  the conditions the correctness review attached to each.
