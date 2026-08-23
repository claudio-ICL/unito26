# From order flow to the order book: the mathematics, and where it lives in the code

Companion to [`order-driven-markets-notation.md`](order-driven-markets-notation.md),
which fixes *what* the objects are.
This file states the mathematics of the implementation
and points at the code that carries each piece.

It is written to be lifted into the LaTeX lecture notes,
so the symbols are the notation file's symbols,
each is given with its `notation.tex` macro,
and the results carry labels in the notes' style.

Every entry is a **triple**: a statement in formulae,
the region of code implementing it,
and the test that certifies it.
Code references point at modules, classes and functions — never at line numbers,
which rot on the next edit.
An entry missing any of the three legs is an entry that is not finished.

**Scope.** Entries 1–6 are built.
Entry 7 (execution PnL) belongs to the order-level book and is not yet written.

---

## 1. The message and the fold

An order is the 4-tuple $(t, q, p, d)$ of §1 of the notation,
with $d = +1$ for a buy and $d = -1$ for a sell.
Prices are integer counts of ticks $\tau$ (`\tickSizeOfLOB`);
the conversion to currency happens once, at the boundary.

A stream of orders becomes a book by a **fold**:
the book is the accumulator, and it holds one state, the current one.
Writing $\mathcal{B}$ for a book state and $m$ for a message,

$$\mathcal{B}_{k} = F(\mathcal{B}_{k-1}, m_k), \qquad \mathcal{B}_0 = \varnothing .$$

The time series $(\mathcal{B}_k)_k$ is *not* held by the book.
It is produced by the driver, which taps the fold at whatever resolution is wanted.

| leg | where |
| --- | --- |
| formulae | §1–§2, §6 of the notation file |
| code | `unito26.lob.messages` (`Message`, `TickGrid`); `unito26.lob.orderbook.AggregateBook.apply`; `unito26.lob.replay.run` and `replay` |
| tests | `tests/lob/test_aggregate_book.py::TestConfiguration`; `tests/lob/test_replay_and_simulate.py::TestTaps` |

Two conventions earn their place in the code rather than in prose.
$d$ is an `int`, never a string and never a bool,
because the single expression $p\,d$ collapses both sides of the book into one comparison.
And a price off the tick grid is rejected at the boundary rather than quietly rounded,
in `TickGrid.to_ticks`.

---

## 2. Aggregation and identity

The organising idea of the strand: what the aggregate state settles, and where it stops.

The **aggregate state** is the object §3 of the notation already defines,

$$\mathcal{B}_t := \big(P^a_t,\ P^b_t,\ \{(V^{a,i}_t, V^{b,i}_t) : i = 1, 2, \dots\}\big),$$

reusing the $\mathcal{B}$ of §1 above, since the book state is what the fold accumulates.
The code keys levels by absolute price where the notation indexes them relative to the touch;
the two are the same state in different coordinates,
$V^{a,i}_t$ being the volume at $P^a_t + (i-1)\tau$.

Everything in §3–§4 of the notation follows from $\mathcal{B}$ by definition:
the prevailing prices and the volumes resting at them, the spread, the mid-price, the imbalance.
The content worth stating is not that, but the dynamics —
`prop.lobUpdate` is written **entirely in terms of $\mathcal{B}$**,
so the aggregate state is closed under the arrival of an order,
and the queue inside a level never has to be represented in order to reproduce the public book.
That map is what `AggregateBook` implements.

