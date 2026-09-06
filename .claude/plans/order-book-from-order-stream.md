# Order-stream → order book: a ladder of toy problems

## Context

The course needs its order-book strand: code that folds a stream of orders into a limit
order book. The exercise is chosen because it is the algorithm market makers and HFT firms
actually compete on, but the goal is *teaching* — clear idiomatic Python first, optimisation
earned by measurement (`CLAUDE.md`), with microstructure insight carried along.

Design decision: **build a ladder of toy problems of increasing complexity**, each rung a
complete, tested artefact. Reconstructing the real LOBSTER order book from its message file
is the aspiration the ladder points at, but **it is not built here** — that is a later,
separate commit. This plan stops at L5 and documents L6's edge cases so that students (and
we) can see exactly what the remaining leap consists of.

All notation, mechanics and invariants come from
`documentation/order-driven-markets-notation.md` (and the `market-microstructure` skill).
Nothing here renames or re-derives them.

---

## The break: aggregation vs identity

This is the organising idea of the whole strand, and it should be stated to students exactly
once, sharply, and then paid off repeatedly.

**The aggregate book is a sufficient statistic for the public book.** Represent the state as
`{price → volume}` on each side. For a stream of orders specifying `(t, q, p, d)`, the
transition

```
(aggregate book, incoming order)  ->  (new aggregate book, fills as [(π, size)])
```

is well defined on that state alone: matching consumes level π in FIFO order, and the total
consumed there is `min(remaining q, V[π])` — **independent of how `V[π]` decomposes into
individual orders**. The queue inside a level therefore never has to be represented. Prices,
volumes, spread, mid, imbalance, the whole of §3–§4, all follow from aggregate state.

**Aggregation fails the moment a question concerns a *named* order.** Not "what is the book",
but "what about *this* order":

| the question you must answer | state required |
| --- | --- |
| what are the prices and volumes? how does the book evolve? | aggregate levels |
| how much volume is ahead of **my** order? will it be filled? | order-level, id-indexed |
| whose fill was that? what is account X's position and PnL? | order-level, id-indexed |

The two perspectives that force the second row are the only two that matter in practice:

- **the trader**, who must know her own order's position in the queue — it determines fill
  probability, and with it the adverse-selection term `V·ΔP^m` of §7. `min(q, V[π])` tells
  you *that* the level traded; it cannot tell you whether *you* traded;
- **the trading venue**, which must attribute every fill to an account: allocation, clearing,
  and per-participant PnL. The aggregate transition is deliberately blind to exactly this.

So the state you keep is chosen by the question you are being paid to answer, not by which
message types the feed happens to carry. Cancellation, in particular, is a **consequence**
rather than a cause: a message carrying `(price, size)` is one more aggregate delta and
breaks nothing, while `cancel(order_id)` is just another question about a named order and so
falls on the identity side along with everything else there.

---

## The book is the accumulator; the history is a separate concern

Stated explicitly, because the plan was ambiguous about it and the distinction matters.

**The book object holds one state — the current one.** `AggregateBook` and `OrderBook` are
mutable fold accumulators: a message goes in, the state is updated in place, fills come out.
They have no notion of history and no `t` index. This is what a real engine does, and it is
what keeps the hot path free of allocation.

**The time series of states is produced by the driver, not the book.** `replay.py` owns it:

```
replay(book, messages, record=...) -> Iterator[snapshot]
```

a generator that folds the stream through the book and *taps* whatever the caller asked to
record. The tap is a parameter because the right answer differs by use:

- **nothing** — just run the fold and keep the final book. The benchmark path;
- **top of book per message** — `(t, P^b, V^b, P^a, V^a)`, fixed width, cheap. Feeds §4's
  signals, which are time series and are what students actually analyse;
- **top-`n` levels per message** — a `4n`-wide array. Note this is *exactly* the format of
  LOBSTER's shipped orderbook file, which makes the eventual comparison a matter of equality
  rather than translation;
- **periodic checkpoints** — a deep snapshot every `k` messages.

Three teaching points fall straight out of this split, and they are the reason for making it
rather than bolting a `history` list onto the book:

1. **Aliasing.** A tap that records the book itself records *the same mutable object* every
   time, and every "snapshot" ends up equal to the final state. The tap must copy. This is
   the classic Python bug in its natural habitat and it becomes an exam snippet verbatim.
2. **Snapshots versus deltas.** Recording every state is O(M·n); recording the event stream
   plus occasional checkpoints is O(M), and any intermediate state is recoverable by
   replaying from the nearest checkpoint. This is precisely why real market-data feeds are
   deltas with periodic snapshots, so the implementation choice and the industry design are
   the same fact — worth about 200 MB of arithmetic on the LOBSTER file to make concrete.
