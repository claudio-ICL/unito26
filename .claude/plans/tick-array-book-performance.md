# Why `TickArrayBook` is not faster, and how to make it fastest

## Context

`notebooks/simulated-market-session.ipynb` §11 reports that on the ladder's top rung the fold is
*slower* than on the plain dict book, and §12 that `TickArrayBook.write_lobster_row` earns
nothing. Both readings are artefacts of the setup, not properties of the tick-indexed book.

Seven changes, A–G. No new class: the ladder keeps its five rungs. Everything below was
measured, and everything marked *reviewed* was independently re-derived by a second pass that
ran the real suite against a prototype of each change.

Numbers: 7 200–7 500 messages, reported depth 10, `imbalance_levels = (1, 2, 3, 5, 10)`, best of
three or five, Python 3.14 in the `unito26` env.

## Part 1 — the diagnosis

### 1. The band is 60× too wide, because a sentinel leaks into it

`MARKET_SELL_PRICE = 0`. The notebook sizes the band with
`[m.price for m in messages if m.price < 10 ** 9]`, which catches
`MARKET_BUY_PRICE = sys.maxsize` and lets the sell sentinel through — the trap
`resting_price`'s own docstring names: 0 *is* indistinguishable from a real price. The band
comes out **10 140 ticks wide where 168 are needed**. Both bitmap-backed rungs then carry a
ten-thousand-bit integer that every `set_volume` rewrites and every ask-side `best_price`
negates and masks.

The two sentinels fail asymmetrically, which is why this survived: `MARKET_BUY_PRICE` is the
maximum, so it never moves `origin` and it kills `TickArrayBook` loudly —
`TickArrayBook.for_prices([9995, sys.maxsize])` raises `MemoryError`. `MARKET_SELL_PRICE` is the
minimum, so it silently inflates both bitmap rungs. A filter written for one lets the other
through, exactly as `grid-levels-and-lobster-levels.md` §7 says of the padding sentinels.

| fold, depth 10, no statistics | leaky band | honest band |
| --- | --- | --- |
| `AggregateBook` | 0.065 | 0.056 |
| `BitmapBook` | 0.062 | 0.057 |
| `TickArrayBook` | **0.096** | **0.055** |

`tests/lob/test_market_session.py:58` has the same filter. `benchmark.Session.prices` does not
— it already uses `is_market_price`.

### 2. The regime measured is one where no index can win

With `example_mark_params` the book holds ~14 occupied levels a side. `max()` over 14 dict keys
is one C loop. With `deep_mark_params`, which the repo already ships, it holds ~136:

| fold, depth 10, honest band | ~14 levels/side | ~136 levels/side |
| --- | --- | --- |
| `AggregateBook` | 0.066 | 0.180 |
| `CachedBestBook` | 0.064 | 0.158 |
| `TickArrayBook` | 0.062 | **0.070** |

The dict books triple; the tick array barely moves. That is the ladder's claim, and §11 measures
it where the claim is empty.

### 3. The fold asks the book for the same thing four times a message

Profiling the deep fold with statistics: 14 964 `occupied_levels` calls, 44 892
`queue_imbalance` calls, **155 082 `best_price` calls** for 7 482 messages. Bare `apply` — the
matching the ladder was built to time — is **0.005 s of the 0.276**. The fold's cost is
recording, not matching.

## Part 2 — the two comments in `write_lobster_row`

**"Can we populate the padding with a strided slice instead of the `while` loop?"** Measured,
and no: a numpy strided store costs about a microsecond of fixed overhead, which is what four or
five scalar writes cost, so the crossover is around eight padded slots a side. At full depth it
is 0.99×, at six occupied levels 0.89×, and only at two levels does it reach 1.22×.

**"Is this the best we can do?"** No — see E. Also measured and rejected: a flat `array.array('q')`
with `np.frombuffer` at the end (zero-copy, 1.10× at best) and a flat Python list with one
`np.array` (1.04×).

Both `# For Claude:` comments come out with the change that touches the method — they are
prompts to an assistant, not invariants, and fail the "still true in a year" test.

## Part 3 — the changes

Order of work: **A → C → G → B → E → D**. A first because it changes the bands every other
measurement is taken on; C and G before B because B's numbers should be reported against a
post-C baseline.

