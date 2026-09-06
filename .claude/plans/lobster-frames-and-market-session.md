# Rigid schemas, gap statistics, and the market session

## Context

The `lob` strand (L0–L3 plus the performance ladder) is built and tested, but a review of it
found four things to change and two to add.

*Change.* Model parameters (`MarkParams`, `HawkesParams`) and the book itself have no
serialized form, so a parametrization can only be passed around as live Python. Worse,
`default_flow_params()` *computes* a parameter set at call time and calls it a default — it
is an example of a parametrization, and naming it a default teaches students to skip the
choice. The order-flow simulator still carries a submission-only mode, and the package uses
keyword-only markers and defaults on parameters that change what a function means.

*Add.* The aggregate book should report how its occupied levels are distributed — how many,
where the holes are, how big the largest one is. These are the statistics that make the
performance ladder pay off a second time: the dict books sort keys, the bitmap books read
the answer off an integer, using the vocabulary already drafted in `binary_gaps.py` and
derived in `documentation/integers-in-binary.md`. And a replay should produce a
**`MarketSession`** — a LOBSTER-shaped frame plus those statistics — reachable by several
routes that must agree: message-by-message from the evolving book against vectorized over
the finished frame, and three recording strategies against each other. Tests that they
agree, and a notebook that runs the whole pipeline — parametrization on disk, synthetic
order flow, queues evolving, statistics read off them — and times the routes against each
other.

*Outcome.* Every parameter object and every book state round-trips through a schema-checked
DataFrame; the examples ship as frozen JSON rather than as code that runs; the session is a
named structure instead of a stream of tuples; and the truncation that makes a real LOBSTER
file hard is visible in our own frames rather than hidden.

## Decisions taken

- **pandera** is the schema tool, verified working against the installed pandas 3.0.5 on
  py3.14 (0.33.0 from pip, 0.32.1 from conda-forge, which declares `pandas >=2.1.1` with no
  ceiling, so no downgrade). It reaches `pydantic` → `pydantic_core`, a compiled Rust
  extension — cheap, wheels exist, but not the pure-Python dependency first claimed. The
  schemas live in a new `unito26/lob/frames.py`, not on the model classes. Pandera takes the
  alias `pa`; **pyarrow is imported unaliased** — the two currently collide in `replay.py`.
- **Occupied levels, not grid positions**, in the serialized frame. That is what a real
  LOBSTER file holds, and it is what makes the price columns carry the gap information:
  the gap between ask levels `k` and `k+1` is `(AskPrice_{k+1} − AskPrice_k)/τ − 1`. The
  notes' §3 grid convention stays on `levels()`; the new `occupied_levels()` is the other
  one, and the two are named at the boundary — see the next section, which is the crux of
  this change.
- **CamelCase column names** everywhere: `TimeStamp`, `AskPrice1`, `AskSize1`, `BidPrice1`,
  `BidSize1`, `Component`, `Cause`, `BaseIntensity`, `Kernel`, `Decay`. Column names are
  schema keys, deliberately distinct from Python identifiers.

## How the code is written

Applies to every step below, and to the notebook.

**Few comments.** A comment earns its place only when it is *essential* to understanding
the code and will still be true and useful to someone meeting the file cold in a year.
Everything else is noise that ages badly: restating what the line does, narrating a
decision, defending a rejected alternative, marking what changed. The code says what it
does; a comment is for what the code cannot say — an invariant, a sign convention, a
non-obvious "why this and not the obvious thing".

Concretely, in this work: the grid-versus-reported distinction, the sign of `I^n`, the
fact that a fill trades at the resting price, the coverage condition, and why
`occupied_levels(direction, 1)` must not sort — those are worth a line each. A named
function with well-chosen arguments needs nothing further. Prefer making the code
self-evident to explaining code that is not.

The existing `lob` modules are written at a much higher comment density than this. Do not
match it; new code follows the rule above, and existing prose is left alone unless it is
wrong.

## The two indexings, and why they must never share a name

**Confirmed, and it is the premise of everything below: `I^n` is defined on the grid.** §4
defines it through `V^{b,i}` and `V^{a,i}`, and §3 defines those as the volumes at the grid
prices `P^{b,i} = P^b − (i−1)τ` and `P^{a,i} = P^a + (i−1)τ` — positions on the price
ladder, occupied or not, with `V^{·,i} = 0` where nothing rests. So `I^n` sums volume over
the **first `n` grid positions** from each touch — which spans `n − 1` ticks, not `n`; the
file that exists to fix this vocabulary must not itself say "within n ticks". The `.tex` in
`documentation/tex/notes/orderdriven/` is the authority and it is unambiguous; the code
follows it and does not acquire a second meaning of depth by the back door.

**And confirmed: under LOBSTER's representation this is exactly what stops being
straightforward, because of gaps.** A LOBSTER file indexes by **occupied level** —
`BidPrice2` is the second price *carrying volume*, however far below the touch that is. The
two indexings coincide only when the book has no holes; a single empty queue inside the
window shifts every column relative to its grid position, and from then on the *k*-th column
and the *k*-th grid level are different prices. Summing sizes by column then computes a
different statistic and reports it under the same name — and there is no error, no NaN and
no shape mismatch to catch it. The gaps are precisely the difficulty, they are common on
small-tick instruments, and the whole apparatus below (`occupied_levels`, `grid_span`, the
price mask, the coverage column) exists to handle them.

**The worked case.** τ = 1; asks occupied at 101, 102, 103, 104, 105; bids occupied at 99
and 90 and nowhere between. A frame of reported depth 2 holds

```
AskPrice1=101 AskPrice2=102        BidPrice1=99 BidPrice2=90
```

`I²` sums the bid over the grid window `{99, 98}`, and 98 is empty, so the bid contributes
`V(99)` alone. Summing by **column index** instead contributes `V(99) + V(90)` — two prices
nine ticks apart, presented as a top-of-book signal.

**Recovery is by price, never by column.** The window is
`[BidPrice1 − (n−1)τ, BidPrice1]`, and the vectorized form masks reported levels into it:

```
bid_total(n) = Σ_k BidSize_k · 1{BidPrice_k ≥ BidPrice1 − (n−1)τ}
```

which selects 99 and drops 90. The ask form is the mirror, with `≤ AskPrice1 + (n−1)τ`.

**Coverage is per side, and data-dependent.** Write the grid span of a side as
`|Price_1 − Price_L|/τ + 1`, where `L = min(D, occupied levels on that side)` — using `D`
directly is NaN whenever the side is padded. In the case above the bid span is
`(99−90)+1 = 10` and the ask span is `(102−101)+1 = 2`. So the depth-2 frame answers `I²`
exactly and **cannot answer `I³`** — not for want of bid depth, which has room to spare,
but because the ask ran out at 102. A file's reported depth is therefore not a bound on the
grid depth it can answer; the relation moves row by row as the book breathes.

Three precisions, each of which the plan had wrong:

- **The condition is sufficient, not necessary.** Bids occupied at 100, 99 and 95 with
  `D = 2` give `grid_span = 2`, so the rule calls `I³` uncovered — yet the masked sum equals
  the true grid sum, because the unreported level at 95 lies *below* the window. It first
  genuinely fails at `n = 6`. State it as sufficient, and justify it as **the tightest rule
  decidable from the frame**: at `n = grid_span + 1` the frame is consistent both with a
  level at `Price_L − τ` and with a gap there, so no frame-only rule can do better. That is
  the stronger claim as well as the true one, and a student can build the counterexample in
  two lines.
- **The quantifier is per side, then conjoined.** For *each* side independently:
  `n ≤ grid_span` **or** that side is fully reported. Coverage is the AND over the two. As
  the plan first stated it, one short side excused the other.
- **An empty side is covered**, contributing 0 at every `n`. The NaN price mask happens to
  give that answer by accident of NaN comparison — state the convention rather than lean on
  the accident.

**Consequences carried through the whole plan:**

- **Two parameter names and two types, never reused.** `n` counts grid levels — it is the
  `n` of `I^n`, and `queue_imbalance(n)` keeps it. `reported_depth` counts occupied levels
  and is what the frame, `occupied_levels` and every gap statistic take. A new
  `grid_span(direction, reported_depth)` is the bridge.

  Names alone are not enough once `*` is banned: `from_occupied_levels(book, messages,
  reported_depth, imbalance_levels, price_unit)` has three adjacent ints, and a positional
  call discards exactly the names the distinction rests on. So the two depths are distinct
  types — `GridDepth = NewType("GridDepth", int)` and
  `ReportedDepth = NewType("ReportedDepth", int)`, one line each in `messages.py`. A
  swapped pair is then visible to a reader at the call site and to a type checker, with no
  keyword-only marker anywhere.
- **The two stat routes do not claim total equality.** Route 1 holds the whole book and
  computes the true `I^n`. Route 2 computes it from the frame and writes NaN where the
  window is not covered, beside a `QueueImbalanceCovered` column. The reconciliation test
  asserts exact equality on covered rows and NaN on the rest.
- **Gap statistics run the other way**: they are defined on the reported span, so they take
  `reported_depth` and reconcile with no coverage caveat. Two statistics on one class
  taking two different meanings of "depth" is precisely the trap, hence the naming rule.
- **A documentation file**, below, since this is the invariant the session rests on.

## Step 0 — unblock

Nothing in the package imports today. The breakage is wider than one file.

1. `unito26/lob/hawkes.py:41` — `import panders.pandas as pa` → `pandera.pandas`.
2. `unito26/lob/replay.py:66` — `SyntaxError: '(' was never closed`: the
   `pa.DataFrameSchema({...}` call is unterminated, so everything after it is a paren
   continuation rather than the indentation nesting it looks like. The file also uses
   `dataclass`, `pd`, `np` and `pa` without importing any of them. Rewritten wholesale in
   step 4.
3. `unito26/lob/benchmark.py:38-40` — `SHALLOW = MarkParams(depth_decay=0.45)` and
   `DEEP = MarkParams(depth_decay=0.02)` at module scope, but `MarkParams` lost its defaults
   in the working copy; and `session()` at `:64` calls `OrderFlowSimulator(rng=seed,
   marks=marks)` with neither `params` nor `reference_price`. Step 7 reuses this module, so
   it is on the critical path. `SHALLOW`/`DEEP` move to `config.py` beside the other frozen
   examples.
4. `unito26.yml` — add `pandera` under the conda-forge dependencies, pinned `>=0.32`.
   conda-forge's newest is 0.32.1 and pip has 0.33.0; both work here, and conda-forge
   declares `pandas >=2.1.1` with no ceiling, so there is no pandas downgrade. Correction to
   the decision above: the dependency is **not** pure Python — pandera pulls `pydantic`,
   whose `pydantic_core` is a compiled Rust extension. Still cheap and wheels exist for
   py3.14, but say what it is.
5. Delete the stray `unito26/lob/.replay.py.swp`.

## Step 1 — the style sweep

**`*` in signatures.** Two sites: `messages.py:147` `TickGrid.to_ticks(self, price, *,
tolerance=1e-9)` and `simulate.py` `OrderFlowSimulator.__init__`. Remove both markers.
`tolerance` becomes a module constant `TICK_TOLERANCE = 1e-9` in `messages.py` — it is not
a per-call choice.

**Default arguments.** Keep a default only where the parameter is genuinely superfluous.
The surviving cases are the `rng` on `_HawkesState` and `OrderFlowSimulator`, where a
caller may or may not want to control the seed. Made required:

| site | was |
| --- | --- |
| `AggregateBook.queue_imbalance` | `depth=1` |
| `BitmapBook.__init__` | `origin=0` |
| `TickArrayBook.__init__` | `origin=0, width=4096` |
| `lobster.load_orderbook` | `depth=10` |
| `lobster.describe_orderbook` | `tick=100` |
| `benchmark.session`, `time_variants` | `horizon`, `seed`, `repeat` |

`strict=False` **stays**: replaying a feed is the overwhelmingly common case, and the few
tests wanting strictness say so explicitly.

**Removing the `origin`/`width` defaults breaks `from_levels`**, which does `book = cls()`
(`orderbook.py:402`) — and every `AXIS_B_VARIANTS`-parametrized path runs through it:
`worked_examples.check:235`, `test_axis_b_variants.py:99,130`, and the plan's own new
round-trip test. `from_levels` must size the band from the prices it was given, the way
`for_prices` already does. Same problem for `from_lobster_frame`: as a `@staticmethod` it
cannot construct the variant class at all, so it becomes a `classmethod` and sizes the band
from the frame's own prices — `TickArrayBook.set_volume` raises outside the band (`:729`).

**Call sites the sweep breaks, all currently unlisted.** `OrderFlowSimulator` is constructed
seven times with partial arguments: `test_axis_b_variants.py:33` (a module-scoped fixture,
so it takes down every variant test), `test_replay_and_simulate.py:75,100,109,121,136`, and
`benchmark.py:64`. `notebooks/aggregate-book.ipynb` calls `MarkParams(depth_decay=0.01)`,
`session(...)` without `seed` and `time_variants(...)` without `repeat`. All are in scope.

**Submission-only mode.** Delete `SUBMISSION_TYPES` from `simulate.py` and the
`test_submissions_only_mode_emits_no_withdrawals` test. Update the ladder description in
`dev-context/market-microstructure.md`, where L0–L2 are still described as submission-only.

**`MarkParams`.** The round-lot mixture (`round_lot_probability`, `round_lots`) is already
gone from the working copy; `_size` is now the lognormal draw alone, rounded to `lot`.
Nothing further — this item is verified, not outstanding.

**`CLAUDE.md`.** A new *Python style* subsection under Conventions recording:

- **Few comments.** Only where essential to understand the code, and only where the comment
  will still be true and useful to someone meeting the file cold in a year. No restating
  what a line does, no narrating a decision, no defending a rejected alternative, no marking
  what changed. The code says what it does; a comment is for what it cannot say.
- No `*` in a signature.
- Defaults only for genuinely superfluous parameters.
- A serialized type carries a pandera schema plus `to_frame`/`from_frame` and a round-trip
  test.