3. **The fold is the abstraction.** `replay` is `functools.reduce` with a tap. Naming it that
   way lets us contrast it with an immutable book returning a new state per message — pure,
   elegant, and far too slow — as a road deliberately not taken, with the reason measured.

So for L0–L3: yes, one live aggregated book, updated in place. The series of states exists,
but it is a recording made by the driver, at whatever resolution the question needs.

### The delta strategy, in detail

"Store the deltas" hides two genuinely different things, and separating them is most of the
lesson.

**The message stream is not a book delta.** Replaying messages from a checkpoint does recover
any state, and costs nothing to store — but a message is an *instruction*, not a change: one
marketable order can rewrite five levels, and decoding it requires the matching engine. Any
consumer must own a full engine to read your log.

**A book delta is the set of level changes a message caused**, which is self-describing and
applies with a dict assignment. This is what exchanges actually publish as incremental market
data, and it is what we store:

```python
@dataclass(frozen=True, slots=True)
class LevelDelta:
    side: int      # +1 bid, -1 ask
    price: int     # in ticks
    volume: int    # the NEW absolute volume at that price; 0 means the level is gone
```

`submit()` already knows exactly which levels it touched, so it returns
`list[LevelDelta]` alongside its fills — no diffing of before/after states, which would cost
more than the update itself. Counts are small: a resting order or a cancellation touches one
level, an order walking `k` levels touches `k` (plus one more if it leaves a remainder), and
the empirical average is a shade over one.

**Three encoding decisions, each with a real answer:**

1. **Absolute new volume, not signed change.** A signed change is smaller but requires a
   perfect gapless sequence; an absolute volume is *idempotent* and self-healing — a lost or
   duplicated update is corrected by the next update at that price. Real feeds send absolute
   size per level for exactly this reason, and it is a clean introduction to idempotence as a
   protocol property rather than a slogan.
2. **Key by price, not by level index.** An index-based delta ("bid level 3 is now X") breaks
   the instant the best price moves, because every index shifts — which is precisely the
   `δP^a_t/τ` index shift of §5 in the notation file. Same phenomenon, met twice, once as
   algebra and once as a bug. Good exam snippet.
3. **Invertibility.** With absolute new volumes the log cannot be stepped *backwards*. Storing
   the old volume as well doubles the size and buys rewind, which is genuinely useful in
   research. Present as a trade-off with the cost stated, not as a default.

**On disk, columnar.** `pyarrow` is already in the stack, so the log is a table
`(seq int64, t int64, side int8, price int32, volume int32)`, one row per level change,
written as Parquet. Compare against the dense alternative — one `4n`-wide snapshot row per
message, which is exactly what LOBSTER ships. Order-of-magnitude estimate for that file:
~270k messages × 10 levels × 4 fields ≈ 43 MB dense, against ~350k delta rows ≈ 5 MB. **An
estimate to be measured, not a result** — and the compression ratio is itself a nice
exercise, since dictionary and run-length encoding do most of the work on the `price` column.

**Checkpoints turn the log into random access.** State at time `T` = nearest checkpoint ≤ `T`,
then apply deltas forward. Checkpoint every `k` messages and storage grows as `O(M·n/k)`
while seek costs `O(k)` — students can derive a sensible `k` themselves. Worth naming the
cross-domain relatives explicitly, since it is the same structure every time: video keyframes
and inter-frames, database write-ahead logs with periodic snapshots, event sourcing.

**And the punchline, which belongs to this plan's spine.** From level deltas alone you
**cannot tell a cancellation from an execution** — both simply shrink a level. That is why
venues publish a separate trade feed alongside the book feed. It is the aggregation/identity
break appearing a third time, now in the storage format: aggregate deltas describe the book
perfectly and are silent about what happened.

## Two axes, not one

- **Axis A — complexity of the problem** (rungs L0–L6 below). The spine: each rung adds one
  mechanism, and each rung is finished before the next starts. The break above is the
  L3 → L4 boundary.
- **Axis B — performance of the representation** (dict → cached best → heap → array band).
  Orthogonal, and deliberately *deferred*: we walk it once, on a rung already understood and
  already tested, so every optimisation is validated against a known-correct baseline.

Conflating them is the usual way this topic goes wrong.

---

## The ladder

Each rung states what is added, what state it forces, and its test.

### L0 — one side, submissions only
Aggregate a stream of same-side limit orders into `{price → volume}`. No matching, no best
price. Warm-up: integer tick prices, `(t,q,p,d)` with `d` an `int`, `IntEnum` message types,
a generator over the stream. Test: totals conserved; prices are integer ticks.

### L1 — two sides, matching
The first real engine, still aggregate. `submit()` = **consume-then-rest**, one code path
(Prop. `prop.decompositionOfLimitOrder`), best prices by `min()`/`max()` over dict keys.
Covers walking the book, partial fills, a residual resting inside the old spread.
Tests: §8 Case A and Case B verbatim; book never crosses; shares conserved; fills print at
the *resting* price π, never the incoming price.

