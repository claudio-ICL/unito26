# Point processes and prediction

The theory the imbalance regressions use, stated once. A companion to
[`order-driven-markets-notation.md`](order-driven-markets-notation.md) in the way
[`order-flow-to-order-book.md`](order-flow-to-order-book.md) is one, and written to be
lifted into the LaTeX notes.

Every entry is the same triple those files use — the statement in formulae, the region of
code that carries it, the test that certifies it — and an entry missing a leg is
unfinished. Where a leg is a *gap* the entry says so rather than leaving it blank.

§5 and §6 of `order-flow-to-order-book.md` already carry the Hawkes construction, the
Markov state, stability, the compensator display and the random time change. This file
cites them and does not restate them: the entries below add the hypotheses and the
consequences that file leaves out, which is where the design's pressure actually falls.

Numbers are at the example parametrization — $\rho = 0.6$, $\beta = 60\,\mathrm{s}^{-1}$,
$\nu = 30.19$ events/s — unless another is named.

---

## 1. The filtration is the subject

$N$ is a counting process: increasing, adapted, càdlàg, one coordinate per event type.
$\mathcal{F}_t$ is what is known at $t$ and $\mathcal{F}_{t-}$ its left limit. The
intensity is defined *relative to a filtration* and is meaningless without one.

The simulator makes this concrete rather than abstract. `simulate._withdrawal` drops an
event on an empty side, so the message stream is a **state-dependent thinning** of the
point process, and the filtration an observer of messages has is strictly coarser than the
one the Hawkes state has. Two consequences the study relies on: the drop rate is a
property of the *book* and not of the model, and it cannot be estimated from the messages,
since the messages are precisely what the drops are missing from.

`EventJournal` exists to hold the difference. At the example parametrization the drops are
almost all in the warm-up, where the book fills from cold. Over twenty hour-long sessions
past the warm-up a side is empty on 26 rows in a million.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.simulate` — `EventJournal`, `OrderFlowSimulator.stream`, `_withdrawal` |
| tests | `tests/lob/test_fold_and_simulate.py::TestTheEventJournal` |

---

## 2. What subcriticality is and is not for

§5 has the compensator; this entry supplies the hedge it omits.

$N - \Lambda$ is a true — indeed square-integrable — martingale on every $[0, T]$ as soon
as $\mathbb{E}[N_T] < \infty$, and for a linear Hawkes process with an exponential kernel
that holds at **any** $\rho$, sub- or supercritical, because the mean solves a linear
renewal equation that is finite on compacts. Writing "local martingale, by
subcriticality" attributes the wrong thing to the wrong hypothesis.

Subcriticality buys something else, and the study needs all three parts of it:
stationarity, second moments bounded uniformly in $T$, and ergodicity. The residual test
of entry 4 needs the first, entry 8 needs the second, and the session lengths rest on the
third — a longer session buys variance more cheaply than another seed only if the process
is ergodic.

| leg | where |
| --- | --- |
| formulae | this entry; `order-flow-to-order-book.md` §5 for the construction |
| code | `unito26.lob.hawkes` — `HawkesParams.__post_init__`, which refuses $\rho \ge 1$ |
| tests | `tests/lob/test_hawkes.py::TestParameterValidation::test_rejects_unstable_process` |

---

## 3. Predictability, and what it does and does not constrain

Predictability — $\mathcal{F}_{t-}$-measurability — is the requirement on the
**compensator**, not on a regressor. A predictor need only be
$\mathcal{F}_t$-**adapted**, and $\mathrm{OFI}_{t,w}$ includes $e_n$, so it is adapted and
not predictable. A file demanding predictability of it would forbid the study's own
statistic.

What the distinction does govern is **ties**. With several rows sharing a timestamp,
adaptedness fixes which of them the regressor may read and which the outcome starts from,
and that is what the `searchsorted` side arguments encode. The base of a forward
difference is the row *by index*, never a lookup on its own timestamp, because several
rows are different states at one clock reading. The right edge at $t+h$ legitimately
includes its ties, the outcome being measured there.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.imbalance_regression` — `forward_change`, `backward_change`; `unito26.lob.session.window_start` |
| tests | `tests/lob/test_imbalance_regression.py::TestForwardChange`, `::TestBackwardChange` |

---

## 4. The random time change

Meyer (1971), Papangelou (1972); Ogata (1988) for the residual analysis. §6 has the
construction, so this entry carries the hypotheses:

* the compensators are continuous;
* $\Lambda_i(\infty) = \infty$ almost surely;
* no two components jump simultaneously.