- Model parametrizations ship as frozen serialized examples, never as code that computes a
  "default".

## Step 2 — serialization

**The schemas live in a new `unito26/lob/frames.py`**, not on the classes they describe.
`orderbook.py` is the file a student reads to learn the book; hanging a schema library off
it — and `pandera` reaches `pydantic_core`, a compiled extension — buys nothing for the
notation-following class and costs its readability. `frames.py` holds every
`DataFrameSchema` and every `to_frame`/`from_frame` pair, and imports the model classes.

The pattern is identical in all three cases: a `get_schema(...)` returning a
`pa.DataFrameSchema`, a `to_frame(obj)` that builds and validates, a `from_frame(df)` that
validates and reconstructs. Verified pandera behaviour to build against:

- Checks are handed **the whole Series**, not elements. `pa.Check(lambda p: 0. < p < 1.)`
  raises *truth value of a Series is ambiguous*; `lambda v: v >= 0` happens to work, since
  it returns a boolean Series. Prefer `pa.Check.ge` / `pa.Check.in_range` (which takes
  `include_min`/`include_max`, so open bounds are expressible) — but the plan's stated
  reason over-generalises, and only the chained comparison actually breaks.
- `nullable=True` plus a check that would fail on NaN **passes**: pandera drops nulls before
  running checks. So `BaseIntensity` with NaN off-diagonal and `Check.ge(0)` is fine.
- **Nullable integer columns need `Int64` and `coerce=True`.** `pa.Column(int,
  nullable=True)` against a padded price column fails — *expected int64, got float64* —
  because a numpy int64 cannot hold a null, and `pd.DataFrame` built from tuples containing
  `None` yields `float64`, not the masked `Int64`. Worse, the dtype is data-dependent: a
  session that never pads gives `int64` and one that pads gives `float64`, and the same
  schema must accept both. Only explicit `Int64` + `coerce=True` does.
- **`pd.read_json` no longer accepts a literal string** on pandas 3.0.5 — it treats it as a
  path and raises `FileNotFoundError`. The frozen config constants must go through
  `io.StringIO`.

**`MarkParams`** (`simulate.py`) — one row: `DepthDecay` in `(0,1)`, `MeanLogSize`,
`SigmaLogSize > 0`, `Lot` (int, `≥ 1`; the drafted schema types it float).

**`HawkesParams`** (`hawkes.py`) — `d²` rows in long form, `MultiIndex(Component, Cause)`
reset to columns. `Kernel` is `excitation[i, j]` flattened; `BaseIntensity` carries
`baseline[i]` on the diagonal and **NaN off it**, so that column is `nullable=True` — the
`TODO` at `hawkes.py:143` is exactly this. `Decay` repeats; `from_frame` asserts it is
single-valued, asserts the `(Component, Cause)` grid is complete and square, and rebuilds
`baseline` from the diagonal.

The drafted orientation is **correct** — `from_product([components, cause])` with a C-order
`flatten()` does put `excitation[i, j]` on row `(Component=i, Cause=j)`, matching "row is
excited, column is exciting". But the obvious tests cannot see a transpose, so:

- `from_frame` must **pivot on `(Component, Cause)`**, never `reshape(d, d)` in row order.
  A shuffled frame reshapes to `[[4,2],[1,3]]` where the pivot gives `[[1,2],[3,4]]`, and no
  schema can constrain row order — so the round-trip test **shuffles the frame before
  `from_frame`**, or it certifies nothing.
- The round-trip fixture must be **asymmetric with four distinct entries** and `d ≥ 2`. A
  symmetric matrix round-trips under transposition; and at `d = 1` there are no off-diagonal
  rows, so the NaN convention and `nullable=True` are never exercised.
- Add one direct assertion, `frame.loc[(i, j), 'Kernel'] == excitation[i, j]` for `i ≠ j` —
  the only test that pins the encoding itself rather than the round trip.
- A branching-ratio test would *not* catch a transpose (the spectral radius is
  transpose-invariant, confirmed: 0.8 either way). The example's asymmetry assertion does
  catch it — `A[LIMIT_BUY, MARKET_BUY]/A[MARKET_BUY, LIMIT_BUY] = 20`, which inverts to
  1/20 under transposition — provided it reads `params.excitation` *after* `from_frame`
  rather than reading the frame.

`DepthDecay`'s domain is `(0, 1]`, not `(0, 1)`: `p = 1` means every order at the touch,
which is a legitimate parametrization and is accepted by `rng.geometric`.

**`AggregateBook`** (`orderbook.py`) — `get_frame_schema(reported_depth)` currently iterates
`for level in depth` and hard-codes `AskSize1` inside the loop; rewrite as
`AskPrice{k}/AskSize{k}/BidPrice{k}/BidSize{k}` for `k` in `1..reported_depth`. The
parameter is named `reported_depth` here and everywhere below, per the naming rule.

**The format is fixed by `data/lobster/LOBSTER_SampleFiles_ReadMe.txt`, which is in the
repo. Read it rather than reasoning about it.** It settles four things the plan had wrong
or unstated:

- *Padding is asymmetric.* "The extra bid and/or ask prices are set to **-9999999999 and
  9999999999**, respectively. The Corresponding volumes are set to **0**." Not NaN, and not
  one sentinel. So the size columns are **not nullable**, and a normaliser written as
  `replace(-9999999999, nan)` leaves every padded ask holding a price of 999,999.9999. Both
  sentinels are normalised per side, and the round-trip test covers a padded row on *each*
  side separately — a symmetric test passes with the ask half broken.
- *"The term level refers to occupied price levels. This implies that the difference between
  two levels in the LOBSTER output is not necessarily the minimum tick size."* This one
  sentence is the whole justification for the occupied-level decision; quote it in the
  documentation instead of arguing the point.
- *There is no time column.* The orderbook file is `N × (4 × levels)` beginning at
  `AskPrice1`; time lives in the row-aligned message file. So `lobster_book` carries
  **exactly `4 × reported_depth` columns and no `TimeStamp`** — the working copy's schema
  prepends one. Time becomes the frame's index, shared with `stats`. Without this the
  "comparison is equality rather than translation" claim is false, since a shipped file
  would not validate against our schema.
- *Halt rows duplicate the preceding state.* A type-7 message carries price `-1`, `0` or
  `1` with direction `-1`, and its orderbook row is a copy, not a computation. Replaying one
  as an order submits at price `-1`.

`to_lobster_frame(self, price_unit, reported_depth)` — note the missing `self` in the stub —
emits one row of the **occupied** top levels; `from_lobster_frame(df, price_unit)` is its
inverse and goes through `set_volume`, so a variant carrying an index is correctly
initialised, and it asserts `price % price_unit == 0` rather than dividing.

**`price_unit`, not `tick_size`.** LOBSTER prices are dollars × 10000, so a penny tick is
the integer `100`. But `TickGrid.tick_size` (`messages.py`) is a *currency float*, `0.01`.
Two units under one name, in one package, silently producing off-grid float prices when
crossed — exactly the failure the depth section exists to prevent, and the plan reproduced
it. The boundary parameter is `price_unit: int`.