### L2 — market orders and exhausted sides
`p = 0` / `p = ∞` sentinels; the remainder of a market order must **never rest** (otherwise a
sell rests at price 0 and matches everything thereafter). The exhausted-side branch:
`N_v = +∞`, best price undefined, one side empty. Tests: sell 500 into the §8 book empties
the bid side; `queue_imbalance` asserts its precondition rather than silently returning 0/0.

### L3 — quantity-addressed changes *(the near-miss)*
Messages that reduce or withdraw resting volume by naming `(price, size)`. Deliberately
placed here because they *look* like they should break aggregation and do not: they are
signed deltas, ~10 lines on top of L1. Volume at a level stops being monotone, the best price
can now move both ways, and the book can empty entirely — but the state does not grow.
This rung exists to make the L4 break land as a genuine result rather than an assumption.

### L4 — **the break: identity**
State becomes `dict[price → deque[Order]]` + `dict[id → Order]`, motivated by the two
perspectives above, not by any message type. The new implementation problem is *removing or
locating a named order inside a queue*, and it gets three implementations, measured against
each other on the same stream:

1. **naive** — linear scan of the level. Simple, and the profile shows this scan dominating
   (on real flow the overwhelming majority of orders leave by withdrawal rather than by
   fill, so removal-by-name *is* the hot path, not an academic case);
2. **tombstones** — mark dead, keep the level volume counter eager, skip on match, compact
   periodically. O(1) removal; teaches deferring work;
3. **intrusive doubly-linked list** — `prev`/`next` on `Order`, id-dict for O(1) location,
   O(1) unlink. This is the actual production design (see the Axis-B research note), and the
   published C++ benchmarks have it winning decisively. In CPython we do not know: `deque` is
   a C-level block structure, while a Python-level linked list pays an attribute lookup per
   hop, so the ranking may invert. The lesson is to **predict from the C++ evidence, measure
   in CPython, and explain whichever way it comes out** — getting the *reason* right, not the
   ranking, is the course's judgment thesis, and it works as a lesson under either result.

Test — the bridge: project the order-level book to levels and assert equality with the L3
aggregate book **after every message**. This is the general form of "both routes agree" in
§8, and it is the single most valuable test in the strand.

### L5 — cashing in the identity
The things L4's state was built for, and L0–L3 provably cannot answer:
- **trader view**: `volume_ahead(order_id)`, fill probability, and the §7 PnL — a limit order
  earns `φ/2` but carries the adverse-selection term `V·ΔP^m`, because we do not choose when
  we are filled;
- **venue view**: fill attribution per account, running inventory `H` and cash `K` per
  participant, and the check that they sum to zero across accounts;
- the mechanism that makes queue position fragile and valuable at once: a size *reduction*
  keeps time priority, while a price change or size increase is a cancel/replace to the back
  of the queue.

### L6 — LOBSTER *(aspiration only — no code in this plan)*
The eventual goal is to reconstruct the shipped 10-level orderbook file from the message
file, validated row by row against ground truth that ships with the data. **That code is
explicitly out of scope here and belongs to a later, separate commit.** It is described in
the plan because the ladder is designed to point at it, and because the reasons it is hard
are themselves teaching material worth stating at L3–L5:

- **Truncation.** Only events inside the visible 10-level range are reported, so deep levels
  are unknowable and even level 10 degrades over the session.
- **Pre-existing orders.** Messages reference orders posted before the file starts; the book
  must be seeded from the first snapshot row, and that seeded volume has no ids — a hybrid of
  aggregate and identified state that neither L3 nor L4 alone handles. This is the sharpest
  illustration of the break on real data.
- **Hidden liquidity.** Type-5 executions are trades that change no visible level, and can
  print at sub-tick prices.
- **Non-unique timestamps.** §1 assumes distinct timestamps; real feeds carry hundreds of
  messages at the same nanosecond. Identity is the order id, not the time — which is also
  §1's uniqueness assumption failing exactly where identity starts to matter.
- **Halts and crosses.** Type 7, and auction prints, are not ordinary matching at all.
- **Asymmetric reporting.** The feed reports the *resting* side of a fill, so the aggressor's
  direction is `-d` — trade signing, exactly, for free. A win rather than a problem.

The ladder therefore ends at L5, and the students' leap from there is: *"same fold, but the
state is partly anonymous, the window is truncated, and time is not an identifier."* That
sentence is worth a lecture on its own, and it is what we hand them if the reconstruction
never gets written.

---

## Axis B — the performance ladder (walked once, on the finished L3 book)

Confirmed scope: **all five steps, ending at the numpy price band, and passing through
`heapq` on the way** — the heap is not skipped, because lazy deletion is an idiom students
will meet again elsewhere.

