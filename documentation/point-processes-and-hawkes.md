# Point processes and Hawkes flow

The apparatus that generates the order flow of this course, and the quantities one may
legitimately read off it.

**Sources.** The theory is developed in
[`tex/notes/hawkes/`](tex/notes/hawkes/), chapter `chap.hawkes`; the symbols are defined
once, as macros, in [`tex/include/notation.tex`](tex/include/notation.tex). This file is the
code-facing half: it maps each section of the chapter onto the module and the test that
carry it, and adds the facts that belong to this package rather than to the theory.
**If this file and the `.tex` ever disagree, the `.tex` wins** — fix this file.

Numbers are at `config.example_order_flow_params()` — $\rho = 0.6$, $\beta = 4\ \mathrm{s}^{-1}$,
$\nu = 30.19$ events/s — unless another parametrization is named.

---

## 1. The map

| chapter | statement | code | tests |
| --- | --- | --- | --- |
| §1 `sec.countingProcesses` | compensator, intensity, Meyer's time change | — | — |
| §2 `sec.hawkesProcesses` | the definition, $\Gamma$, the cluster representation | `hawkes.HawkesParams` | `test_hawkes.py::TestParameterValidation` |
| §3 `sec.exponentialKernel` | $\lambda = \mu + AS$, the $O(1)$ recursion, the compensator display | `hawkes.intensities_at_events`, `hawkes.compensators_at_events` | `test_hawkes.py::TestTheReplayedIntensity` |
| §4 `sec.stability` | $\rho$, $\lambda^*$, cluster sizes, the endogenous fraction | `HawkesParams.branching_matrix`, `.branching_ratio`, `.stationary_intensity`, `.endogenous_fraction`, `.mean_cluster_size` | `test_hawkes.py::TestTheBranchingStructure` |
| §5 `sec.secondOrder` | the Lyapunov equation | `scipy.linalg.solve_lyapunov`, used in the notebook | — |
| §6 `sec.simulation` | Dassios–Zhao, Ogata thinning, the residual test | `hawkes.ExponentialHawkes`, `hawkes.OgataThinningHawkes` | `test_hawkes.py::TestExactSimulation`, `::TestAgreementAndClustering` |
| §7 `sec.readingOrderFlow` | $p$, $\Delta\lambda$, the comparison with $\mathrm{OFI}$ | `HawkesParams.signed_endogenous_fraction`, `imbalance_regression` | `test_hawkes.py::TestTheSignedContrasts` |

Three invariants any implementation must respect, all of them load-bearing:

- **$A \ge 0$ and a scalar $\beta$ are what make the exact scheme valid**, and they do
  *different* jobs. The common $\beta$ is what makes the total intensity decay as a single
  exponential between events; $A \ge 0$ is what makes the excess over $\bar\mu$
  non-negative, so that both factors of the survival function are genuine. Neither
  substitutes for the other.
- **$\rho < 1$ is checked in `__post_init__`**, and the error names the offending value.
  Nothing downstream re-checks it.
- **$\Gamma$ is read column-exciting, row-excited.** `excitation @ decayed_counts` and
  `excitation.sum(axis=0)` are the two places this shows. A transposed kernel passes every
  stability check and produces a stationary path of the right total rate, so the convention
  is the only defence.

The compensator is implemented independently of the simulator **on purpose**. An accumulated
compensator would agree with the path by construction; an independently computed one turns
the time-change theorem into a test. That is what
`test_hawkes.py::TestExactSimulation::test_residuals_are_unit_exponential` exercises.

---

## 2. The two regimes

The package ships two flow parametrizations. They hold $\rho = 0.6$ and $\nu = 30.19$ in
common --- and only those two, since a different shape gives a different $\Gamma$ and hence
a different $(I-\Gamma)^{-1}$ --- and differ in one structural property, which is the property that decides what
$\mathrm{OFI}$ predicts.

Pressure partitions the six event types: $p = +1$ on
$\{$market buy, limit buy, withdraw ask$\}$ and $-1$ on the mirror. `EXAMPLE_ORDER_FLOW_PARAMS`
excites **across** that partition — what depletes a side calls forth what refills it —
so an offspring tends to carry the opposite pressure to its parent.
`TRENDING_ORDER_FLOW_PARAMS` excites **within** it, so an offspring tends to carry the same.