Needs two new primitives on `AggregateBook`, beside the grid-based `levels()`:

```
occupied_levels(direction, reported_depth) -> list[tuple[int, int]]  # (price, volume), best first
grid_span(direction, reported_depth) -> int    # grid ticks those levels span, inclusive
```

**These must be written against `best_price` and `volume_at`, never against `levels_map`.**
The module's own rule (`orderbook.py:102-107`) is that derived quantities go through the
four storage primitives and nothing else, and here it is load-bearing rather than stylistic:
`levels_map` bypasses `CachedBestBook`'s cache and `HeapBook`'s heap entirely, and on
`TickArrayBook` it *builds a fresh dict by walking every occupancy bit* (`:749-764`) — so
the plan's first phrasing, "sort the keys of `levels_map`", would turn a per-message
top-of-book read into an O(L) dict construction on the fastest rung and quietly flatten the
very axis the notebook is measuring. `occupied_levels(d, 1)` is `best_price` plus one
`volume_at`; deeper reads walk down from the touch, and the variants override as they
already do. Where a genuine sort is wanted, `heapq.nsmallest`/`nlargest` is O(L log D)
against `sorted`'s O(L log L) — and a full sort per message on a deep book would swamp the
timing grid.

`grid_span` is the coverage bridge of the section above, with the three precisions stated
there: it uses `L = min(reported_depth, occupied levels)`, the condition is per side and
then conjoined, and it is sufficient rather than necessary.

**Config examples** (`unito26/lob/config.py`). `default_flow_params()` is deleted. Its
output is generated once and frozen as a JSON string constant, alongside a mark-parameter
example:

```
EXAMPLE_ORDER_FLOW_PARAMS: str   # HawkesParams.to_frame().to_json()
EXAMPLE_MARK_PARAMS: str         # MarkParams.to_frame().to_json()

def example_order_flow_params() -> HawkesParams
def example_mark_params() -> MarkParams
```

Loaders live here, so `config` imports `hawkes` and `simulate` and never the reverse. The
module docstring keeps the *rationale* that the deleted function carried — the three
empirical asymmetries (market orders replenish limit flow strongly, the reverse barely at
all, market buys pull sell-side quotes), and that the matrix was written for its shape and
rescaled to a branching ratio of 0.8 — since the code that expressed it is gone. A test
asserts those properties of the loaded example, so they survive the deletion.

**JSON demotes dtypes on the way back.** On the installed pandas 3.0.5, `to_json` writes
`60.0` but `read_json` returns `Decay` and `Kernel` as **int64** whenever every value is
whole — so the reloaded frame fails `pa.Column(float)`, and re-serializing emits `60`, which
breaks a byte-for-byte comparison for no substantive reason. The loader casts the numeric
columns to float, and the stability test compares the frozen constant against `to_json()` of
the *reconstructed params*, not of the re-read frame. NaN → `null` → NaN does survive
intact, so the off-diagonal convention is safe.

## Step 3 — the gap statistics

`binary_gaps.py` first, since the book methods are written in its vocabulary. It has no
tests and **three** defects, all confirmed by brute force against a string reference over
`n = 1 … 19999`:

1. `count_trailing_zeros(0)` does not terminate.
2. `measure_largest_binary_gap` counts trailing zeros as a gap — `0b100` returns 2 where
   there is no gap between ones — so it requires a normalised input. On normalised input it
   is exactly correct on all 19 999.
3. **`count_binary_gaps` is simply wrong: 9 923 failures.** `count_binary_gaps(0b1001)`
   returns 2 where the answer is 1. The `n >> 1` inside the loop, combined with
   `discard_trailing_zeros(discard_trailing_ones(...))` in that order, splits one gap of
   length ≥ 2 into two counts. The correct loop drops the shift and swaps the order:
   `n = dto(dtz(n))` before the loop and again at the end of each pass — verified, 0
   failures. This matters beyond the module: `BidGapCount`/`AskGapCount` on `BitmapBook` and
   `TickArrayBook` are built on it, so without the fix the axis-B agreement test fails.

Fix the guards, correct the docstrings to say what each function *requires* of its input,
add a module docstring pointing at `documentation/integers-in-binary.md`, and add
`tests/lob/test_binary_gaps.py`. Note the module has five functions, not four —
`count_binary_gaps` was unlisted.

Then on `AggregateBook`, replacing the two `NotImplementedError` stubs — both currently
missing `self` — defined over the price range spanned by the first `reported_depth`
occupied levels:

```
occupied_level_count(direction, reported_depth) -> int
empty_grid_positions(direction, reported_depth) -> list[int]   # the holes, by grid index
largest_gap_size_between_non_empty_levels(direction, reported_depth) -> int
gap_count(direction, reported_depth) -> int                    # maximal runs of holes
```

The stub's name `gaps_between_non_empty_levels` becomes `empty_grid_positions`, because
`gap_count` is **not** its length: the list holds hole *positions* and `gap_count` counts
maximal *runs* of them. Two near-synonymous names where one is not the length of the other
is a trap worth removing rather than documenting.

The returned indices are **grid** indices, 1-indexed from the best price on that side per
§3 — the one place the two indexings meet, and worth a sentence of docstring. The stub's
example is bids at prices 100, 99, 97, 96, 93; at `reported_depth = 5` it gives holes
`[3, 6, 7]`, largest gap 2, gap count 2, `grid_span = 8`. Note the stub writes its pairs as
`(25, 100)` — that is `(volume, price)`, the reverse of `occupied_levels`' `(price,
volume)`. Whoever writes the test will get it backwards once; fix the stub's comment.

The ladder is the point:

- `AggregateBook` — sort the keys of `levels_map`, walk consecutive prices. O(L log L),
  and unavoidable here: a gap statistic genuinely needs the span in order. That is why
  `occupied_levels(direction, 1)` must take the separate `min`/`max` path of axis C rather
  than share this one.
- `CachedBestBook`, `HeapBook` — inherit unchanged; neither index helps here, and saying so
  is part of the lesson.
- `BitmapBook`, `TickArrayBook` — the occupancy integer *is* the answer. Mask to the span,
  `bit_count()` for the count, `measure_largest_binary_gap` for the largest, and the set
  bits of `~bits & span_mask` for the hole indices. The bid side reads downward from the
  top bit and the ask side upward from `bits & -bits`, which is the same asymmetry
  `best_price` already has.

Also fix `queue_imbalance`: it keeps the parameter name `n` and stays defined on the grid,
per §4; it returns `float("nan")` when both sides are empty over the requested `n` rather
than raising (`orderbook.py:247`); and `TickArrayBook` overrides it to read the volume
array directly.

**Its bounds are strict, and worth asserting as such.** For `n ≥ 1` with both sides
non-empty, `V^{b,1} > 0` *and* `V^{a,1} > 0` — which rests on `set_volume`'s invariant that
a price whose queue empties is removed (`orderbook.py:122`), not on the definition of the
best bid alone; the one-sided argument proves only `I^n > −1`. So both window sums are
positive and `I^n` lies *strictly* inside `(−1, +1)`. `I^n = ±1` iff exactly one side is
empty; `NaN` iff both are. Sharper than the `[−1, 1]` the implementation notes state, and
it is the property test.

The trichotomy needs `n ≥ 1`: at `n = 0` both windows are empty under the notes'
`V^{·,j} = 0, j ≤ 0` convention, so `I^0` is `NaN` on a perfectly healthy book. Reject
`n ≤ 0` rather than returning that.

## Step 3b — the micro-price

`micro_price` is in the symbol table and unimplemented. Writing out the crossed-weight
definition — the ask price carries the *bid* volume, which is its own exam snippet —

```
P^mu = (P^a V^b + P^b V^a) / (V^a + V^b)
     = P^m + (phi/2) * I^1