### A. `for_prices` filters the sentinels — `orderbook.py` *(reviewed: safe)*

`AggregateBook.for_prices` drops prices for which `is_market_price` is true. **Filter, do not
raise:** `for_prices` is a *sizing* method, its contract is "the range the book must cover", and
a sentinel names no point on the grid, so it contributes no range. Raising would make it
unusable on a raw message stream, which is the one convenience it exists to offer. One line in
the docstring.

Breaks no caller — `from_levels` passes real prices, `DeltaLog.opening_book` passes resting
prices, `benchmark.Session.prices` already filters. Fix the two call sites anyway
(`tests/lob/test_market_session.py:58`, notebook §11): a test that reaches for `10**9` teaches
the wrong habit.

**One consequence to pin with a test:** a genuine level at price 0 stops being sizeable —
`TickArrayBook.from_levels({0: 5}, {500: 5})` will raise "outside the band". The ambiguity is
pre-existing (`resting_price` already says 0 is indistinguishable from a real price); A only
moves where it bites, and the behaviour should be chosen rather than discovered.

*1.6–1.75× on `TickArrayBook`; ~20% even on a narrow book.*

### B. `TickArrayBook` mirrors its ask side — `orderbook.py` *(reviewed: safe, conditions mandatory)*

`documentation/integers-in-binary.md` derives that the highest set bit costs O(1) and the lowest
O(span). Stop asking for the lowest one: index the sell side **downward from the band's
ceiling**, so the best price is the highest set bit on either side. The volume array stays
indexed by `price - origin`; only the occupancy bitmap is mirrored.

```python
self.ceiling = origin + width - 1
# bids: bit (price - origin);  asks: bit (ceiling - price)
def best_price(self, direction):
    bits = self._bits[direction]
    if not bits:
        return None
    index = bits.bit_length() - 1
    return self.origin + index if direction == BUY else self.ceiling - index
```

On a 40 000-wide band with 2 000 levels a side: `best_ask` 1.626 → **0.121 µs (13×)**,
`occupied_levels(SELL, 10)` 18.58 → **3.16 µs (5.9×)**, `side_statistics(SELL, 10)` 27.28 →
**14.85 µs (1.8×)**. Full suite green under a prototype. **Write the index arithmetic inline** —
a `self._price(direction, index)` helper called once per level costs more than the mirroring
saves.

Five conditions, none optional:

1. **Five methods change together**: `set_volume`, `best_price`, `occupied_levels`,
   `span_bits` / `write_lobster_row`, and — the one that gets forgotten — **`levels_map`**,
   which indexes `volumes[index]` with the bit index and returns both wrong prices *and* wrong
   volumes if missed. `test_axis_b_variants.py::test_agrees_with_the_baseline_over_a_whole_session`
   catches it. Ask dict-iteration order flips to descending price; nothing depends on it, but
   `__repr__` and notebook output will look different.
2. **The `BitmapBook` sharing breaks, and it fails silently.** On the case-B book the shared
   `_side_statistics_from_bits` applied to reversed ask bits gives `gap_count=0` where the truth
   is 1 — `largest_gap` comes out right by accident, since gap length is reversal-invariant.
   The clean fix is to have the helper call `book.span_bits(direction, reported_depth)` rather
   than reach into `book._bits` and `book.origin`; both classes already define `span_bits`
   identically, so `TickArrayBook` overrides that one method and the helper stays shared where
   it genuinely is. Keep `test_gap_statistics.py::TestCaseB`'s literal `gap_count == 1` — the
   batched-vs-individual test would *not* catch this, because both routes go through
   `span_bits` and would be wrong together.
3. **The suite does not currently check the ceiling at all.** An injected off-by-one
   (`ceiling = origin + width`) passes all 15 435 tests, because `price ↦ C - price` is
   self-inverse for any `C` as long as encode and decode agree, and `BAND_MARGIN = 64` keeps
   every existing test away from the band edge. The tight ceiling must be pinned by a test that
   constructs the band directly with ask levels at `origin` and at `origin + width - 1`.
4. **`copy()` and `_empty_like()` become load-bearing on `width`.** Today `_bits` depends only
   on `origin`; after B the ask side depends on both. A future `_empty_like` that resized would
   corrupt the ask side and leave the bid side correct. Needs a test that copies a book with an
   ask level at each band edge.