All three hold for the Hawkes state. The third, together with the choice of filtration, is
exactly what the dropped-withdrawal thinning breaks for an observer of messages — entry 1
again, in a second guise.

**A gap, named rather than hidden.** The theorem yields unit-rate Poisson components that
are also *independent of one another*. The suite tests each margin against
$\mathrm{Exp}(1)$ and nothing else, so the independence is asserted by the mathematics and
not certified by the code.

| leg | where |
| --- | --- |
| formulae | `order-flow-to-order-book.md` §6; the hypotheses here |
| code | `unito26.lob.hawkes.compensators_at_events` |
| tests | `tests/lob/test_hawkes.py::TestExactSimulation::test_residuals_are_unit_exponential` — margins only |

---

## 5. The cluster representation

Hawkes and Oakes (1974): existence by the branching construction, and not merely by the
intensity equation. Immigrants arrive at rate $\mu$; each event of type $j$ has
$\mathrm{Poisson}(\Gamma_{ij})$ offspring of type $i$, at exponential lags of mean
$1/\beta$; $\Gamma = A/\beta$.

Two quantities are routinely read off $\rho$ and are not it.

The **endogenous fraction** is $1 - \bar\mu/\nu$, and it equals $\rho$ only when $\Gamma$
has constant column sums, $\mathbf{1}^\top$ being its left Perron vector in that case.
Here the column sums are $(1.310, 1.310, 0.437, 0.437, 0.470, 0.470)$ and the fraction is
$0.576$ at $\rho = 0.6$.

The **mean cluster size** is $\mathbf{1}^\top(I-\Gamma)^{-1}e_j$ for a type-$j$ immigrant
— $4.635$ for a market order, $1.960$ for a limit order — averaged with weights
$\mu_j/\bar\mu$, which gives $2.357$ against the scalar formula's $2.5$. The weight is the
right one because clusters are founded by immigrants, and it is certified by
$\bar\mu \times 2.357 = \nu$. Weighting by $\lambda^*/\nu$ answers a different question,
descendants of a randomly chosen event rather than of an immigrant, and gives $2.425$.

**This is the entry that explains why $\mathrm{OFI}$ carries information at all.** A
cluster is a run of same-signed events, and a sum over a window is an estimate of whether
one is in progress.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.hawkes` — `branching_matrix`, `endogenous_fraction`, `mean_cluster_size` |
| tests | `tests/lob/test_hawkes.py::TestTheBranchingStructure` |

---

## 6. What $\mathrm{OFI}$ is an estimator of, and where it is wrong

The bridge, and the reason this file exists.

$S(t)$ is a sufficient statistic for the future of the flow, and $\lambda = \mu + A\,S$.
So the flow-only predictor of the next event's pressure is built from the single scalar

$$\kappa(t) = p^\top A\,S(t),$$

$p$ being the pressure vector of $\pm 1$. $\mathrm{OFI}_{t,w}$ is a **causal linear filter
on that same state**, which is what makes tuning $w$ a question with an answer rather than
a hyperparameter sweep. It differs from $\kappa$ in three separable ways, and the study
measures each.

**The window shape.** A boxcar of width $w$ against the exponential $e^{-\beta s}$. This
is the tunable one. Matching a boxcar to an exponential in $L^2$ puts the optimum at
$w^* = c/\beta$ — note $1/\beta$ and not $1/(\beta(1-\rho))$: the filter matches the
*kernel*, not the cluster relaxation. Measured on simulated paths at fixed $\lambda^*$,
the argmax of $\mathrm{Corr}(\text{signed boxcar}, \kappa)$ gives $w^*\beta$ of
$1.62, 1.81, 1.79, 1.78$ at $\beta = 30, 60, 120, 240$ — the window halves when $\beta$
doubles — against the competing group $w^*\beta(1-\rho)$, which is not constant in the
$\rho$ ladder at all.

**The type weights.** $\kappa$ weights an event of type $j$ by $(p^\top A)_j$, here
$(\pm 30.23, \pm 16.12, \mp 16.12)$: a market event carries $1.875$ times the weight of a
limit or a withdrawal. $\mathrm{OFI}$ weights flat. This is a misspecification no window
removes — at its best window the plain signed boxcar correlates $0.816$ with $\kappa$
where the type-weighted boxcar reaches $0.856$, and the gap of about $0.04$ persists
across the whole $\rho$ ladder. A result about the estimator, not a defect to be fixed.

**The marks.** $e_n$ is not $p_n \times \text{size}$.
`session._order_flow_contribution` returns the *touch-size increment*: zero for a limit
order resting behind the touch, a whole queue for a cancellation at it, the stale best-ask
size for a market order that walks. So $\mathrm{OFI} = \sum p_n g_n$ with a
book-dependent random gain, and `simulate._withdrawal` caps a withdrawal at the resting
size, so the marks are book-measurable and independence does not hold. What is available
is the approximation $\mathbb{E}[g_n \mid \mathcal{F}_{t-}, \text{type}] \approx \bar g$,
which needs a stationary book and no correlation between touch depth and $S$ — both
testable, and the diagnostic is a regression of $|e_n|$ on the trailing event count.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.hawkes.intensities_at_events`; `unito26.lob.imbalance_regression` — `backward_sum`, `tune_window`, `lag_buckets`; `unito26.lob.session._order_flow_contribution` |
| tests | `tests/lob/test_imbalance_regression.py::TestBackwardSum`, `::TestTuningTheWindow`, `::TestTheNestedFit` |