1. `dict[int,int]` + `min()`/`max()`. The honest baseline. *Expectation:* the O(L)
   best-price scan dominates rather than the matching. **To be measured, not assumed** — if
   the profile says otherwise, the ladder's motivation changes and we say so.
2. **Cached best price**, repaired only when the best level empties. *Expectation:* the
   largest win per line of code in the whole ladder, since it removes the step-1 scan from
   the hot path. Teaches incremental invariant maintenance and keeping a cache honest (a
   debug-mode assert against recomputation — which is also the property test).
3. **`heapq` with lazy deletion.** Min-heap only, so the negation trick for bids; the top may
   be stale, so pop until it indexes an occupied level. O(log L) amortised is a fact about
   the algorithm; **whether it beats step 2 in CPython is genuinely open** — a cached best
   price is already O(1) on the common path, and the heap adds push/pop overhead on every
   message. It may well lose. It is on the ladder because lazy deletion is an idiom worth
   knowing, and a negative result here would be one of the more instructive outcomes.
4. **Array-backed price band (numpy).** Volumes in a contiguous `int64` array indexed by
   tick — `array[p - min_tick]` — with best-bid/best-ask cursors and the band shifted when
   the mid drifts. Teaches integer prices as indices, cache locality, and the honest costs
   (memory, and a fallback for out-of-band prices). **Expect this one to be slower than the
   dict in CPython, not faster.** Scalar indexing into a numpy array carries per-access
   interpreter overhead that a `dict` lookup does not, and the cache-locality win that makes
   this design dominant in C++ is invisible from inside the interpreter. We measure it; if it
   loses, that *is* the lesson — the right structure for the machine is not automatically the
   right structure for the language, and this is where the exam's "judge what an assistant
   proposes" skill gets its sharpest example. A `list[int]` variant is worth timing alongside.
4b. **Occupancy bitmap for the next active level.** Instead of scanning the array for the
   next non-empty tick, keep a bitmap of occupied levels and jump straight to it. In C++ this
   is a two-level 64-bit structure and a `ctz` instruction; in Python it is one arbitrary-
   precision `int` used as a bitset, with `bit_length()` and `x & -x`. Expressive, and a rare
   case where Python states an HFT trick *more* clearly than C++ — but **unmeasured**, and
   the caveat is real: Python's big-int operations are O(width of the band), so a wide band
   could erase the advantage. Measure before recommending it.
5. **Aside: what does not vectorise.** Replay is a sequential fold. numpy cannot remove the
   loop, only make each step cheap — a deliberate counterweight to "reach for numpy".

Every variant is checked for byte-identical output against step 1 on the same stream.

### Honesty about the performance claims

Every "faster" above is a **hypothesis we will measure**, not a result we have. The ladder is
ordered by what it teaches, and the ordering deliberately does not depend on the benchmarks
coming out as predicted. Concretely:

- **evidenced** (third-party C++ measurements, cited below, not reproduced by us): flat array
  beats `std::map`; intrusive lists beat deques. Both are *C++* results and we should say so
  in the notes rather than let students read them as universal;
- **expected but unmeasured**: step 1's scan dominating the profile; step 2 being the big win;
- **genuinely uncertain, could go either way**: step 3 versus step 2; step 4b's big-int cost;
- **expected to go the "wrong" way in Python**: step 4, the numpy band.

The notebooks report whatever the timings actually say, including where they contradict this
plan, and the notes present the contradictions as content rather than hiding them. A course
whose thesis is *judgment* cannot ship unverified performance folklore.

### Is this actually what industry does? (checked, August 2026)

Yes — and the research sharpens two things rather than confirming them blandly.

The widely-cited reference design (WK Selph, "How to Build a Fast Limit Order Book", and the
implementations that follow it) is: **price levels in a tree or map, orders within a level in
a doubly-linked list, a hash table `order_id → order`, and cached pointers to best bid and
best ask.** That is exactly our L4 plus Axis-B step 2. The low-latency refinement replaces
the tree with **a flat array indexed by tick**, precisely because prices live on a fixed
grid — one recent engine *reports* `std::map`+deque at 861K orders/s and p99 3000 ns, the
flat array at 1.36M and 2200 ns, and array + intrusive list at 2.57M and 900 ns. Those are
someone else's numbers on someone else's C++ code; we cite them, we have not reproduced them,
and they say nothing directly about CPython. The occupancy-bitmap trick (4b) and the
sorted-map fallback for wide, sparse price ranges are both documented practice too.

**Correction to make in the plan's own framing.** The industry design is array **and**
intrusive list *together* — they are complementary layers (level lookup vs. intra-level
queue), not competing options, so the ladder must end by combining them rather than leaving
students to think they must choose. And the C++ evidence has the intrusive list winning
decisively, which is the opposite of the "you'll be surprised" line drafted earlier; see the
corrected L4 wording.