```

so it is one line on `AggregateBook` given `queue_imbalance(1)`. Implement it as the
identity and test it against the direct formula on the §8 fixture and on random books —
with `pytest.approx`, not `==`: the identity is exact over the rationals but the two
expressions disagree in the last bit on roughly 3 books in 1000, worst relative gap 6e-16,
and insisting they not share code is precisely what exposes that.

**The correct micro-price sits toward the *thin* side.** With `P^a = 102`, `P^b = 100`,
`V^b = 900`, `V^a = 100`, `P^μ = 101.8 > P^m = 101` — bid-heavy pushes it up toward the ask.
So an inverted imbalance drags it toward the *heavy* side, below the mid on a bid-heavy
book, and that is the check. `micro_price` is `NaN` when either side is empty, like `spread`
and `mid_price`.

`MicroPrice` joins the session's statistics, from the touch alone on the vectorized route,
so it is recoverable from any frame whose first level is not padded.

## Step 4 — `MarketSession`

`replay.py` is rewritten. `run()` stays as the benchmark path. The `Tap` protocol goes —
a callable returning `Any` is the "arbitrary tuple" the review objected to — but the
*flavours* of replay it carried survive, promoted to named constructors on `MarketSession`.
`book_copy` and `snapshots_to_table` go; the aliasing lesson `book_copy` carried moves to a
comment on `AggregateBook.copy`.

```python
@dataclass(eq=False)   # DataFrame fields make the generated __eq__ raise
class MarketSession:
    reported_depth: int                 # occupied levels held per side, LOBSTER's depth
    imbalance_levels: tuple[int, ...]   # the n of I^n, counted on the grid; one column each
    price_unit: int                     # LOBSTER price units per tick
    from_file: bool                     # provenance: see the coverage caveat below
    lobster_book: pd.DataFrame          # 4 x reported_depth columns, time on the index
    stats: pd.DataFrame                 # same index, one column per statistic
    level_deltas: list[tuple[int, float, LevelDelta]] | None   # (seq, time, delta)

    def stats_from_frame(self) -> pd.DataFrame