5. **One sentence in the class docstring**: the band's *upper* edge is now semantically
   load-bearing on the ask side, so widening the band at the top stops being free. That is a
   fair trade for 13×, but it should not be a surprise to whoever implements the band-shifting
   the docstring already anticipates.

`BitmapBook` stays correct and unchanged: it has no ceiling by design, so the trick does not
apply. That asymmetry is the price of the band, made visible — a better rung boundary than the
one there now.

### C. Gap statistics from the levels list, not from a bitmask — `orderbook.py` *(reviewed: exactly equivalent)*

`side_statistics` already walks the side to build `levels`. The empty positions between two
consecutive occupied prices form one maximal run of length `|p_{i+1} - p_i| - 1`, and those runs
are separated by occupied positions, so they *are* the maximal runs. Property-tested at **240 360
comparisons across all five rungs, zero disagreements.**

`side_statistics(BUY, 10)` on a 20-level side with holes: `AggregateBook` 0.0332 → 0.0182,
`TickArrayBook` 0.0225 → 0.0135.

**The number that matters is not the speedup.** Before C, `BitmapBook` led the baseline
1.23× on the gap statistics; after C, 1.07×. **C erases what is left of the single-integer
bitmap's advantage here.** `TickArrayBook` keeps its lead, but for a different reason — see G.

`count_binary_gaps`, `measure_largest_binary_gap` and their tests stay exactly as they are, and
are still reached through the `gap_count` and `largest_gap_size_between_non_empty_levels`
overrides. `documentation/integers-in-binary.md` covers only the best-price identities, so it
loses nothing. The honest §13 — an optimisation that beats the obvious code, and a simpler
restatement of the problem that beats them both — is a better lesson than the flattering one,
and is precisely the judgment `CLAUDE.md` says the course is about. Rewrite §13 and the
dev-context entry as part of this change, not after it.

### G. Three more gap statistics a side — `orderbook.py`, `replay.py`, `visualization.py`

`GapCount` and `LargestGap` say how many holes a side has and how long the longest is, but not
*where*. Three more, all over the reported span, all falling out of the same pass as C:

| column | meaning |
| --- | --- |
| `{Side}FirstGapDistance` | ticks from the touch to the shallowest empty position of the gap nearest the touch |
| `{Side}FirstGapSize` | length in levels of that nearest gap |
| `{Side}LargestGapDistance` | the same distance for the largest gap, ties broken toward the touch |

Conventions, fixed because both routes must agree on them: a distance is **NaN** when the side
has no gap — there is no position to name, and 0 would mean the touch itself — while a size is
**0**, matching `LargestGap`. The distance is measured to the empty position, so it equals
`empty_grid_positions(...)[0] - 1`.

- **From a book.** `SideStatistics` gains `first_gap_distance`, `first_gap_size`,
  `largest_gap_distance`. Each also gets its own obvious method on `AggregateBook`, written
  against `empty_grid_positions`, which the batched version is reconciled against — that is the
  pattern `side_statistics`'s docstring already claims, and it must not be broken by the three
  statistics that most need it.
- **From a frame.** `stats_from_frame` gains the vectorized forms. The tie-break comes free:
  `np.argmax` returns the first occurrence of the maximum, which is the one nearest the touch.

Both routes verified to agree exactly, row for row, on both regimes.

Measured, all five gap statistics a side a message:

| | ~13 levels/side | ~136 levels/side |
| --- | --- | --- |
| `AggregateBook` | 0.043 | 0.170 |
| `CachedBestBook` | 0.040 | 0.148 |
| `HeapBook` | 0.044 | 0.151 |
| `BitmapBook` | 0.043 | 0.151 |
| `TickArrayBook` | 0.041 | **0.055 (3.08×)** |

Decisive on a deep book, flat on a shallow one, and the two facts reconcile with C: once the
levels are in hand the statistics are cheap either way, so what this table measures is
`occupied_levels`. The dict rungs answer it with `heapq.nsmallest(depth, …)` over the whole
side — negligible at 13 levels, real at 136 — while the tick array walks exactly `depth` bits.
So C removes `BitmapBook`'s advantage and G shows where `TickArrayBook`'s actually comes from.
Both belong in §13.