Sources: [WK Selph, How to Build a Fast Limit Order
Book](https://gist.github.com/halfelf/db1ae032dc34278968f8bf31ee999a25);
[HFT-Orderbook, the Selph design in Python and
C](https://github.com/Crypto-toolbox/HFT-Orderbook); [How I Built an HFT Matching Engine
(flat array + intrusive lists, with
benchmarks)](https://dev.to/c0sbyy/how-i-built-an-hft-matching-engine-and-all-the-things-i-got-wrong-e23);
[Designing a matching engine that keeps price-time priority (tick-indexed arrays, occupancy
tree, cached best
pointers)](https://www.techinterview.org/post/3233477258/matching-engine-price-time-priority-system-design/).

---

## Streams to drive the ladder

- **Scripted fixtures** (L0–L2): the §8 book and a handful of hand-written sequences, so
  every expected value is derived on paper in the notes and checkable by eye.
- **Synthetic simulator** (L1–L5): a multivariate Hawkes order-flow generator — its own
  section below. Needed because no real feed is submission-only, and filtering a real feed
  produces a book that never existed.
- **LOBSTER, read-only** (any time): parse the message file and *look* at it — message-type
  counts, the withdrawal rate, inter-arrival times, the shipped book's spread distribution —
  **without reconstructing anything**. Cheap, motivating, and safe from every edge case
  above; it is descriptive statistics over two CSVs, not a replay.

---

## The simulator: multivariate Hawkes with a common exponential kernel

Order flow is not Poisson — it clusters, and the clustering is the phenomenon. Calibrations
of Hawkes models on exchange data put **70–90% of high-frequency order flow as endogenous**
(triggered by other orders) rather than driven by external information. A Poisson simulator
produces a book that looks nothing like a real one, and every queue-position or
adverse-selection intuition built on it is wrong. So the simulator is not scaffolding — it is
the second piece of microstructure content in the strand.

### The model

`d` event types; take `d = 6`: market buy, market sell, limit buy, limit sell, cancel buy,
cancel sell. Rungs L1–L2 use the 4-type submission-only restriction of the *same* simulator;
L3 onward switches the cancel types on.

Conditional intensity of type `i`:

```
λ_i(t) = μ_i + Σ_j α_ij Σ_{t^j_k < t} exp(−β (t − t^j_k))
```

with `α_ij ≥ 0` reading "an event of type *j* excites type *i*".

**Design decision: one common decay `β` for all pairs.** This is what makes everything below
work, and it is worth being explicit that it is a modelling choice bought for tractability.

### Why exponential kernels: the Markov state

Define the `d`-vector of decayed counts

```
S_j(t) = Σ_{t^j_k < t} exp(−β (t − t^j_k)),      so   λ(t) = μ + A·S(t).
```

Between events `S` decays deterministically, `S(t) = S(t_n)·exp(−β(t − t_n))`; at an event of
type `j`, `S_j ← S_j + 1`. So `(N, S)` — equivalently `(N, λ)` — is a **piecewise-deterministic
Markov process**, and the entire history collapses into `d` floats. This is the point the
whole design turns on.

Two consequences worth teaching explicitly:

- with a **common** `β`, the state is a `d`-vector; with per-pair `β_ij` it is a `d × d`
  matrix. Choosing the kernel *is* choosing the size of your state;
- the naive alternative — recomputing `λ` by summing over all past events at every step — is
  O(n²) over a run. The recursion is O(1) per event. This is the same "carry the right
  summary statistic" idea as the aggregate book, arriving from a completely different
  direction, and the two should be pointed at each other in the notes.

### Simulation: exact, no rejection

Because all `α_ij ≥ 0` and `β` is common, the **total** intensity `Λ(t) = Σ_i λ_i(t)` is
itself a one-dimensional exponentially-decaying process: it relaxes at rate `β` towards
`μ̄ = Σ_i μ_i`, and at an event of type `j` it jumps by the column sum `c_j = Σ_i α_ij`. So
the Dassios–Zhao exact scheme applies to `Λ` directly, and the type is drawn afterwards.

Given the intensity `Λ_n` just after the last event at `t_n`, the compensator over the next
`s` splits into two increasing pieces,

```
Λ̄(s) = μ̄·s        +    (Λ_n − μ̄)(1 − e^{−βs})/β
        └ baseline ┘      └────── excited part ──────┘
```

A point process with compensator `Λ̄₁ + Λ̄₂` is the superposition of two independent ones, so
the next inter-arrival is the **minimum of two closed-form draws** (`U₁, U₂ ~ Uniform(0,1)`):

```
S₁ = −ln(U₁) / μ̄                                        # baseline part, always finite
S₂ = −(1/β)·ln(1 + β·ln(U₂)/(Λ_n − μ̄))                   # excited part
     = +∞  when  1 + β·ln(U₂)/(Λ_n − μ̄) ≤ 0             # the excited part dies out first
S  = min(S₁, S₂)
```

`S₂ = ∞` is not an edge case to patch around: the excited part carries only finite total mass
`(Λ_n − μ̄)/β`, and `S₂ = ∞` is exactly the event that it expires without firing. Then
`t_{n+1} = t_n + S`, decay `S(·)`, draw the type `i` with probability `λ_i(t_{n+1})/Λ(t_{n+1})`,
and increment `S_i`.

**O(1) per event, exact, no rejection, no discretisation bias, no time grid.** For teaching
this is close to ideal: the algorithm is fifteen lines and every line corresponds to a stated
fact.

*Honesty note:* the reduction of the multivariate case to the scalar Dassios–Zhao scheme via
the common `β` is derived here rather than quoted from the paper (which states the scalar
case with i.i.d. jump sizes; ours are type-dependent, which the derivation permits because
the inter-arrival law depends only on `Λ_n`). It is therefore **verified numerically by the
residual test below**, not asserted.

**Second implementation: Ogata thinning.** Kept alongside, both as the cross-check and as the
route that survives when the kernel is *not* common-`β`. The upper bound is free — with
`α ≥ 0` the intensity is non-increasing between events, so `Λ(t_n⁺)` bounds it until the next
event. Teaches rejection sampling, and makes concrete what the exponential kernel bought us.

### Marks: from an event type to an order

The Hawkes layer produces `(t, type)`. A separate, deliberately independent layer produces
the mark — the `(q, p, d)` that completes the `(t, q, p, d)` of §1:

- **price**: for limit orders, an offset in ticks from the best price, geometric-tailed and
  peaked at the touch, allowed to be negative (inside the spread); market orders take the
  sentinel `p = 0 / ∞` of §6. Needs a defined fallback when a side is empty;
- **size**: lognormal rounded to the lot, mixed with atoms at round lots — real sizes clump
  at 100/500/1000, and a simulator without that produces unrealistically smooth queues;
- **cancellations are state-dependent** and this is the one genuine modelling fork:
  - *(recommended)* Hawkes gives the timing; the victim is a resting order chosen at random
    on that side, size-weighted; if the side is empty the event is a no-op. Keeps the Hawkes
    layer independent and independently testable. **Honest caveat to state in the notes: the
    realised cancellation process is then no longer exactly Hawkes**, because the no-ops thin
    it state-dependently;
  - *(extension)* Cont–Stoikov–Talreja-style intensity proportional to resting volume, which
    is more realistic and destroys the clean separation. Worth showing, not worth starting
    with.

### Default parameters

Set the branching matrix `Γ = A/β` to spectral radius ≈ 0.8, so students see realistic
burstiness rather than a smooth flow, and bake in the empirically documented asymmetry:
**market orders excite the limit-order flow heavily, while limit orders barely excite market
orders.** Self-excitation on each type carries the order-splitting story; market-buy →
cancel-sell carries the liquidity-withdrawal story, which is the mechanism behind the
adverse-selection term of §7. Students can then *see* §7's antagonist in a simulated book.

### Tests

The simulator is not a fixture — it is code with a right answer, and it gets tested like it:

1. **Degenerate case.** `A = 0` ⇒ homogeneous Poisson; KS test of inter-arrivals against
   `Exp(μ̄)`.
2. **Stationary mean intensity.** Simulated per-type rates over a long horizon match
   `(I − Γ)^{-1} μ`, within a stated Monte-Carlo tolerance at a fixed seed. This is the sharp
   quantitative test and it catches almost every indexing error in `A`.
3. **Residual (random time change) test.** Transform each component's event times by its own
   compensator `Λ_i`; the results must be a unit-rate Poisson process, so the transformed
   inter-arrivals are i.i.d. `Exp(1)` — `scipy.stats.kstest`. This is what validates the
   derived exact scheme.
4. **Exact vs thinning agree** in distribution: two-sample KS on inter-arrivals, same
   parameters, independent seeds.
5. **Stability guard.** Constructing parameters with `ρ(Γ) ≥ 1` raises at construction, with
   a message naming the branching ratio.
6. **Clustering is real.** Fano factor of counts markedly > 1, against ≈ 1 for the Poisson
   control — the one-line demonstration of why we did any of this.
7. **Reproducibility.** Same seed, identical stream; `numpy.random.Generator` throughout, no
   legacy global seeding.

*Performance note, same honesty rule as Axis B:* at `d = 6` the numpy vector operations per
event may well be **slower** than plain Python tuples, since the arrays are tiny and the
per-call overhead dominates. Expected, unmeasured, and worth measuring in front of the
students — it is the Axis-B lesson arriving in a second context.

### References

Oakes (1975) for the Markov property; Dassios & Zhao (2013), *Exact simulation of Hawkes
process with exponentially decaying intensity*, for the decomposition; Ogata (1981) for
thinning and (1988) for residual analysis; Bacry, Mastromatteo & Muzy (2015) for the finance
survey; Large (2007) and Bacry et al. for multivariate order-flow specifications; Cont,
Stoikov & Talreja (2010) for the volume-proportional cancellation extension.

---

## Cross-cutting threads

**Python craft:** generators and streaming; `dataclass(slots=True)` vs `NamedTuple` vs dict,
measured; `collections.deque` and what it cannot do; `heapq` idioms; `IntEnum`; typing on
containers; `cProfile`/`timeit` discipline and microbenchmark honesty; defensive replay
(unknown order id → `strict` flag: skip or raise).

**HFT insight:** price-time priority makes queue position an asset, and an asset is exactly
what aggregate state cannot price; L2/MBP versus L3/MBO feeds, and why market makers pay for
the identified one — it is this plan's break, with a price tag on it; latency budgets and why
the hot path allocates nothing; book shifting.

**Exam-snippet harvest** (multiple-choice, per the exam format): float tick prices; a
market-order remainder resting at price 0; inverted imbalance sign; a stale heap top used
without popping; code that answers "am I filled?" from aggregate volume; two removal-by-name
implementations, one correct-but-O(n) and one O(1).

---

## Batches (confirmed scope)

**Step 0 — commit this plan into the repo.** Copy this file to
`.claude/plans/order-book-from-order-stream.md` in `unito26` and commit it with the first
batch, so that reviewing the code means diffing it against the plan it came from rather than
against memory. `.claude/` is not gitignored, so it tracks cleanly. The canonical copy stays
at `~/.claude/plans/consider-order-driven-markets-linked-pearl.md`; the repo copy is the one
that travels with the PR, and if the two ever diverge the repo copy is amended to match what
was actually agreed.

**Batch 1 — L0 to L3, plus the whole of Axis B.** One coherent delivery: `AggregateBook` and
its Axis-B variants, ending on the near-miss that sets up the break. Files: `messages.py`,
`orderbook.py` (parts 1–2), `replay.py`, `hawkes.py`, `simulate.py`, tests.

Plus entries 1–5 of `documentation/order-flow-to-order-book.md`, in the same commits as the
code they document.

`hawkes.py` is separable and self-contained — pure point-process code with no dependency on
the book — so it can be built and tested first, or in parallel, and it is the natural place
to start if the order-book API needs more discussion.

**Batch 2 — L4 and L5.** `OrderBook` appended to the *same* `orderbook.py`: all three
removal strategies benchmarked, queue position, fill attribution, and the §7
adverse-selection story. `to_levels()`, the bridge test, and the combined
array-plus-intrusive-queue design land here, plus entries 6–7 of the documentation file.

**Not in this plan — LOBSTER reconstruction.** L6 is documented above as the aspiration the
ladder points at, and no reconstruction code is written here; it is a later, separate commit.
The only LOBSTER code in scope is `lobster.py` as a **read-only loader and descriptive
statistics** over the two sample CSVs — worth doing early, since it motivates the strand at
almost no cost and touches none of L6's edge cases.

## Deliverable: the maths-to-code documentation

A markdown file, **`documentation/order-flow-to-order-book.md`**, written *as the code is
written* rather than afterwards. Its job is to state each piece of mathematics in formulae
and point at the function that implements it, so that it can be lifted into the LaTeX lecture
notes for this part of the course with the derivations already done.

**Structure.** One numbered entry per result. Each entry is: the statement in formulae → the
region of code implementing it → the test that certifies it. That triple is the whole point;
an entry missing any of the three is an entry that is not finished. The middle leg is a
*pointer*, at whatever granularity is natural — module, class or function — and precision
beyond "a reader with the formula can find the code" is not wanted.

**Contents, in order:**

1. **The message and the fold.** `(t,q,p,d)`, integer ticks, consume-then-rest. Points at
   §1–§2 and §6 of `order-driven-markets-notation.md` rather than restating them, and at
   `AggregateBook.submit`.
2. **The sufficiency proposition** — the aggregation/identity break, stated as a proposition
   with its short proof (the amount consumed at level π is `min(q, V[π])`, independent of the
   decomposition of `V[π]`), plus the precise statement of what it does *not* give you
   (allocation, queue position). This is new mathematics relative to the existing notes and
   it is the spine of the chapter.
3. **The update rule**, §5 of the notation file, mapped line by line onto the implementation,
   including the exhausted-side branch that the proposition's formulae exclude.
4. **Complexity statements** for each Axis-B representation — asymptotic cost per message and
   per operation, stated separately from the measured timings, so the reader can see where
   the two disagree and why.
5. **Hawkes order flow.** The intensity, the Markov state `S`, the PDMP structure, the
   branching matrix `Γ = A/β` and the stability condition `ρ(Γ) < 1`, the stationary mean
   `(I − Γ)^{-1}μ`, the compensator, and — written out in full, since it is derived here
   rather than quoted — the reduction of the multivariate common-`β` case to the scalar
   Dassios–Zhao scheme, with the `S₁`/`S₂` decomposition and the `S₂ = ∞` case.
6. **The random time change** and why it certifies the simulator, connecting the compensator
   to the KS test in `tests/`.
7. **Execution PnL**, §7, as implemented in the L5 attribution code.

**Conventions**, so the lift into LaTeX is mechanical rather than a rewrite:

- symbols are the notation file's symbols and nothing else — the skill's naming map governs,
  and every symbol used gets its `notation.tex` macro named alongside it;
- British English, and semantic line breaking (one clause per line), matching the
  `writing-in-tex` house style;
- **code references point at regions, never at line numbers.** A module, a class, or a
  function name — `unito26.lob.hawkes.ExponentialHawkes.step`, or just "the decay-and-jump
  block in `ExponentialHawkes`" where that reads better. The purpose is to let a reader
  holding a formula find the code that implements it; it is not to be a precise index.
  Line numbers rot on the next edit and chasing them is wasted effort, so they are excluded
  deliberately rather than merely discouraged;
- results carry labels in the notes' style (`prop.aggregationSufficiency`,
  `prop.hawkesExactSimulation`) so cross-references survive the move into the `.tex`.

It is written incrementally with each batch — Batch 1 fills entries 1–5, Batch 2 fills 6–7 —
and reviewed as part of that batch's diff, never deferred to the end.

## Proposed code layout

```
unito26/lob/
  messages.py     # Order, MessageType, direction conventions, tick conversion
  orderbook.py    # BOTH books, in one file — see below
  replay.py       # the fold: replay(book, messages, record=...) + the snapshot taps
  hawkes.py       # HawkesParams (validated), ExponentialHawkes (exact), OgataThinning
  simulate.py     # marks + the book-coupled order stream generator
  lobster.py      # read-only loader + descriptive statistics. NO reconstruction here.
tests/lob/        # mirrors the above: §8 fixtures, invariants, the bridge test
notebooks/        # one notebook per rung, narrative + measurements
```

**`orderbook.py` holds both representations in a single file**, in this order:

1. `AggregateBook` — L0–L3. The `{price → volume}` book, `submit`, `withdraw`, and the §4
   derived quantities.
2. The Axis-B variants of that same book — cached best, `heapq`, numpy price band — as
   subclasses or siblings overriding only best-price lookup, so the matching logic is written
   once and the variants are visibly *only* about finding the best price.
3. `OrderBook` — L4–L5. The order-level book, with the three removal-by-name strategies and
   `volume_ahead` / fill attribution.
4. `OrderBook.to_levels()` — the projection onto `AggregateBook`'s state.
5. The **combined design** — array-indexed levels (Axis-B 4/4b) *with* intrusive intra-level
   queues (L4.3) and the `order_id` dict. This is the reference architecture the research
   note describes, and the file should end on it so students see the two ladders meeting
   rather than competing.

Keeping them in one file is the point rather than an accident: the break of §"aggregation vs
identity" is legible only when the two representations sit side by side, `to_levels()` is the
morphism between them, and the bridge test reads as one statement about one module. The file
will be long; the notebooks, not a file split, are what stage it for students.

Register modules in `unito26/__init__.py` as they are actually built. The agreed design
replaces the `_TBD_` placeholders in `dev-context/market-microstructure.md`, which exists for
exactly this.

## Verification

- `python -m pytest tests/` — §8 Case A/B fixtures at L1/L2; invariants (no crossed book,
  shares conserved, integer ticks, imbalance in [-1,1] with the bid-minus-ask sign); the L4
  bridge test asserting order-level and aggregate agree after every message.
- Each Axis-B step is checked for identical output against the step-1 baseline on the same
  stream, and reports its measured timing against the previous step — **as found, including
  slowdowns**. The plan's predictions above are recorded so they can be scored against the
  results; where a prediction is wrong, the notebook says so explicitly and the notes keep
  the discrepancy as teaching material.
- Simulator: the seven tests of the simulator section, in particular the stationary-intensity
  match against `(I − Γ)^{-1} μ` and the residual KS test — the latter is what certifies the
  exact scheme derived in this plan rather than quoted from a paper.
- LOBSTER read-only statistics reproduce (269,747 messages; 131,954 submissions; 8,974
  visible and 2,445 hidden executions; the remainder withdrawals).
- `documentation/order-flow-to-order-book.md`: every entry names a formula, a code region and
  a test. Checked by reading, not by a script — the references are navigational aids, and
  building machinery to verify them would cost more than it saves.