```

plus the three named constructors below, which are the ways to fill it. The schemas —
`lobster_book_schema(reported_depth)` and `stats_schema(imbalance_levels)`, the latter
needing the family to name its columns — live in `frames.py` with the others.

`level_deltas` must carry the sequence and time, not bare `LevelDelta`s: a `LevelDelta`
holds only `(side, price, volume)`, so a flat list loses the message boundaries entirely.
Nor can the boundaries be recovered by counting, because a message can produce **zero**
deltas — `withdraw` returns a bare `SubmitResult()` when nothing was resting
(`orderbook.py:369`). This is the shape `deltas_to_table` already consumes.

The two depths are separate fields precisely because they are separate quantities — the
section on indexings made structural rather than merely documented.

Each constructor is a fold: apply each message, append the book's own `to_lobster_frame`
row, and read the statistics off the evolving book. Rows accumulate as lists of tuples and
become a DataFrame once, at the end — building a frame incrementally reallocates on every
message and would dominate the timing the notebook is trying to measure.

`stats_from_frame` recomputes the same columns from `self.lobster_book` alone, vectorized,
touching no book:

| column | from the book (route 1) | from the frame (route 2) |
| --- | --- | --- |
| `Spread` | `book.spread` | `(AskPrice1 − BidPrice1) / price_unit` |
| `MidPrice` | `book.mid_price` | `(AskPrice1 + BidPrice1) / (2·price_unit)` |
| `MicroPrice` | `book.micro_price` | `(AskPrice1·BidSize1 + BidPrice1·AskSize1)/((AskSize1 + BidSize1)·price_unit)` |
| `QueueImbalance{n}` | `book.queue_imbalance(n)` | price-masked into the grid window, NaN where uncovered |
| `QueueImbalance{n}Covered` | `n ≤ grid_span` both sides | the same test, on the price columns |
| `BidOccupiedLevels`, `AskOccupiedLevels` | `occupied_level_count` | price columns that are not the sentinel |
| `BidGapCount`, `AskGapCount` | `gap_count` | runs in `−diff(BidPrice)/τ − 1`, `+diff(AskPrice)/τ − 1` |
| `BidLargestGap`, `AskLargestGap` | `largest_gap_size_…` | `max` of the same |

One `QueueImbalance{n}` / `QueueImbalance{n}Covered` pair per entry of `imbalance_levels`,
so a session carries the whole family and the notebook can show the signal *and* its
recoverability degrading together as `n` grows. `stats_schema()` takes `imbalance_levels`
to name them.

**Four ways this table goes wrong, each of which returns a plausible number:**

1. **Units.** `AggregateBook.spread` and `mid_price` are documented *in ticks*
   (`orderbook.py:222,228`), while the frame holds LOBSTER price units. The three price
   statistics therefore differ between the routes by a factor of `price_unit` — and only
   those three, since the imbalance is unit-free and the gap columns already divide by τ.
   Statistics are stated **in ticks**, route 2 divides. The reconciliation test runs at
   `price_unit = 100`, never at 1, because at 1 the bug is invisible.
2. **The bid `diff` runs downward.** Bid prices descend with level, so a single formula for
   both sides makes every bid gap negative. The bid takes `−diff`. This is the same
   asymmetry `best_price` and the bitmap walk already carry, and the plan stated it for the
   bitmap and forgot it here.
3. **`skipna=True` is the pandas default**, so `df[size_cols].sum(axis=1)` over a window
   containing NaN quietly sums as though the missing level were absent. Route 2's whole
   correctness rests on NaN *propagating*. Mask explicitly, or pass `min_count`.
4. **`None` is not `NaN`.** Route 1's `spread`, `mid_price` and `micro_price` return Python
   `None` on an empty side; a column built from those is object dtype, fails
   `pa.Column(float)`, and never compares equal to route 2's NaN. Normalise at the fold.

The imbalance columns are the only row-dependent case: route 1 reads the whole book we
simulated and always answers, route 2 answers only where the reported levels span the grid
window. The mask goes in its own column rather than being inferred from the NaNs, so a study
can count how much of a session it lost and to which side. `MicroPrice` needs only the touch
and so is always recoverable. Every other column reconciles unconditionally, because both
routes read the same `reported_depth` occupied levels.

**Route 1 is not "the truth".** On a real feed both routes give the *visible* imbalance;
hidden liquidity (LOBSTER type 5, already documented in `lobster.py`) means neither is the
book. Route 1 is "computed from the whole book we simulated", and the docstrings say so —
teaching that a reconstructed book is ground truth is the most expensive misconception in
this area.

**The sentinels interact with this table.** The price mask rejects `-9999999999` on the bid
and `9999999999` on the ask automatically, so the imbalance survives padded rows untouched.
Nothing else does: `AskPrice1 − BidPrice1` on a row padded at level 1 gives ≈2×10¹⁰, and a
largest-gap on a padded row gives ≈10⁸ ticks. **`lobster.describe_orderbook` has this bug
live today** (`lobster.py:133–145` computes spread and imbalance with no sentinel filter);
step 1 already edits that function, so fix it there.

**The vectorized masking is the part to get right**, and it is `≥ BidPrice1 − (n−1)τ` on
the bid and `≤ AskPrice1 + (n−1)τ` on the ask — never `.iloc[:, :n]`. Column slicing is the
bug the whole section above exists to prevent, and it belongs in the exam snippets.

### Axis C: the recording strategy

Three named constructors, three ways to build **the same** session, orthogonal to which
rung of the book ladder sits underneath — so the ladder pays off a third time, and "which
is faster" again has a conditional answer rather than a ranking:

```python
@classmethod
def from_top_of_book(cls, book, messages, imbalance_levels, tick_size)
@classmethod
def from_occupied_levels(cls, book, messages, reported_depth, imbalance_levels, tick_size)
@classmethod
def from_level_deltas(cls, book, messages, reported_depth, imbalance_levels, tick_size)
```

- `from_top_of_book` reads the four touch properties per message and yields a
  `reported_depth = 1` session. **It must produce a session equal to
  `from_occupied_levels(..., reported_depth=1, ...)`** — same frame, same statistics. That
  equality is not an accident and is worth one line of docstring: `set_volume` pops a level
  whose volume reaches zero (`orderbook.py:130-134`), so the best price is *always* an
  occupied price and grid level 1 always coincides with occupied level 1. The empty-side
  case agrees only under the stated padding convention (sentinel price, size 0), since
  `bid_volume(1)` returns 0 when `bid_price(1)` is `None`.
- `from_occupied_levels` is the general dense route described above.
- `from_level_deltas` records only `result.deltas` and densifies once at the end. Equal
  again — which turns the storage saving into a claim about *equivalence*, not just size.
  Two corrections to how the plan first described it: `deltas_to_table` is the sparse
  *serializer*, not a densifier, so densification is a second fold to write; and because a
  delta records only levels a message *changed*, the reconstruction is relative to the book
  state at the start of the replay. On the warmed-up book the session actually uses, the
  deltas alone do not determine the frame — **it must seed from the book's opening state
  before folding**. What does work as advertised: `LevelDelta.volume` is the absolute
  post-state volume, so densifying is an overwrite and not a running sum.
  And be honest about what it measures: reconstructing the top `D` occupied levels per
  message needs full book state at every step, so this route is a *re-fold* and should time
  **worse** than `from_occupied_levels`, not better. The saving deltas buy is in **storage**,
  which the existing test already measures; cheap to store is not cheap to reconstruct, and
  conflating the two was the plan's error.

Why the winner is not fixed: `from_top_of_book` costs four best-price lookups per message
against `from_occupied_levels(1)`'s two — `best_bid_volume` reaches `bid_volume(1)` →
`bid_price(1)` → `best_bid_price`, a second full lookup on top of the one for the price
itself, twice over. On the baseline `AggregateBook` both are dict scans and the four-lookup
route should lose. On `CachedBestBook` every lookup is O(1) and they should converge.

**Not on `BitmapBook`, and the plan first had this backwards.** The ask side's lowest set
bit is `(bits & -bits).bit_length() - 1`, which the class docstring itself states costs
**O(span)** where the bid side's highest bit is O(1) (`orderbook.py:626`). So the
four-lookup route does twice the O(span) ask work: that rung is where the 4-versus-2 gap
should be *widest*, not where it disappears. The prediction is worth writing down precisely
so the measurement can refute it — but the notebook narrates it as a hypothesis, not a law.

At `reported_depth > 1` the cache stops helping at all, since it indexes only the best
price: the same shallow-versus-deep conditional the strand already measured, from a new
direction.

## Step 5 — tests

`tests/lob/test_serialization.py`, new, covering the round trips the review asked for:

- `MarkParams` → `to_frame` → `from_frame` → equal instance; the frame validates against
  `get_schema`; a frame with a bad dtype, a missing column, and `DepthDecay = 1.5` are each
  rejected.
- `HawkesParams` → round trip, `baseline`/`excitation`/`decay` equal elementwise; NaN
  off-diagonal preserved; a frame carrying two distinct `Decay` values is rejected; an
  incomplete `(Component, Cause)` grid is rejected.
- `AggregateBook` → `to_lobster_frame` → `from_lobster_frame` → identical `levels_map` on
  both sides, **parametrized over `AXIS_B_VARIANTS`**. Cases: the canonical §8 Case-B
  fixture after the sell of 400; a book with interior gaps; a book shallower than
  `reported_depth` (padding round-trips to nothing); one empty side.
- `config` → `example_order_flow_params()` → `to_frame` → `to_json` reproduces the frozen
  constant byte for byte, so an edit to the schema cannot silently orphan the config.
- the example's documented properties: branching ratio ≈ 0.8, and replenishment more than
  5× the reverse coupling — the assertions that used to test `default_flow_params`.

`tests/lob/test_binary_gaps.py`, new: the four bit functions against a brute-force
reference over the strings of a few hundred small integers, plus the boundary cases (`0`,
powers of two, all-ones).

`tests/lob/test_gap_statistics.py`, new: the stub's worked example; the §8 Case-B book,
which has two interior holes on the ask side; agreement across `AXIS_B_VARIANTS`; and a
property test that the gap indices are strictly interior — never before the best occupied
level, never after the deepest.

`tests/lob/test_derived_quantities.py`, new, for §4:

- `micro_price` from the identity equals the direct crossed-weight formula (`approx`, per
  step 3b), on the §8 fixture and on random books. **This independent comparison is the
  whole test.** Asserting instead that a bid-heavy book has `micro_price > mid_price` *and*
  `I¹ > 0` is tautological when `micro_price` is implemented as the identity — inverting
  `queue_imbalance` inverts both sides of it. The crossed-weight formula is the only
  witness, which is exactly why it must not share code.
- `I^n` is **strictly** inside `(−1, +1)` whenever both sides are non-empty, at every `n`,
  over a simulated session; `±1` iff exactly one side is empty; NaN iff both are.

`tests/lob/test_market_session.py`, new:

- `session.stats` equals `session.stats_from_frame()` on the canonical fixture and on a
  200-second simulated session, for every ladder variant — every column unconditionally,
  and `QueueImbalance` on the rows where `QueueImbalanceCovered` holds.
- Uncovered rows carry NaN in route 2 and a real number in route 1, and the simulated
  session at a small `reported_depth` must actually produce some, or the test is not
  exercising the case it claims to.
- **The grid-versus-column trap, directly**: the 101–105 / 99, 90 book at
  `reported_depth = 2`, `imbalance_levels = 2`. Both routes must give
  `(V99 − V101 − V102)/(V99 + V101 + V102)`, and the test states the column-sliced value
  it must *not* equal. Then the same book at `imbalance_levels = 3`, where coverage fails
  on the ask side alone while the bid has span to spare.
- **Axis C equivalence**: `from_top_of_book` equals `from_occupied_levels` at
  `reported_depth = 1`, and `from_level_deltas` equals `from_occupied_levels` at every
  depth tested — frame and statistics both, parametrized over `AXIS_B_VARIANTS`, so the
  equivalence is a claim about the three strategies and not about one book. Timing stays
  out of the tests and goes in the notebook, as the strand already does.

**Existing test files that must change and were unlisted.** `test_replay_and_simulate.py`:
the tap tests go, the `submissions_only` test goes, `default_flow_params` becomes
`config.example_order_flow_params`, and five `OrderFlowSimulator` constructions gain their
arguments. `test_aggregate_book.py:67-68` asserts
`pytest.raises(ValueError, match="undefined")` on `queue_imbalance(1)` for an empty book —
step 3 makes that return NaN, so the assertion inverts; the file's other 20-odd tests need
reading for the same reason. `test_axis_b_variants.py:33` holds a module-scoped simulator
fixture, so it fails at collection until fixed.

**Two comparison hazards the reconciliation tests must handle.** `MarketSession` is
`eq=False`, so "equal sessions" means field-wise `assert_frame_equal`, not `==`. And route
1's `stats`, built from Python floats, is `float64` carrying `np.nan`, while route 2's
arithmetic over masked `Int64` columns yields `Float64` carrying `pd.NA` — which
`assert_frame_equal` rejects on dtype, and `pd.NA is not np.nan`. Normalise explicitly and
say which null is meant; `check_dtype=False` hides the problem rather than deciding it.

**A LOBSTER file test, conditional.** `data/lobster/` holds the ReadMe but the sample CSVs
are gitignored and absent. Add the test anyway, skipped when the file is missing: column
count is `4 × LEVEL`, both sentinels appear with size 0 on padded rows, and one row
round-trips through `from_lobster_frame`/`to_lobster_frame`. It is worth more than the rest
of the new tests together, because it is the only thing that makes "LOBSTER compatible" a
fact rather than an assertion.

## Step 6 — the documentation

`documentation/grid-levels-and-lobster-levels.md`, new, and the reference for everything
above. It is written around one claim, stated in this order:

1. **`I^n` is a grid quantity**, by §3–§4 of the notes. `n` is a number of ticks from each
   touch, not a number of queues. Restated with the definitions inline so the file stands on
   its own, and cross-referenced to the `.tex`, which remains the authority.
2. **A LOBSTER book indexes by occupied level**, so its column *k* and grid level *k* are
   the same price only when the book has no holes.
3. **Gaps are therefore the whole difficulty**, and they are ordinary rather than
   pathological — common on small-tick instruments, and present in Case B of the notes' own
   worked example. A gap inside the window shifts every column past it, silently: the
   column-summed number is well-formed, plausible, and a different statistic.
4. **The repair is to read prices, not columns** — the mask, its ask mirror, and a worked
   evaluation of the 101–105 / 99, 90 book both ways, ending in the two numbers side by
   side.
5. **The repair has a limit**: `grid_span`, the per-side coverage condition, why it is
   sufficient rather than necessary, and why `I³` is unanswerable there from a depth-2 file
   while `I²` is exact. A large-tick book with no holes needs a shallow file and a sparse one
   needs a deep file to answer *the same* `I^n`. Reported depth is a purchase option —
   LOBSTER sells 1, 5, 10, 30 or 50 levels and puts it in the filename; what the market
   decides is **how much grid depth a given reported depth buys**, which is the sentence the
   plan first got backwards.
6. **And truncation limits even that.** On a file, a padded side does *not* mean "the book
   ends here" — it means "no further levels in the visible price range", and `lobster.py`'s
   own docstring says even the last visible level degrades over the session. So the
   "fully reported ⇒ covered" branch is exact for a frame we generated and only an upper
   bound for one we loaded. Hence `MarketSession.from_file`: with a loaded frame that branch
   is dropped. The honest account has three states, not two — covered, not covered, and
   covered-only-within-the-visible-range — and the third cannot be detected from the data,
   so it is named in prose rather than modelled in a column.

It must also say plainly that **our `I^n` is not the literature's**. §4 counts `n` on the
grid, so `I^5` is volume within five ticks of each touch; feed-derived empirical work
almost always counts the first five *queues*, because that is what a file hands you. The
two agree on a large-tick instrument and diverge on a small-tick one, and a student
reproducing a paper's number on the same data needs to know which is which. The grid
definition is the one we keep — a price distance is comparable across instruments and stays
meaningful as the book thins — but the divergence is documented, not discovered.

**Generate the worked evaluation, do not hand-write it.** The repo already forbids this:
`tests/lob/test_documentation_is_generated.py` exists because "a fixture explained in prose
and asserted in code is two statements of one fact". The 101–105 / 99, 90 evaluation appears
in both this document and `test_market_session.py`, so it goes through
`worked_examples.write_into`, as `order-flow-to-order-book.md` already does, and the same
test guards it.

Linked from `documentation/order-driven-markets-notation.md` §3 (which fixes the grid
convention and should say where the other one lives). That file's §9 symbol table also gains
rows for the names this work introduces — `occupied_levels`, `grid_span`, `micro_price`,
`reported_depth` — since the plan adds a link and no entries. And
`unito26/lob/__init__.py` gains `frames`, `config` and `binary_gaps`, per `CLAUDE.md`;
its `replay` entry still advertises "the snapshot taps", `simulate.__all__` still exports
`default_flow_params`, and `AggregateBook.copy`'s docstring is written entirely about a tap
that is being deleted.

**Exam snippets** go in `dev-context/market-microstructure.md` beside the existing ones.
Index-sliced imbalance is the best of them — both versions run, both return a plausible
number, and the wrong one is what most published code does. Better ones surfaced by the
review, all of which are live bugs or near-misses in this very codebase:

- **The sentinel.** `spread = ask_price_1 - bid_price_1` over a padded file gives a mean
  spread near 10⁹ — and the plausible fix, `book[book.bid_price_1 > 0]`, filters the bid
  correctly and the ask not at all, because the two sentinels have opposite signs.
- **Units.** `book.spread` against `AskPrice1 - BidPrice1`: which one is in ticks?
- **`skipna`.** Two imbalance computations differing only by `min_count=1`; one returns NaN
  on an uncovered window, the other a plausible number.
- **The bid `diff` sign** in a gap counter that is right on the ask and negative on the bid.
- **`from_lobster_frame` on a padded row**, which constructs a level at the sentinel price
  with volume 0 — and `set_volume`'s zero rule silently removes it. "Why does this bug not
  bite?" tests whether the student knows the removal invariant, which is a better question
  than "find the bug".
- **A type-7 halt message** replayed as an order at price −1.

"A gap statistic given a grid depth" is the weak one: it needs two definitions in the
reader's head before the snippet means anything, and a multiple-choice item has to stand
alone in about fifteen lines.

## Step 7 — the notebook

`notebooks/simulated-market-session.ipynb`. Not a statistics demo: the **whole pipeline**,
end to end, from a parametrization on disk to a book evolving through a session to the
quantities read off it. The statistics are the last third, not the subject. Load the
**`dataviz`** skill before writing any plotting cell.

### The pipeline, in order

1. **Load the parametrization.** `example_order_flow_params()` and `example_mark_params()`
   from `config`, deserialized from frozen JSON — the notebook demonstrates loading a
   specification, never constructing one inline. Show the `HawkesParams` frame, its
   branching ratio and its stationary intensity, so the numbers are inspected rather than
   trusted.
2. **Build the flow.** `OrderFlowSimulator` over `ExponentialHawkes`, seeded. Warm the book
   up first — a book that starts empty is unrepresentative until it has been running.
3. **Fold the session.** `MarketSession.from_occupied_levels(...)`, which applies each
   message and records the book as it goes. This is the pipeline's centre: order flow in,
   book state out.
4. **Look at what came out.** The `lobster_book` frame *is* what a data vendor sells you —
   say so, and check it against `AggregateBook.get_frame_schema`.
5. **Statistics, both routes**, reconciled and then timed.
6. **Performance**, axis B × axis C.

### Plots

All time series are **step lines** (`line_shape="hv"`): the book holds each state until the
next message, so interpolating between them draws states the book never had. Set
`connectgaps=False` — uncovered `QueueImbalance{n}` rows are NaN, and a line drawn straight
through them would hide exactly the thing the coverage column exists to expose. A long
session is tens of thousands of points, so use `Scattergl` or thin the series, and say
which.

- **Queue evolution at level *n*.** The figure the strand is about, and it comes before any
  derived quantity. One figure, `make_subplots(rows=2, cols=1, shared_xaxes=True)`, with a
  **single dropdown choosing the level *n*** driving all four traces:
  - **top subplot — volumes.** Two traces: `V^{a,n}` and `V^{b,n}`. The queues at that level
    filling and emptying, both sides against each other on one axis.
  - **bottom subplot — prices.** Two traces: `P^{a,n}` and `P^{b,n}`, the actual price levels.

  Splitting by *quantity* rather than by side is what makes the figure readable: each panel
  compares the two sides directly, and the panels share a time axis, so a queue draining
  above and a price stepping below are visibly the same event. Colour encodes side — one
  colour for ask, one for bid, **the same in both panels** — so the reader learns the
  mapping once and the panels are told apart by their y-axes, not by their palette.

  What the price panel shows that nothing else does: the two lines can never cross, and the
  vertical distance between them is the *n*-level spread, widening as the dropdown goes
  deeper. That is `P^{a,n} > P^{b,n}` made visible rather than asserted.

  Plotly mechanics worth getting right, each of them a silent failure:
  - traces are pre-rendered and the dropdown toggles `visible`, so **each button's mask
    needs one entry per trace in `fig.data`**, in trace order — `4 × reported_depth` entries,
    four of them true — and it must switch both panels together;
  - the initial `visible` state must agree with the dropdown's declared `active` index, or
    the figure renders wrong and silently corrects itself on the first click;
  - **plot padded levels as NaN, never as the sentinel.** Where a side holds fewer than *n*
    occupied levels the price is ±9999999999 and the volume 0; drawn literally, one point
    takes the price axis to 10¹⁰ and the panel is destroyed. With `connectgaps=False` the
    line breaks instead, which is the honest picture — that level did not exist then. This
    is the sentinel bug of the exam snippets, in visual form.
  - **say on the figure which indexing *n* means.** It selects a *reported* level, since
    that is what the frame holds. On a book with holes that is not the grid level of the
    same number, and the axis title is where a reader finds that out.
- **Mid-price and micro-price** on one pair of axes, with the shaded band between the
  touches. `P^μ` rides inside the spread and leans toward the thin side: the identity
  `P^μ = P^m + (φ/2)I¹` made visible.
- **Spread**, and the **price gaps** — `BidLargestGap` / `AskLargestGap` and the gap counts
  — stepwise, so the book's sparsity over the session is legible next to its prices.
- **`QueueImbalance{n}` against its column-sliced impostor**, same axes. On a large-tick
  book they lie on top of each other; on a sparse one they diverge, which is the argument
  for the whole convention.
- **Coverage sweep**: `n` over `imbalance_levels` against `reported_depth` over a range,
  plotting the fraction of the session where `I^n` is *not* recoverable from the frame. The
  cell that answers "how deep a file do I need to buy?".

### Timing

- The two stat routes against each other, with a `timeit` decorator, reusing
  `unito26/lob/benchmark.py` (`time_variants`, `best_price_share`).
- The three **recording strategies** across `AXIS_B_VARIANTS` — a 3×5 grid; the headline is
  whether `from_top_of_book` beats `from_occupied_levels(1)`, and on which rungs.
- The gap statistics across `AXIS_B_VARIANTS`, on a shallow book and a deep one — the
  strand's existing finding, that the ladder pays only on a deep book, should reappear here
  or be contradicted.

Whatever the numbers say goes into `dev-context/market-microstructure.md` beside the
existing measured findings, **including where it contradicts the reasoning in this plan**.

## Verification

First action, before any code: copy this plan to **`.claude/plans/`** inside the repo,
beside `order-book-from-order-stream.md`, which `dev-context/market-microstructure.md`
already links to as "the agreed plan, kept so the code can be reviewed against it". Add it
to that reference list.

```bash
conda env update -f unito26.yml && conda activate unito26
python -c "import pandera.pandas as pa; print(pa.__name__)"
python -m pytest tests/ -q
```

The suite must collect (it does not today) and pass, including the 63 existing tests once
their construction sites are updated for the removed defaults.

Then run `notebooks/simulated-market-session.ipynb` top to bottom from a Jupyter launched
inside the env, so plotly renders server-side. Confirm: the session builds from the frozen
config without constructing parameters inline; the two stat routes report identical frames
and different timings; every line holds flat between messages rather than sloping; NaN runs
in the imbalance appear as breaks and not as straight lines; and **the level dropdown
switches the volume panel and the price panel together and is correct on first render,
before any click**. Check one deep level explicitly: the price panel must show breaks where
the side is padded, not a spike to 10¹⁰.

Not in scope: `order_flow_imbalance` on `MarketSession`, which the working copy marks as a
later commit. It is shaped unlike everything else here — Cont–Kukanov–Stoikov's OFI is a
function of *consecutive* touch states, where every statistic above is a function of one
row, so it forces the fold to carry the previous touch in its accumulator. Note the reason
runs one way only: OFI depends on the touch alone, so on the *vectorized* route it is a pure
`diff` over four columns of any frame and is **more** recoverable than `I^n`, not less.