**The figure.** `visualization.gap_figure` goes from two panels to three, sharing the x axis, one
panel per *kind* of quantity — a side keeps its colour, and which gap it is is carried by the
dash, the convention `touch_figure` already uses:

| row | panel | traces |
| --- | --- | --- |
| 1 | Spread | spread (mid colour) |
| 2 | Gap size, in levels | `LargestGap` solid, `FirstGapSize` dashed, bid and ask |
| 3 | Distance from the touch, in ticks | `FirstGapDistance` solid, `LargestGapDistance` dashed, bid and ask |

The distances are NaN wherever a side is contiguous, and with the module's standing
`connectgaps=False` the line breaks exactly there — a contiguous stretch of book reads as a hole
in the distance panel, which is the right way round but needs one sentence in the notebook so it
is not read as missing data.

### E. One walk a side a message, into a pre-padded buffer — `replay.py`

**E(i) — the row from `SideStatistics.levels`.** *(reviewed: safe and exact; the best part of the
proposal.)* `SideStatistics.levels` **is** `occupied_levels(direction, reported_depth)` — the
same call, not an equivalence to be argued — so the row can be assembled from it instead of
walking the book a second time. Verified byte-for-byte against `to_lobster_row` across all five
rungs on 1 500 random books × five depths. Worth **9–14%** of an online fold.

Three conditions: it applies only when `online_statistics` is True, so there are two
row-writing paths and `test_writing_in_place_matches_building_a_row` must be extended to cover
the new one rather than left guarding only the old; computing the statistics before the row is
safe, since both read the same immutable state; and it must **not** be expressed as
`write_lobster_row(..., levels=None)` — that is a default on a parameter that changes what the
function means. `to_lobster_row(price_unit, reported_depth)` stays exactly as it is and the new
entry point sits beside it.

**E(ii) — pre-fill the padding pattern.** *(reviewed: the specification as I first wrote it
corrupts data. Reproduced.)* Filling `ASK_PADDING` into columns `0::4`, `BID_PADDING` into
`2::4` and zeros elsewhere **once at allocation** is wrong, because `_RowBuffer.claim()` grows
with `np.empty` and copies only `[:used]`: **every row past a doubling boundary carries freed-heap
bytes in its padded columns.** Reproduced at depth 3 with a one-level-a-side book — row 1024 came
back as `[…, 14, 21, 28, 35, 42, 49, 56, 63]`, which passes the schema's `Check.ge(0)` and reads
as a plausible, absurdly crossed book. The existing suite catches it only at `count=2049`, only
for 4 of 15 combinations, and reports it as a schema error a long way from the cause.

So the pre-fill **lives entirely inside `_RowBuffer`** — at allocation *and* on every growth,
filling only the new tail, which is one bulk store per doubling — and `write_lobster_row`'s
changed precondition is stated in its docstring, since a silent precondition is the bug. With
E(iii) below the growth path does not run at all for a list of messages, which is the second
reason to keep E(iii).