What $\mathcal{B}$ drops is *whose* volume traded.
It fixes how much is consumed at each price and at what price it prints,
because $\min(q', V(\pi))$ does not depend on how $V(\pi)$ decomposes into individual orders —
and the allocation among the orders resting at $\pi$ is exactly the discarded half.
So no quantity that names an order can be computed from it:
queue position and the fill probability that depends on it,
the adverse-selection term of §7 that depends on *that*,
attribution of a fill to an account, per-account inventory and PnL,
and cancellation addressed by order identifier.
A withdrawal that names a quantity at a price is a different matter —
it is one more signed delta, which is why it costs nothing here.

| the question | state required |
| --- | --- |
| what are the prices and volumes? how does the book evolve? | aggregate |
| how much volume is ahead of *my* order? will it be filled? | order-level, id-indexed |
| whose fill was that? what is account $X$'s position and PnL? | order-level, id-indexed |

The two perspectives that force the second row are the trader,
who needs her queue position because it drives fill probability,
and the venue, which must attribute every fill to an account.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.orderbook.AggregateBook` — the whole class is the closure made concrete; `AggregateBook.withdraw` is the quantity-addressed case |
| tests | `tests/lob/test_aggregate_book.py::TestCaseA`, `::TestCaseB`, `::TestPassiveOrdersAndWithdrawals` |

---

## 3. The update rule, and the one code path

By the decomposition of §6 (`prop.decompositionOfLimitOrder`),
processing $(t,q,p,-1)$ is processing the ordered pair

$$\big[(t, q_M, 0, -1),\ (t, q - q_M, p, -1)\big],
\qquad q_M = \min\Big(q,\ \sum_{i\ge 1} V^{b,i}_{t-}\mathbf{1}_{\{P^{b,i}_{t-}\,\ge\,p\}}\Big),$$

with $q_M$ (`\marketOrderSize`) the market-order component.
So the engine needs **one** code path — consume, then rest the remainder —
and never a separate branch for "marketable" orders.
In `AggregateBook.submit` the loop simply does not execute when nothing matches.

The eligibility test is the single expression of §2,

$$\pi d \le p d,$$

written `best * direction > limit_price * direction` as the *stopping* condition,
so that one line serves both sides.
A fill trades at the resting price $\pi$, never at the incoming $p$;
`Fill` carries the resting price for that reason.

Two branches are not optional.

**The exhausted side.**
The formulae of §5 assume the incoming order does not consume the whole price-eligible side.
When it does, $N_v = +\infty$, that side empties, and its best price is undefined.
The code returns `None` for a best price rather than a number,
and the derived quantities propagate the `None` instead of inventing one.

**The market-order remainder.**
A market order carries a sentinel price, $p = 0$ (sell) or $p = \infty$ (buy),
which is a price *specification* guaranteeing execution and not a point on the grid.
So its remainder cannot rest where it was sent.
It rests instead at the price it last executed against —
the **market-to-limit** rule, and what venues that accept market orders do with the untraded part.
Xetra states it plainly: any unexecuted part of a market-to-limit order is entered into the book,
at the price it executed at.

The one remainder that cannot rest at all is a market order that executed *nothing*,
which has no price to inherit.
That arises only against an empty opposite side,
where there was no liquidity to take at any price,
so refusing it costs nothing;
`SubmitResult.unfilled` reports the shares rather than dropping them silently.

What must never happen is resting at the sentinel itself.
A fill trades at the **resting** order's price,
so a residual left at $p = \infty$ would print later fills at `sys.maxsize`,
and one left at $p = 0$ — a value indistinguishable from a real, very low price —
would hand every subsequent buyer free shares.
The objection is to the price, not to the resting.

Note what market-to-limit needs: the last traded price, which is not part of $\mathcal{B}$.
Closure survives only because those fills happened in the *same* message,
and the case where none did is exactly the case that is refused.
It is the narrowest the closure of §2 ever gets.

The level changes a message causes are returned as `LevelDelta` values.
These carry the **new absolute volume** at a price, not a signed change,
which makes them idempotent:
a lost or duplicated update is corrected by the next update at that price.
They are keyed by price, never by level index —
an index-keyed delta breaks the moment the best price moves,
because every index shifts by $\delta P^a_t/\tau$, exactly as in §5.

| leg | where |
| --- | --- |
| formulae | §5 and §6 of the notation file |
| code | `AggregateBook.submit` (both parts), `AggregateBook.withdraw`, `messages.LevelDelta` |
| tests | `tests/lob/test_aggregate_book.py::TestCaseB` (walks the book, residual inside the spread, index shift, empty levels), `::TestExhaustedSide`, `::TestMarketOrders`; `tests/lob/test_replay_and_simulate.py::TestTaps::test_delta_volumes_are_absolute_and_so_are_idempotent` |

The worked examples are a catalogue rather than a single fixture,
and it is indexed by the branch of the update rule each one pins,
not by the story each one tells.
Case B remains canonical because it exercises several branches at once.

<!-- begin generated: worked examples -->

### The catalogue of transitions

One example per branch of `prop.lobUpdate`, which is what makes it possible to
argue the set is complete rather than merely plausible.
Each is a fixture in `unito26.lob.worked_examples`,
run against every book variant by the test suite,
with the expected state derived from the notation rather than captured from a run.
The sell-side mirror of each is generated by reflecting prices and flipping $d$.

**1. A passive buy joins an occupied level** &mdash; `buy 75 @ 999`.

*Branch:* N = 0, q^inf = q; the remainder lands where volume already rests.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  ##################             180  ask
    1002  ############                   120  ask
          ----------------------------  spread 2
    1000  ##########                     100  bid
     999  ############################   275  bid
     998  ###############                150  bid
```

**2. A passive buy rests inside the spread** &mdash; `buy 50 @ 1001`.

*Branch:* N = 0, q^inf = q; the best bid improves and the spread narrows.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 1
    1001  #######                         50  bid
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid
```

**3. A sell takes part of the best bid** &mdash; `sell 50 @ 1000`.

*Branch:* N_v bites at n = 1, so N = 0: one price prints and the best is unmoved.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  #######                         50  bid
     999  ############################   200  bid
     998  #####################          150  bid
```

**4. A sell clears the best bid exactly** &mdash; `sell 100 @ 1000`.

*Branch:* N = 1 with nothing walked -- the converse of section 6 failing.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 3
     999  ############################   200  bid
     998  #####################          150  bid
```

**5. Section 8 case a: executed in full, no remainder** &mdash; `sell 250 @ 999`.

*Branch:* N_p bites before N_v; q^inf = 0, so the ask side is untouched.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  ############################   180  ask
    1002  ###################            120  ask
          ----------------------------  spread 3
     999  ########                        50  bid
     998  #######################        150  bid
```

**6. Section 8 case b: walks the book and rests the remainder** &mdash; `sell 400 @ 999`.

*Branch:* q^inf > 0 inside the old spread; ask indices shift, two levels empty.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  ############################   180  ask
    1002  ###################            120  ask
     999  ################               100  ask
          ----------------------------  spread 1
     998  #######################        150  bid
```

**7. A sell consumes the whole bid side** &mdash; `sell 500 @ 998`.

*Branch:* N_v = +inf: the side empties and P^b is undefined.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  ############################   180  ask
    1002  ###################            120  ask
     998  ########                        50  ask
```

**8. A market sell larger than the book** &mdash; `market sell 1000`.

*Branch:* market-to-limit: the remainder rests at the price last executed against.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  #########                      180  ask
    1002  ######                         120  ask
     998  ############################   550  ask
```

**9. A market buy into an empty ask side** &mdash; `market buy 60`.

*Branch:* no fill, so no price to inherit: the remainder cannot rest.

```
    1000  ############################   100  bid

    ---- becomes ----

    1000  ############################   100  bid
```

60 shares are reported as `unfilled`: they neither executed nor rested.

**10. A withdrawal away from the best** &mdash; `withdraw 60 from the buy side at 999`.

*Branch:* a signed delta on one level; the best price does not move.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  ############################   180  ask
    1002  ###################            120  ask
          ----------------------------  spread 2
    1000  ################               100  bid
     999  ######################         140  bid
     998  #######################        150  bid
```

**11. A withdrawal that empties the best bid** &mdash; `withdraw 100 from the buy side at 1000`.

*Branch:* the best price moves *down* and the spread widens -- only cancellation does this.

```
    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 2
    1000  ##############                 100  bid
     999  ############################   200  bid
     998  #####################          150  bid

    ---- becomes ----

    1003  #########################      180  ask
    1002  #################              120  ask
          ----------------------------  spread 3
     999  ############################   200  bid
     998  #####################          150  bid
```

<!-- end generated: worked examples -->

---

## 4. Finding the best price: complexity, and what was actually measured

Write $L$ for the number of occupied levels on a side
and $W$ for the width of the price band in ticks.
Matching is identical in every variant;
**the ladder is entirely about finding the best price.**

The first four keep the dicts as storage and add an index beside them,
so each overrides `best_price` and the `set_volume` that keeps its index in step.
The last one stops varying a single factor on purpose:
a real low-latency book *fuses* storage and index,
the volumes living in the tick-indexed array itself,
and the step from `BitmapBook` to `TickArrayBook` measures exactly that fusion.

| variant | best-price lookup | storage |
| --- | --- | --- |
| `AggregateBook` | $O(L)$ scan of the dict keys | dict |
| `CachedBestBook` | $O(1)$; $O(L)$ on the rescan when the best level empties | dict |
| `HeapBook` | $O(1)$ peek, $O(\log L)$ amortised with lazy deletion | dict |
| `BitmapBook` | one big-integer operation over the occupied span | dict |
| `TickArrayBook` | the same, indexing the array the volumes live in | flat list |

The bitmap deserves its formulae, because they are the whole trick.
With occupancy held as a single arbitrary-precision integer $B$ and origin $p_0$,

$$\max\{p : \text{occupied}\} = p_0 + \operatorname{bitlength}(B) - 1,
\qquad
\min\{p : \text{occupied}\} = p_0 + \operatorname{bitlength}(B \wedge -B) - 1,$$

since $B \wedge -B$ isolates the lowest set bit.
That identity, and the rest of the bit vocabulary the two classes are written in,
are derived in [`integers-in-binary.md`](integers-in-binary.md);
in C++ the same two lookups are a hierarchy of 64-bit words
and a count-trailing-zeros instruction.
**The two sides are not equally cheap**, which is easy to miss and matters below:
the highest set bit is $O(1)$ in the span and the lowest is $O(\text{span})$,
measured flat against a factor of thirty-five over spans from $10^3$ to $10^5$ ticks.

### Measured

Same stream for every variant, verified to produce identical books at every message.
Two regimes, from the same simulator with different `depth_decay`:
about 36 000 messages each, one settling at $L = 33$ occupied levels and one at $L = 900$.

| variant | shallow, $L = 33$ | deep, $L = 900$ | resident, deep |
| --- | --- | --- | --- |
| `AggregateBook` | 1.00× (81 ms) | 1.00× (167 ms) | 110 kB |
| `CachedBestBook` | 0.95× | 1.71× | 111 kB |
| `HeapBook` | 0.94× | 1.75× | **653 kB** |
| `BitmapBook` | 0.95× | 1.77× | 111 kB |
| `TickArrayBook` | 0.97× | **1.85×** | **52 kB** |

**In the shallow regime nothing helps, and everything hurts a little.**
Profiling attributes **8.1%** of run time to the best-price lookup at $L = 33$,
because `min` and `max` over three dozen keys are simply cheap;
removing all of it could not buy more than that,
and every variant instead pays a little index maintenance on each write.
The measured 0.94–0.97× is exactly what that predicts.

**In the deep regime the ladder pays**, and roughly equally for four different designs.
There the lookup is **30.3%** of run time, which is what makes the speedup available.
Note that the speedup is a clean function of $L$ and of nothing else,
so a figure quoted without its $L$ says nothing:
the same code measures 1.0× and 1.85× on the same machine.
The lesson is not a ranking but a conditional —
an optimisation targets a bottleneck,
and whether that bottleneck exists is a property of the market, not of the code.
A large-tick instrument, where flow concentrates within a few ticks of the touch,
sits in the first column.

**Fusion is worth a little, and only where the search already was.**
`TickArrayBook` beats `BitmapBook` by about 5% in the deep regime and neither in the shallow.
In C the fused design wins on cache locality;
inside an interpreter, most of what it saves is spent again on interpretation,
and that gap between the right structure for the machine
and the right structure for the language is the point of showing both.

**Memory tells a different story from time, and it is the one that separates the designs.**
`HeapBook` is the striking case: after 36 000 shallow messages
its heaps hold hundreds of kilobytes of stale entries against a 7 kB book, roughly a hundred to one.
That is the bill for lazy deletion, and `compact` is what pays it.
`TickArrayBook` is the opposite: $8W$ bytes whether or not the levels are occupied,
which here is *less* than the dicts because the band is narrow,
and would be far more on an instrument whose price range is wide and sparse.
The array is a lookup table, and a lookup table costs the whole table.
`BitmapBook`'s $O(W)$ bits are real asymptotically and never bite in either regime measured:
2 kB of bitmap against 426 kB of dicts.

Two methodological notes, both of which changed a number here.
Profiling must use **cumulative** and not own time:
`best_price` does its scanning by calling `max`,
and a profiler bills a builtin to itself,
so the method's own time reports 3% where the truth is thirty.
And an array-backed variant written without a cursor,
rescanning the band on every lookup, once measured 0.18×.
That number was real, and it was a fact about a strawman rather than about the design.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.orderbook` &mdash; `CachedBestBook`, `HeapBook`, `BitmapBook`, `TickArrayBook`, `AXIS_B_VARIANTS`; `unito26.lob.benchmark` for the harness |
| tests | `tests/lob/test_axis_b_variants.py` &mdash; the catalogue and its mirror on every variant, parity with the baseline at *every* step and on the derived views, plus `CachedBestBook.check_cache_is_consistent` |

---

## 5. Hawkes order flow

Order flow clusters, and the clustering is the phenomenon:
calibrations on exchange data put 70–90% of high-frequency flow as endogenous.
A Poisson simulator produces a book that looks nothing like a real one.

For $d$ event types the conditional intensity of type $i$ is

$$\lambda_i(t) = \mu_i + \sum_j \alpha_{ij} \sum_{t^j_k < t} e^{-\beta(t - t^j_k)},
\qquad \alpha_{ij} \ge 0,$$

with $\alpha_{ij}$ read as "type $j$ excites type $i$", and one decay $\beta$ for every pair.

### The Markov state

Define the vector of decayed counts

$$S_j(t) = \sum_{t^j_k < t} e^{-\beta(t - t^j_k)},
\qquad\text{so}\qquad \lambda(t) = \mu + A\,S(t).$$

Between events $S$ decays deterministically, $S(t) = S(t_n)e^{-\beta(t-t_n)}$;
at an event of type $j$, $S_j \mapsto S_j + 1$.
So $(N, S)$ — equivalently $(N, \lambda)$ — is a piecewise-deterministic Markov process,
and the whole history collapses into $d$ floats.

Two consequences worth stating to students.
With a common $\beta$ the state is a $d$-vector;
with per-pair $\beta_{ij}$ it is a $d \times d$ matrix,
so **choosing the kernel is choosing the size of the state**.
And recomputing $\lambda$ by summing over all past events is $O(n^2)$ over a run,
where the recursion is $O(1)$ per event —
the same "carry the right summary statistic" idea as the closure of $\mathcal{B}$ in entry 2,
reached from a completely different direction.

### Stability

With branching matrix $\Gamma = A/\beta$,
$\Gamma_{ij}$ is the expected number of type-$i$ events directly triggered by one type-$j$ event.
Stationarity requires $\rho(\Gamma) < 1$, and then

$$\mathbb{E}[\lambda] = (I - \Gamma)^{-1}\mu .$$

$\rho$ is homogeneous of degree one in $A$,
so the *shape* of the excitation matrix and the overall endogeneity are independent choices;
the default parameters fix the shape by hand and rescale to $\rho(\Gamma) = 0.8$.

### Exact simulation (`prop.hawkesExactSimulation`)

Because every $\alpha_{ij} \ge 0$ and $\beta$ is common,
the **total** intensity $\Lambda(t) = \sum_i \lambda_i(t)$
is itself a one-dimensional exponentially decaying process:
it relaxes at rate $\beta$ towards $\bar\mu = \sum_i \mu_i$,
and at an event of type $j$ it jumps by the column sum $c_j = \sum_i \alpha_{ij}$.
So the scalar Dassios–Zhao scheme applies to $\Lambda$ directly,
and the type is drawn afterwards.

Given $\Lambda_n$, the intensity just after the last event at $t_n$,
the compensator over the next $s$ splits into two increasing pieces:

$$\bar\Lambda(s) = \underbrace{\bar\mu\, s}_{\text{baseline}}
 + \underbrace{(\Lambda_n - \bar\mu)\frac{1 - e^{-\beta s}}{\beta}}_{\text{excited part}} .$$

A point process with compensator $\bar\Lambda_1 + \bar\Lambda_2$
is the superposition of two independent ones,
so the next inter-arrival is the **minimum of two closed-form draws**,
for $U_1, U_2 \sim \mathrm{Unif}(0,1)$:

$$S_1 = -\frac{\ln U_1}{\bar\mu},
\qquad
S_2 = -\frac{1}{\beta}\ln\!\Big(1 + \frac{\beta \ln U_2}{\Lambda_n - \bar\mu}\Big),
\qquad S = S_1 \wedge S_2 ,$$

with $S_2 = +\infty$ exactly when $1 + \beta \ln U_2 / (\Lambda_n - \bar\mu) \le 0$.
That is not an edge case to patch around:
the excited part carries only the finite total mass $(\Lambda_n - \bar\mu)/\beta$,
and $S_2 = \infty$ is the event that it expires without firing.
Then $t_{n+1} = t_n + S$, the state decays, the type $i$ is drawn
with probability $\lambda_i(t_{n+1})/\Lambda(t_{n+1})$, and $S_i$ increments.

$O(1)$ per event, exact, no rejection, no discretisation bias, no time grid.

**This reduction is derived here, not quoted.**
Dassios and Zhao state the scalar case with i.i.d. jump sizes;
ours are type-dependent, which the derivation permits
because the inter-arrival law depends on the state only through $\Lambda_n$.
It is therefore certified numerically, by entry 6, rather than asserted.

Ogata's thinning is kept alongside as the control,
and as the route that survives when the kernel is not common-$\beta$.
Its upper bound is free: with $\alpha \ge 0$ the intensity is non-increasing between events.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.hawkes` — `HawkesParams` (stability, branching, stationary mean), `ExponentialHawkes.step` (the two draws), `OgataThinningHawkes.step`; `unito26.lob.simulate.default_flow_params` for the excitation shape |
| tests | `tests/lob/test_hawkes.py::TestParameterValidation`, `::TestExactSimulation`, `::TestAgreementAndClustering` |

---

## 6. The random time change, and why it certifies the simulator

Integrating the intensity gives the compensator of component $i$,

$$\Lambda_i(T) = \int_0^T \lambda_i(u)\,\mathrm{d}u
= \mu_i T + \sum_j \frac{\alpha_{ij}}{\beta}\big(N_j(T) - S_j(T)\big),$$

because $\int_0^T S_j(u)\,\mathrm{d}u = \big(N_j(T) - S_j(T)\big)/\beta$.
The same two summary statistics that drive the simulation close the compensator in one line.

By the random time change theorem,
transforming each component's event times by its own compensator
yields a unit-rate Poisson process.
So the transformed inter-arrivals must be i.i.d. $\mathrm{Exp}(1)$,
and a Kolmogorov–Smirnov test against $\mathrm{Exp}(1)$ is a direct test
of whether the simulated process has the intensity it claims.

This is the argument for entry 5, not a smoke check,
and it is implemented independently of the simulator on purpose:
a test that shared code with the thing it tests would certify nothing.

Observed, at a fixed seed over four components:
residual means $0.997$–$1.013$ and KS $p$-values $0.39$–$0.72$.
The stationary intensity matches $(I - \Gamma)^{-1}\mu$ to within 2%,
the exact and thinning schemes agree ($p = 0.79$),
and the Fano factor separates the regimes cleanly: $3.42$ against $0.95$ for the Poisson control.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.hawkes.compensators_at_events` |
| tests | `tests/lob/test_hawkes.py::TestExactSimulation::test_residuals_are_unit_exponential`, `::test_stationary_intensity_matches_theory` |

---

## 7. Execution PnL — not yet written

Belongs with the order-level book,
since attributing a fill to an account is exactly what the aggregate state cannot do.
The formulae are §7 of the notation file:
a market order pays $\phi_t/2\,|V|$,
a limit order earns $\phi_{t-1}/2\,|V|$ but carries the adverse-selection term $V\,\Delta P^m_t$.

---

## Appendix: what the real data says

Descriptive statistics only — no reconstruction — over the LOBSTER AMZN sample
(2012-06-21, 10 levels), via `unito26.lob.lobster`:

| quantity | value |
| --- | --- |
| messages | 269,748 |
| submissions | 131,954 |
| withdrawals (partial cancellations + deletions) | 126,375 |
| visible executions | 8,974 |
| hidden executions | 2,445 |
| **withdrawal rate** (withdrawals per submission) | **95.8%** |
| messages sharing a timestamp with the previous one | 3.1% |
| median inter-message gap | 0.62 ms |
| median spread | 13 ticks |
| crossed or locked snapshot rows | 0 |

Three of these are arguments made elsewhere in this document, in measured form.
The withdrawal rate is why removal-by-name, not matching, is the hot path in a real book.
The 3.1% of simultaneous timestamps is §1's uniqueness assumption failing on real data,
precisely where identity begins to matter.
And zero crossed rows is the invariant of §3 holding on a real session.