| | `EXAMPLE_` | `TRENDING_` |
| --- | --- | --- |
| signed endogenous fraction | $-0.351$ | $+0.554$ |
| unsigned endogenous fraction | $0.682$ | $0.574$ |
| $\Gamma$ column sums | $(1.42, 1.42, 0.20, 0.20, 1.04, 1.04)$ | $(0.69, 0.69, 0.46, 0.46, 0.69, 0.69)$ |
| marks | `EXAMPLE_MARK_PARAMS`, `DepthDecay` 0.08 | `TRENDING_MARK_PARAMS`, `DepthDecay` 0.15 |
| empty-side rows | none in $2.17\times10^{6}$ | $1.7\times10^{-3}$ |
| largest single-event mid move | 6.5 ticks | 14.5 ticks |

Measured over six seeds, correlation of $\mathrm{OFI}$ over a 325 ms window against the
forward mid change:

| $h$ | 0.03 s | 0.1 s | 0.325 s | 1 s | 3 s | 10 s |
| --- | --- | --- | --- | --- | --- | --- |
| `TRENDING_` | $+0.025$ | $+0.033$ | $+0.044$ | $+0.024$ | $-0.015$ | $-0.039$ |
| `EXAMPLE_` | $-0.024$ | $-0.035$ | $-0.054$ | $-0.071$ | $-0.094$ | $-0.105$ |

**Contemporaneously both are positive** — $+0.358$ and $+0.408$ over the same 325 ms window.
That is the mechanical accounting of `chap.orderDrivenMarkets` and it does not distinguish
the regimes. Only the forward sign does.

Two facts about the trending regime are constraints rather than choices, and both were
measured rather than assumed. It **requires a thin book**: flattening the offset or
thickening the queues restores the book's own mechanical resilience and drives its
predictive sign negative at every horizon, which is why it carries its own marks. And its
withdrawal rows **cannot be damped** to protect the book — doing so drives the limit-order
baseline negative at $\rho = 0.6$. Its crossover near $h = 3$ s, positive before and
negative after, is impact giving way to resilience, and is a result rather than noise.

| leg | where |
| --- | --- |
| statement | this entry, and `chap.hawkes` §7 |
| code | `unito26.lob.config` — `example_order_flow_params`, `trending_order_flow_params`, `trending_mark_params` |
| tests | `test_serialization.py::TestFrozenExamples::test_the_two_regimes_have_opposite_signed_endogeneity` |

---

## 3. The filtration, and where the flow stops being Hawkes

The generator has two layers and only the first is a point process.

The Hawkes layer produces $(T_n, E_n)$ and is tested as one. The **mark** layer then turns
each event into a message against the live book: a limit order is priced relative to the
opposite touch, and a withdrawal must name size that actually rests. A withdrawal drawn on
an empty side is *dropped*, so the realised withdrawal process is a state-dependent thinning
of a Hawkes process and not a Hawkes process. The rate at which this bites is therefore a
reportable quantity and not a nuisance: it is zero on `EXAMPLE_` and $1.7\times10^{-3}$ on
`TRENDING_`.

This is also why the intensities never read the book. Coupling them to resting size — the
Cont, Stoikov and Talreja extension — would remove the caveat and remove the separation with
it, which is why it is not the starting point.

**Predictability is a property of the intensity, not of a regressor.** $\lambda$ must be
predictable because Definition `def.compensator` requires it, and that is why
$S_e(t) = \sum_{T^e_j < t}$ carries a strict inequality. $\mathrm{OFI}_{t,w}$ is not required
to be predictable and is not: it is $\mathcal F_t$-**adapted**, and it includes $e_n$. A rule
demanding predictability of the regressor would forbid the study's own statistic.

What adaptedness does govern is alignment. The base of a forward difference is the row *by
index*, never a lookup on its own timestamp. For the simulated flow the Hawkes times are
almost surely distinct, so this is a formality; for a session read from a LOBSTER pair it is
not, and `session.window_start`'s `searchsorted` sides are where the convention is encoded.

| leg | where |
| --- | --- |
| statement | this entry |
| code | `unito26.lob.simulate.OrderFlowSimulator._withdrawal`, `session.window_start` |
| tests | `test_fold_and_simulate.py`, `test_rolling_statistics.py` |

---

## 4. The dimensionless groups

The laboratory is specified by four numbers, and every result is reported against them.