Two more failure modes to close with tests: **a row written twice** stops being idempotent (write
a deep book then a shallow one into the same index and the first write's levels survive as the
second's padding) — `notebooks/simulated-market-session.ipynb:7636` already calls
`write_lobster_row` with a caller-supplied index; and the statistics buffer is safe only because
`_write_statistics` writes every column, which any future conditional write there would
silently break.

`test_writing_in_place_matches_building_a_row` must stay on a `np.zeros` array. The tempting fix
when it fails is to pre-fill the test's array, which destroys the one check that the two row
writers agree on padding.

The saving is **1.02× at ten occupied levels, 1.56× at six, 3.15× at two** per row, and padding
is 17% of level slots in the shallow regime, 0% in the deep one, and 0.1% at the depth the suite
uses. It is a shallow-book, deep-file optimization and the notebook should say so.

**E(iii) — size the buffer from `operator.length_hint(messages, 0)`** when non-zero, keeping the
doubling `_RowBuffer` for generators. Measured at **0.4–1% of the fold**, and the review's verdict
is that it is not worth it on speed alone. I would keep it for the two things it buys that are
not speed: the loop index becomes `enumerate` so `claim()` leaves the hot path along with the
`buffer.array`-before-`buffer.claim()` trap that produced two `IndexError`s last round, and for
a list of messages the growth path — the one E(ii) can corrupt — never runs. `from_delta_log`
needs no hint at all: `len(log.times)` is exact. Doubling stays for **both** directions, since a
hint is documented as an estimate: an over-large one is trimmed by `finished()`, an under-large
one must still grow.

### D. `queue_imbalance_profile` — `orderbook.py` *(reviewed: correct; API amended)*

$I^1, I^2, \dots$ nest, so the whole tuple is one accumulating walk per side rather than one
full walk per level with two `best_price` calls each. On the array-backed rungs the walk is a
slice of the volume array and the prefix sums are `itertools.accumulate`. Verified against
`AggregateBook.queue_imbalance` at 45 090 comparisons across all five rungs: zero disagreements,
including both sides empty (`nan`), one-sided books (`±1`), band-edge windows and `n` far past
the occupied depth.

Three amendments from the review:

- **`queue_imbalance(n)` stays as it is** and does *not* become `profile((n,))[0]`. It is where
  the reader meets the definition of $I^n$, including the sign convention its docstring spends a
  paragraph on; defining it as element zero of a batched accumulator hides the definition inside
  the optimisation, which inverts the teaching order `CLAUDE.md` and the skill both fix. Keep
  both, and test that they agree.
- **The parameter is `imbalance_levels`, not `levels`** — `levels(direction, depth)` is already
  taken on the book, and the two depth counts must not be swappable.
- **The edge case needing a test is the array walk, not the arithmetic**: when the grid window
  runs off the band the slice is shorter than `n`, and the clipped running total has to be
  extended with its own last value, since positions outside the band hold nothing.

*0.060 → 0.021 over five levels; 1.43× over three. The win scales with how many levels are
asked for, and the online statistics cost ~60× the vectorized route regardless.*

## Part 4 — the sixth rung, and why it is not here

`BitmapBook`'s docstring says C++ finds the next active level with "a hierarchy of 64-bit words
and a count-trailing-zeros instruction", and then does the other thing. Building that hierarchy —
a list of words per side plus a summary integer whose bit `w` is set iff word `w` is non-zero —
**is not worth a class.**

Isolated properly, with both books mirroring the ask, taking gaps from the levels list and using
the accumulate profile, so the *only* difference is one big integer against a list of words:

| band | one big integer | words/32 | ratio |
| --- | --- | --- | --- |
| 160 | 0.055 | 0.056 | 0.98× |
| 1 160 | 0.057 | 0.062 | 0.92× |
| 4 160 | 0.059 | 0.064 | 0.92× |
| 16 160 | 0.072 | 0.063 | 1.14× |
| 64 160 | 0.087 | 0.062 | 1.40× |

Same shape on the deep book. Chunking **loses 2–10%** below about 5 000 ticks and wins only above
16 000. LOBSTER bands for this course are hundreds to a few thousand ticks, squarely in the
losing region.

**Why it is right in C++ and only conditional here.** In C++ a bitset *is* a `uint64_t[]`; there
is no arbitrary-precision integer to compare against, so the hierarchy is not an optimization but
the implementation, and the summary word skips empty words with pure ALU work. Python changes
the trade twice. `int.bit_length()` is already O(1), so the hierarchy buys **nothing on the
read**. What it could buy is on the *write*: Python integers are immutable, so `bits |= 1 << i`
allocates and copies ⌈width/30⌉ digits — measured at 209 ns for 256 bits and 2 164 ns for
65 536, against a flat 278–293 ns chunked. But chunking *adds* a shift, a mask, a list index and
an inner loop to every level of every walk, and that constant is paid on every message. Below
~5 000 ticks the added interpreter overhead exceeds the digit copies it saves.

The conditional is the finding, and it belongs in the notebook: the structure that is
unambiguously right in C++ is a **crossover** in Python, and the crossover sits above the band
widths this material uses.

The measurement above is the isolated one — same mirroring, same gap route, same imbalance
profile on both sides of the comparison, so the only variable is the occupancy structure. My
earlier "1.42× for the word hierarchy" was a bundle of four changes and is withdrawn.

### End to end, on the notebook's own band

| full fold, online statistics | shallow | deep |
| --- | --- | --- |
| `AggregateBook` today | 0.329 | 0.944 |
| `TickArrayBook` today | 0.369 | 0.433 |
| after A–G | **0.111** | **0.136** |

## Notebooks

**New: `notebooks/why-the-tick-array-book-is-not-faster.ipynb`** — the diagnosis in the order
above, each section one measurement and one paragraph: the claim being tested and bare `apply`
at 0.005 s; the sentinel leak with both bands printed and both sentinels' asymmetric failure;
the two depth regimes side by side with occupied levels per side in the same table; the profile
and its call counts; each change added in turn, ending in the table above; and last the
crossover of Part 4. The rejected ideas — strided padding fill, `array.array` plus `frombuffer`,
the word hierarchy — are kept with their numbers. A measured rejection is worth as much as an
accepted change and is the notebook's subject. Figures go in `unito26/lob/visualization.py`.

**Then `notebooks/simulated-market-session.ipynb`:**

- §8 picks up the three-panel `gap_figure`, with a paragraph on what the new panels say and one
  sentence on why the distance lines break.
- §11 and §12 use the honest band and run both depth regimes; the prose after both is rewritten.
- §13 gets C and G together: `BitmapBook`'s advantage on the gap statistics is gone,
  `TickArrayBook`'s is 3.08× on a deep book and nil on a shallow one, and the reason is that
  what is left to measure is `occupied_levels`.

## Documentation

- `documentation/order-driven-markets-notation.md` §9 — `queue_imbalance_profile` and the three
  new gap statistics in the "names carried by the implementation rather than by the notes"
  paragraph, or they will be reinvented. The distance convention is stated once, there.
- `documentation/integers-in-binary.md` — a closing note that the book no longer reads its gap
  statistics off the occupancy integer, with the measured reason. The derivations stand.
- `dev-context/market-microstructure.md` — this round's numbers, and **two findings retired**:
  "`TickArrayBook` is the slowest rung at `occupied_levels(depth=10)`" (retired by B) and "the
  gap statistics are where the bitmap books earn their keep" (retired by C). Plus the crossover
  of Part 4, which is the finding most likely to be re-derived by someone who has not measured
  it.

## Tests

- `tests/lob/test_aggregate_book.py` — `for_prices` on a stream with both sentinels gives the
  same band as one with them stripped; `for_prices([p, sys.maxsize])` no longer raises
  `MemoryError`; a level at price 0 far from the rest raises "outside the band". The three new
  gap statistics each agree with their own `empty_grid_positions`-based method, on: a contiguous
  side (distances NaN, sizes 0), one gap, two equal-length gaps where the tie-break must pick
  the nearer, a larger gap behind a nearer one, a single level, an empty side, and a hole beyond
  the deepest reported level — which is *not* a gap and must not be counted.
- `tests/lob/test_axis_b_variants.py` — `side_statistics` from the levels list against a direct
  reference (not against the other implementation, or the two drift together) over many random
  books on all five rungs; `queue_imbalance_profile` against `queue_imbalance(n)` term by term,
  including a window running off the band edge; ask levels at `origin` and `origin + width - 1`
  on a directly constructed `TickArrayBook`, checked against `AggregateBook.from_levels`, which
  is the only thing that pins the ceiling; and `copy()` of such a book.
- `tests/lob/test_gap_statistics.py` — keep `TestCaseB`'s literal `gap_count == 1`. It is the
  only test that catches the shared-helper failure under B.
- `tests/lob/test_market_session.py` — a full frame-**content** comparison, not a length
  assertion, at 1 023 / 1 024 / 1 025 / 2 049 rows against the same fold recorded row by row, on
  a book with a padded side; the buffer-boundary test extended to pass a **generator** as well
  as a list; `write_lobster_row` twice into one index with a shallower book second; and the
  equal-length tie-break added to the worked example so the two statistics routes are pinned to
  the same choice rather than agreeing by luck.
- `test_writing_in_place_matches_building_a_row` stays on `np.zeros` and is extended to the new
  `SideStatistics.levels` path.

## Verification

```bash
/home/claudio/anaconda3/envs/unito26/bin/python -m pytest tests/ -q     # 15436 + new
```

Then execute both notebooks in the `unito26` env. Strip outputs before staging.

## Not doing

The sixth rung (Part 4). Mirroring `BitmapBook` — it has no ceiling by design, and that is the
point of the rung. Shifting the band as the price drifts. Overriding `submit` on the fast rungs
— matching is written once in `AggregateBook` and inherited unchanged, which is what lets the
ladder measure one thing.