---

## 7. Why the oracle is not a ceiling

$\mathrm{sign}(\kappa)$ is optimal **among flow-only predictors**. It is not a bound on
what any predictor can do.

$I^n$ reads the book, which is a function of the marks as well as of the points, so it can
and does beat the flow oracle. The extreme case is $\rho = 0$: the flow oracle is then
constant, and $I^n$ still predicts. Stating this prevents the natural misreading that a
Hawkes simulator makes flow statistics optimal by construction.

One further care. $(\lambda^\uparrow - \lambda^\downarrow)/\bar\lambda$ is **not** the
probability contrast for the next event's pressure: the components decay toward $\mu$
while the process waits, so

$$\mathbb{P}(+) - \mathbb{P}(-) = \kappa \int_0^\infty e^{-\beta s}e^{-\Lambda(s)}\,\mathrm{d}s,$$

a strictly shrunk version of it. The *sign* survives the shrinkage, but only because
$p^\top\mu = 0$; on an asymmetric specification even that fails. So $\mathrm{sign}(\kappa)$
is the oracle for classification and the integral for probabilities, while the ratio is
the instantaneous mark expectation and is labelled as one, never scored as a calibrated
probability.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.hawkes.intensities_at_events`, whose docstring carries the shrinkage |
| tests | `tests/lob/test_hawkes.py::TestTheReplayedIntensity` |

---

## 8. Second-order structure, and the window

Written out, because this is the one place the derivation is usually got wrong. With
$V = \mathrm{Cov}(S)$,

$$(A - \beta I)V + V(A - \beta I)^\top + \mathrm{diag}(\lambda^*) = 0 .$$

The forcing term is the **jump-intensity diagonal** and not a free $Q$. The jump part
contributes $S\lambda^\top + \lambda S^\top + \mathrm{diag}(\lambda)$, and substituting
$M = V + mm^\top$ with $m = \lambda^*/\beta$ cancels the cross terms exactly, because
$(A - \beta I)m = -\mu$.

Applying $\mathbf{1}^\top$ with $\mathbf{1}^\top A = \beta\rho\,\mathbf{1}^\top$ recovers
the scalar formula $\nu/(2\beta(1-\rho))$ — which exhibits it as the **constant-column-sum
special case** it is, the same hypothesis that fails for the endogenous fraction. Here it
fails by $5.1\%$: $\mathrm{Var}(\mathbf{1}^\top S) = 0.6612$ against the formula's
$0.6289$, and forcing the column sums equal reproduces the formula to machine precision,
which pins the cause.

The relative standard deviation is what says how long a window must be before its sum is
signal rather than noise, and it must be compared object by object. For
$\mathbf{1}^\top S$ the exact value is $1.6162$ against the formula's $1.5762$; for
$\bar\lambda$ it is $1.0551$ against the same formula value, the large constant baseline
$\bar\mu = 12.81$ of $\nu = 30.19$ damping a variation the formula knows nothing about.
Setting one object's exact number against the other's formula value is the error to avoid.

The spectrum of $A - \beta I$ is
$(-48.60, -45.89, -44.92, -43.88, -43.88, -24.00)$: six independent modes at five distinct
rates, the repeated one semisimple, which is what rules out a $t\,e^{\lambda t}$ term. The
slowest is the Perron mode at $-\beta(1-\rho) = -24$. There is **no** mode at $-\beta$,
which is to say $A$ is non-singular: $1/\beta$ is the mean lag of a direct child, not a
relaxation rate of the mean response.

Nor is $\ln 2/(\beta(1-\rho))$ the half-life of that response. The *intensity*-response
half-lives are $33.8$ ms for a market shock, $24.3$ for a limit and $28.5$ for a
withdrawal, against an asymptotic $28.9$ ms that the market response **exceeds**, so no
bound holds in that direction. The *state* response is a different set again, and its
market figure is a first crossing rather than a decay constant: $\mathbf{1}^\top
e^{(A-\beta I)t}e_0$ rises to $1.082$ at $9.9$ ms before it falls, the market column sum
of $\Gamma$ being $1.310$ and so above one.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `scipy.linalg.solve_lyapunov` on `HawkesParams.excitation`; no package code owns it |
| tests | notebook §2 — the identity, and the forced-column-sum collapse |

---

## 9. The dimensionless groups

The lab is specified by four numbers, and every result is reported against them.

| group | what it controls |
| --- | --- |
| $\rho$ | how much of the flow is endogenous, and how long a cluster lasts |
| signed endogenous fraction | how much of that endogeneity carries the parent's sign |
| $\nu w$ | aggregation: how many events a window is expected to hold |
| $\nu/\beta$ | clustering: how many events fall within one kernel timescale |

The rate symbols must be kept apart. $\lambda(t)$ is the intensity **vector**;
$\bar\lambda(t) = \mathbf{1}^\top\lambda(t)$ its total, the scalar the exact scheme thins
against; $\lambda^* = (I-\Gamma)^{-1}\mu$ the **stationary** vector, which the $\rho$
ladder holds fixed; and $\nu = \mathbf{1}^\top\lambda^*$ its total, a rate in events per
second.

**$\nu w$ is a stationary-rate count, and the window's realised occupancy is not it.**
Rows are sampled at events, so what a window holds is the *Palm* count: at $w = 20.8$ ms,
$\nu w = 0.63$ against a measured $2.70$. The decomposition is $1$ — the sampling event
itself, present for a Poisson process too — plus $0.63$ from the rate, plus the rest from
the pair correlation; only the last is clustering, and nothing is length-biased, so this is
Palm sampling with a positive pair-correlation function and not the inspection paradox.
The excess shrinks with $\rho$; the distinction does not.

The signed endogenous fraction is $((p^\top\Gamma) \odot p)\cdot\lambda^*/\nu$, here
$0.3030$ against an unsigned $0.5758$. It is **not** a spectral radius: with
$P = \mathrm{diag}(p)$ and $P^2 = I$, $P\Gamma P$ is similar to $\Gamma$ and has exactly
its spectrum. Setting $p = \mathbf{1}$ recovers the unsigned fraction, which therefore
bounds it above, with equality exactly where no offspring crosses.

| leg | where |
| --- | --- |
| formulae | this entry |
| code | `unito26.lob.hawkes` — `stationary_intensity`, `signed_endogenous_fraction`, `with_cross_pressure_scaled` |
| tests | `tests/lob/test_hawkes.py::TestTheSignedContrasts` |

---

## 10. What the model does not contain

A list, so that a reader cannot take a result here for a result about markets.

* **The intensities do not read the book.** There is no queue-depletion feedback — the
  Cont, Stoikov and Talreja extension that `simulate.py`'s own docstring names. The
  *marks* do read it, and that is the mechanism behind the book's restoring force, not a
  qualification of this sentence.
* **No informed trading and no adverse selection**, which is where $I^n$'s value would
  otherwise live.
* **No queue-position economics.**
* **One excitation timescale**, the kernel being a single exponential.
* **No intraday non-stationarity**, so a tuned window is not validated against one.
* **No anchor for the price level**, so the level wanders freely and $\mathbb{E}[\Delta P^m]$
  is a per-seed random drift the size of the effects being measured.

Two questions are deferred because they cannot be asked without recorded data: whether any
regime studied here occurs in a traded market, and whether one excitation timescale
suffices for one.

---

## References

Hawkes (1971), *Biometrika* **58**(1). Hawkes and Oakes (1974), *J. Appl. Prob.*
**11**(3):493–503. Daley and Vere-Jones (2003). Meyer (1971). Papangelou (1972), *Trans.
AMS* **165**:483–506. Ogata (1981), *IEEE Trans. Inf. Theory* **27**(1):23–31, and (1988),
*JASA* **83**(401):9–27. Dassios and Zhao (2013), *ECP* **18**(62):1–13. Cont, Kukanov and
Stoikov (2014), *JFEC* **12**(1):47–88. Cont, Stoikov and Talreja (2010), *Operations
Research* **58**(3):549–563.
