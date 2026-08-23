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

This is the organising result of the strand,
and it is new relative to the existing notes.

Let the **aggregate state** be the pair of maps from price to volume,

$$\mathcal{A}_t = \big(\{(p, V^b_t(p))\},\ \{(p, V^a_t(p))\}\big),$$

using $V^b_t(p)$, $V^a_t(p)$ (`\bidVolumePriceP`, `\askVolumePriceP`)
for the volume resting at the absolute price $p$ on each side.

> **Proposition (`prop.aggregationSufficiency`).**
> For a stream of orders $(t,q,p,d)$, the map
> $$(\mathcal{A}_{t-},\ (t,q,p,d)) \longmapsto \big(\mathcal{A}_t,\ \{(\pi, \text{size})\}\big)$$
> is well defined on the aggregate state alone.
> The same holds for a withdrawal that names a quantity at a price.

*Proof.*
Matching consumes the eligible prices in the order given by price-time priority.
At a price $\pi$ with resting volume $V(\pi)$ and $q'$ still to execute,
the amount transacted is $\min(q', V(\pi))$,
and the resting volume becomes $V(\pi) - \min(q', V(\pi))$.
Neither depends on how $V(\pi)$ decomposes into individual orders:
FIFO order within the level fixes *which* orders are consumed,
but not *how much* is consumed there, nor at what price.
Iterating over the eligible prices in order, and resting any remainder at $p$,
determines $\mathcal{A}_t$ and the fills aggregated by price. $\square$

Two consequences, and the second is the important one.

- The queue inside a level **never has to be represented**
  in order to reproduce the public book.
  Everything in §3–§4 of the notation — $P^a$, $P^b$, $V^{a,i}$, $V^{b,i}$,
  $\phi$, $P^m$, $I^n$ — follows from $\mathcal{A}$.
- The proposition is silent about *who* traded.
  The fills it determines are aggregated by price;
  the allocation among the resting orders at that price is exactly what it drops.

So aggregation fails as soon as a question concerns a **named order**:

| the question | state required |
| --- | --- |
| what are the prices and volumes? how does the book evolve? | aggregate |
| how much volume is ahead of *my* order? will it be filled? | order-level, id-indexed |
| whose fill was that? what is account $X$'s position and PnL? | order-level, id-indexed |

The two perspectives that force the second row are the trader,
who needs her queue position because it drives fill probability
and with it the adverse-selection term of §7,
and the venue, which must attribute every fill to an account.

**Cancellation is a consequence, not a cause.**
A withdrawal carrying $(p, q)$ is one more signed delta on $\mathcal{A}$ and breaks nothing.
A withdrawal carrying only an order identifier is another question about a named order,
and falls on the identity side with everything else there.
This is why the ladder places quantity-addressed withdrawal *before* the break:
it looks as though it should force identity, and it does not.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.orderbook.AggregateBook` — the whole class is the proposition's content; `AggregateBook.withdraw` is the "near miss" |
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
A genuine market order carries the sentinel price $p = 0$ (sell) or $p = \infty$ (buy).
Its unfilled remainder must **never** rest:
without the guard, an oversized market sell rests at price $0$
and then matches every subsequent buy,
corrupting the book silently from that point on.

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

The worked example of §8 is reproduced verbatim as the fixture.
Case B is canonical because it exercises everything that usually breaks at once.

---

## 4. Finding the best price: complexity, and what was actually measured

Write $L$ for the number of occupied levels on a side and $W$ for the width of the price band in ticks.
Matching itself is the same in every variant;
**the ladder is entirely about finding the best price**,
so each variant overrides `best_price` and inherits the rest.

| variant | best-price lookup | update |
| --- | --- | --- |
| `AggregateBook` | $O(L)$ scan of the dict keys | $O(1)$ |
| `CachedBestBook` | $O(1)$ amortised; $O(L)$ on the rescan after the best level empties | $O(1)$ |
| `HeapBook` | $O(1)$ peek, $O(\log L)$ amortised with lazy deletion | $O(\log L)$ push |
| `BandBook` | $O(1)$ at the cursor; short local walk, then a vectorised $O(W)$ fallback | $O(1)$ |
| `BitmapBook` | one big-integer operation, $O(W/64)$ words | $O(W/64)$ |

The bitmap deserves its formulae, because they are the whole trick.
With occupancy held as a single arbitrary-precision integer $B$ and origin $p_0$,

$$\max\{p : \text{occupied}\} = p_0 + \operatorname{bitlength}(B) - 1,
\qquad
\min\{p : \text{occupied}\} = p_0 + \operatorname{bitlength}(B \wedge -B) - 1,$$

since $B \wedge -B$ isolates the lowest set bit by two's complement.
In C++ this is a hierarchy of 64-bit words and a count-trailing-zeros instruction;
Python states it in one line each.

### Measured, on 120k simulated messages

Same stream for every variant, verified to produce identical books.
**Two of the plan's predictions were wrong, and they are recorded here as found.**

| variant | shallow book (~12 levels) | deep book (~966 levels) |
| --- | --- | --- |
| `AggregateBook` | 1.00× (baseline) | 1.00× (baseline) |
| `CachedBestBook` | 1.04× | 2.62× |
| `HeapBook` | 0.93× | 3.27× |
| `BandBook` | 0.93× | 3.08× |
| `BitmapBook` | 0.97× | 3.11× |

**In the shallow regime nothing helps, and some things hurt.**
The prediction was that the $O(L)$ scan would dominate the profile.
It does not: profiling attributes **12.8%** of run time to the best-price lookup
when $L \approx 12$, because `min`/`max` over a dozen keys is simply cheap.
Removing all of it could not have bought more than about 15%,
and the measured 1.04× is consistent with that.
The prediction that the cached best price would be the largest win per line of code
was wrong for the same reason.

**In the deep regime the ladder pays**, and roughly equally for three different designs.
There the same profiling attributes **92.2%** of run time to the best-price lookup,
which is what makes a 2.6–3.3× speedup available at all.
The lesson is not a ranking but a conditional:
an optimisation targets a bottleneck,
and whether that bottleneck exists is a property of the market, not of the code.
A large-tick instrument, where flow concentrates within a few ticks of the touch,
sits in the first column.

The array-backed variant is also a lesson in benchmarking.
Written first without the cursor the plan specified — rescanning the band each time —
it measured 0.18× in the deep regime.
That number was real, and it was a fact about a strawman, not about the design.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.orderbook` — `CachedBestBook`, `HeapBook`, `BandBook`, `BitmapBook`, and `AXIS_B_VARIANTS` |
| tests | `tests/lob/test_axis_b_variants.py` — parity with the baseline at *every* step, not just at the end, plus `CachedBestBook.verify_cache` |

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
the same "carry the right summary statistic" idea as `prop.aggregationSufficiency`,
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