| group | value | what it controls |
| --- | --- | --- |
| $\rho$ | $0.6$ | how much of the flow is endogenous, and how long a cluster lasts |
| signed endogenous fraction | $-0.351$ / $+0.554$ | whether that endogeneity carries the parent's pressure — the regime |
| $\nu/\beta$ | $7.55$ | clustering: how many events fall within one kernel timescale |
| $\nu w$ | $9.8$ at $w = 325$ ms | aggregation: how many events a window is expected to hold |

Keep the rate symbols apart. $\lambda(t)$ is the intensity **vector**;
$\bar\lambda(t) = \mathbf 1^\top\lambda(t)$ its total, the scalar the exact scheme decomposes;
$\lambda^* = (I-\Gamma)^{-1}\mu$ the **stationary** vector, which the $\rho$ ladder holds
fixed; and $\nu = \mathbf 1^\top\lambda^*$ its total, a rate in events per second.
$\Lambda$ is the compensator and nothing else.

**$\nu w$ is a stationary-rate count, and the window's realised occupancy is not it.** Rows
are sampled at events, so what a window holds is the *Palm* count. The decomposition is one
— the sampling event itself, present for a Poisson process too — plus $\nu w$ from the rate,
plus the rest from the pair correlation; only the last is clustering, and nothing is
length-biased, so this is Palm sampling with a positive pair-correlation function and not the
inspection paradox. The excess shrinks with $\rho$; the distinction does not.

**Why $\beta = 60$ was the wrong laboratory.** At the old decay, $\nu/\beta = 0.50$: an
event's excitation had fallen to 13.7% before the next event arrived, and the tuned window
held 0.9 events. A study run there measures a process whose self-excitation is switched off
between observations, and correctly finds very little. At $\beta = 4$ the same window holds
about ten. The lesson generalises and is worth stating to students: **check $\nu/\beta$
before believing a null result about clustering.**

---

## 5. The window constant

Matching a boxcar of width $w$ to the kernel $e^{-\beta s}$ in $L^2$ maximises
$(1 - e^{-x})/\sqrt x$ with $x = \beta w$, so the optimum solves $e^{-x}(2x+1) = 1$:

$$x^* = 1.2564, \qquad w^* = \frac{1.2564}{\beta} = 314\ \mathrm{ms}\ \text{at } \beta = 4.$$

That is the derivation. The *measured* argmax of predictive skill does not sit there: across
$\beta \in \{30, 60, 120, 240\}$ it lands at $\beta w \approx 1.62, 1.81, 1.79, 1.78$, i.e.
nearer $1.8$, which at $\beta = 4$ is $450$ ms. The gap is not an error in either number.
The $L^2$ match optimises fidelity to the kernel; the skill optimises prediction of a
lattice-valued outcome through the mark layer, and the two are different objectives. Quote
whichever is meant, and say which.

**Never quote $1.3/\beta$.** It is neither the derived constant nor the measured one.

---

## 6. What the model does not contain

So that a reader cannot take a result here for a result about markets.

- **The intensities do not read the book** (entry 3). Arrival rates are indifferent to
  whether a queue is about to empty; only the marks see it.
- **No informed trading and therefore no adverse selection.** This is the largest omission
  and it is argued in full in `chap.hawkes` §7. In a traded book a provider is short an
  option and withdraws before being picked off, so depletion begets depletion, and $I^n$ is
  informative because a thin bid is thin *because* its providers inferred something. Our
  kernel does the reverse by construction. **Whatever forecasting power $I^n$ retains here
  is mechanical, and none of it is informational.** Read every OFI-versus-$I^n$ comparison
  asymmetrically: OFI winning is not evidence it dominates in general; $I^n$ winning would
  be the stronger finding.
- **No queue-position economics.**
- **One excitation timescale**, the kernel being a single exponential. What that costs, and
  what a per-pair $\beta$ would cost instead, is `remark.stateSize`.
- **No intraday non-stationarity**, so a tuned window is not validated against one.
- **No anchor for the price level**, so the level wanders freely and the mean price change
  over a session is a per-seed random drift the size of the effects being measured. This is
  why pooled rows are demeaned within seed.

Two questions cannot be asked in this setting at all, because they need recorded data:
whether any regime studied here occurs in a traded market, and whether one excitation
timescale suffices to describe one.
