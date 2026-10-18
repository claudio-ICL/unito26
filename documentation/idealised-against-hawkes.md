# The idealised book against the geometric book

The idealised placement of `example.idealisedPlacement` and the geometric placement of
`def.geometricPlacement`, driven by the same events from the same book: when the two books
part, and how far apart their mid-prices then are.

**Sources.** The statements are those of `sec.idealisedAgainstHawkes`, the last subsection
of `sec.priceFormation` in
[`tex/notes/microstructure/`](tex/notes/microstructure/); the symbols are the macros of
[`tex/include/notation.tex`](tex/include/notation.tex). This file restates them with their
proofs and maps each onto the code and the test that carry it. The lecture is
`notebooks/lectures/10-the-idealised-book-against-the-hawkes-book.ipynb`.
**If this file and the `.tex` disagree, the `.tex` wins** — fix this file.

---

## 1. The map

| notes | statement | code | tests |
| --- | --- | --- | --- |
| `assumption.twoPlacements` | the two books on one path | `coupling.RecordedEvents`, `coupling.CoupledPlacements.on`, `OrderFlowSimulator.driven_by` | `test_coupling.py::TestRecordedEvents`, `::TestThePair` |
| `def.targetOffset` | $\zeta^*_n = \phi^{\mathrm{id}}/\tau - 1 - \mathbf 1\{S^{\mathrm{id}} = \bar S\}$ | `coupling.target_offsets` | `::TestTheTargetOffsets` |
| `lemma.agreementRule` | agreement iff $\zeta_n = \zeta^*_n$, probability $\eta(1-\eta)^{\zeta^*_n}\mathbf 1\{\zeta^*_n\ge0\}$ | `coupling.agreement_probability`, `limit_event_outcomes`, `agreement_by_case` | `::TestThePair`, `::TestTheTargetOffsets` |
| `def.firstDiscrepancy`, `prop.coincidenceBeforeDiscrepancy` | $\chi^{\neq}$, the books equal before it | `CoupledPlacements.first_discrepancy`, `coupling.first_discrepancy` | `::TestTheFirstDiscrepancyAlone` |
| `prop.couplingSurvival` | $\mathbb P(\chi^{\neq} > t \mid \mathfrak F^N) = \eta^{N_{\lim}(t)}(1-\eta)^{J(t)}\mathbf 1\{\chi^\emptyset > t\}$ | `coupling.conditional_survival` | `::TestTheTargetOffsets` |
| `prop.countGeneratingFunctional`, `corol.decouplingRate` | the generating functional of the counts, the rate $c(\eta)$ | `HawkesParams.count_generating_function` | `test_hawkes.py::TestTheCountGeneratingFunction` |
| `prop.spreadPinnedAtOneTick` | the touch walks and $\chi^\partial$ | `coupling.touch_walk_exit` | `::TestTheTouchWalks` |
| `prop.touchIdentity`, `corol.touchIdentityUnderTheAssumption`, `prop.distanceDecomposition` | the touch identity and the three terms of the distance | `coupling.distance_terms` (`ImbalanceMismatch`, `TouchSizeMismatch`, `DepthMismatch`, `IdealisedDepthMismatch`) | `::TestTheDistance` |
| `prop.geometricContribution`, `corol.thinnedImbalance` | $e^{\mathrm{geo}}_n$ under the geometric placement | `SessionStatistics` (`OrderFlowContribution`) on the geometric session | `::TestTheDistance` |
| `prop.geometricWithdrawalContribution` | $e^{\mathrm{geo}}_n$ of a withdrawal | the same | `::TestTheDistance` |
| `corol.geometricExhaustion`, `remark.depthBalance` | the depth balance and the first empty side | — | — |
| `lemma.withdrawalAgreement`, `prop.couplingSurvivalWithWithdrawals` | a withdrawal agrees with probability $S^{1}/S(\tau\mathbb N)$ | `coupling.touch_shares`, `coupling.conditional_survival` | `::TestTheTouchShares` |
| `prop.stationaryDistanceRate` | the rate of the distance under H0–H2 | — | — |

`touch_walk_exit` moves the walks at withdrawals too; the notes define the walks without
withdrawals, where the two agree.

---

## 2. Setting

The order flow is that of `def.orderFlowProcess`, types numbered as in the notes: 1, 2 the
market buy and sell, 3, 4 the limit buy and sell, 5, 6 the withdrawals from the bid and the
ask. (`EventType` numbers them from 0.) An opening book has both sides occupied and
satisfies part *iii.* of `assumption.idealisedBook`. The **idealised book** is folded from it
by the messages of `example.idealisedPlacement`, orders of one share; the **geometric book**
by those of `def.geometricPlacement`, with the sizes $q_n$ of the flow. Superscripts
$\mathrm{id}$ and $\mathrm{geo}$ name the book. A quantity indexed by $T_n$ is read after the
$n$-th event; $T_0 = 0$ is the opening book.

$\mathfrak F^N$ is the $\sigma$-algebra of the arrival times and types. The idealised
placement draws nothing, so the idealised book is $\mathfrak F^N$-measurable. $\chi^\emptyset$
is the first arrival time at which the idealised placement would empty a side
(`AssumptionBreach`); the idealised book exists on $[0, \chi^\emptyset)$.

**The floor.** `_limit_price` returns `max(1, price)`, as the footnote of
`def.geometricPlacement` says. A floored limit buy sits at one tick, behind the best bid
unless the best bid is at one tick, where it joins it. Everything below that reads a limit
price assumes the best bid of either book above one tick.

---

## 3. The first discrepancy

Orders of one share, no withdrawals: $\mu_5 = \mu_6 = 0$ and rows and columns 5, 6 of $A$
null, so those types carry no event almost surely and the path is a Hawkes process on the
four order types (on which $\mu > 0$, as `thm.stationarity` asks).
$N_{\lim} := N_3 + N_4$, $\lambda^*_{\lim} := \lambda^*_3 + \lambda^*_4$.

**Target offset** (`def.targetOffset`). For a limit event before $\chi^\emptyset$,

$$\zeta^*_n := \frac{\phi^{\mathrm{id}}_{T_n-}}{\tau} - 1 - \mathbf 1\{S^{\mathrm{id}}_{T_n-} = \bar S\},$$

$S^{\mathrm{id}}$ the size at the best quote of the order's side. It is the offset at which
`eq.limitPrice` prices the order where the idealised placement does: at the best quote when
it holds less than $\bar S$, one tick inside it when it holds $\bar S$. It is $-1$ exactly at
a full best quote facing a spread of one tick, where the idealised order trades.

**Agreement rule** (`lemma.agreementRule`). If the books coincide before
$T_n < \chi^\emptyset$, they coincide after the event iff it is a market order, or a limit
order with $\zeta_n = \zeta^*_n$. Given $\mathfrak F^N$ and the past offsets, a limit event
agrees with probability $\eta(1-\eta)^{\zeta^*_n}\mathbf 1\{\zeta^*_n \ge 0\}$.

| book before, $\phi = k\tau$ | idealised order | agrees iff | probability |
| --- | --- | --- | --- |
| market, any | one share at the opposite best | always | $1$ |
| limit, $S^d < \bar S$ | joins the best quote | $\zeta_n = k-1$ | $\eta(1-\eta)^{k-1}$ |
| limit, $S^d = \bar S$, $k\ge2$ | one tick inside, a new best of one share | $\zeta_n = k-2$ | $\eta(1-\eta)^{k-2}$ |
| limit, $S^d = \bar S$, $k=1$ | trades one share at the opposite best | never | $0$ |

*Proof.* The book before the event satisfies the assumption (`example.idealisedPlacement`).
A market buy is $(T_n, 1, \infty, +1)$ under one placement and a limit buy of one share at
$P^a$ under the other, whose market part is its whole size (`prop.decompositionOfLimitOrder`);
the ask holds at least one share, so both trade one share there and rest nothing. For a
limit order of direction $d$ with idealised price $\tilde p_n$,
$d(p_n - \tilde p_n) = \tau(\zeta^*_n - \zeta_n)$; equal offsets give the same message.
Otherwise the geometric order rests one share at $p_n$ on side $d$, while the idealised one
rests at $\tilde p_n \ne p_n$ on side $d$ ($\zeta^* \ge 0$) or acts on side $-d$
($\zeta^* = -1$): the size at $p_n$ differs by one. The offsets are i.i.d. and independent of
the flow. $\square$

The case split is exhaustive: part *iii.* caps a touch at $\bar S$. Equality is of the
aggregated books, which is what `_signed_levels` compares and all that either placement reads.

**First discrepancy** (`def.firstDiscrepancy`). $\chi^{\neq}$ is the first $T_n < \chi^\emptyset$
after which the books differ at some price, and $\chi^\emptyset$ if there is none. Stopping at
the breach is what makes $\chi^{\neq}$ defined on the whole space.

**Coincidence** (`prop.coincidenceBeforeDiscrepancy`). The books, and their mid-prices,
coincide on $[0, \chi^{\neq})$, where the geometric book satisfies the assumption;
$\chi^{\neq}$ is the first limit event before $\chi^\emptyset$ with $\zeta_n \ne \zeta^*_n$.
*Proof.* Induction on $n$ with the agreement rule. $\square$
At $\chi^{\neq}$ the mids may still agree (an order behind the touch), so $\chi^{\neq}$ is at
most the first time the mids differ.

**Conditional survival** (`prop.couplingSurvival`). With $J(t)$ the sum of the target offsets
of the limit events of $(0,t]$ before $\chi^\emptyset$, $J(t) = \infty$ if one is $-1$,

$$\mathbb P(\chi^{\neq} > t \mid \mathfrak F^N) = \eta^{N_{\lim}(t)}(1-\eta)^{J(t)}\mathbf 1\{\chi^\emptyset > t\},
\qquad (1-\eta)^\infty := 0,\ 0^0 := 1.$$

*Proof.* $\{\chi^{\neq} > t\} = \{\chi^\emptyset > t\} \cap \bigcap_{n}\{\zeta_n = \zeta^*_n\}$
over the limit events of $(0,t]$. The first event and every $\zeta^*_n$ are
$\mathfrak F^N$-measurable; the offsets are i.i.d. and independent of $\mathfrak F^N$
(`def.geometricPlacement`). The conditional probability is the product. $\square$

In the code, `driven_by` draws the marks on a generator of their own, the size before the
offset at every limit event even when every size is one. With the plain constructor events and
marks share a generator, consumed in an interleaved order; each draw is fresh, so the joint
law is still the product law.

Consequences (`remark.couplingAtUnitOffsetParameter`):
$\eta^{N_{\lim}}\mathbf 1\{\chi^\emptyset > t, J = 0\} \le \mathbb P(\chi^{\neq} > t\mid\mathfrak F^N) \le \eta^{N_{\lim}}$;
at $\eta = 1$, $\chi^{\neq}$ is $\mathfrak F^N$-measurable, the first limit event with
$\zeta^* \ne 0$; and $\mathbb P_\eta(\chi^{\neq} > t) \to \mathbb P(J(t) = 0, \chi^\emptyset > t)$
as $\eta \uparrow 1$ by bounded convergence. Exercise `exercise.limitOrdersBeforeDiscrepancy`:
$\mathbb P(N_{\lim}(\chi^{\neq}-) \ge k) \le \eta^k$, so
$\mathbb E[N_{\lim}(\chi^{\neq}-)] \le \eta/(1-\eta)$.

### The generating functional of the counts

`prop.countGeneratingFunctional`. For piecewise-constant $x : [0,\infty) \to [0,1]^{d_E}$ let

$$\psi'(r) = -\beta\psi(r) + A^\top\big(x(r)\circ e^{\psi(r)} - \mathbf 1\big), \qquad \psi(0) = 0 .$$

Then $\psi$ exists on $[0,\infty)$ in the box $[-\Gamma^\top\mathbf 1, 0]$, and

$$\mathbb E\Big[\prod_{s < T_n \le s+h} x_{E_n}(s+h-T_n)\,\Big|\,\mathfrak F_s\Big]
= \exp\Big(\psi(h)^\top Z(s+) + \int_0^h \mu^\top\big(x(r)\circ e^{\psi(r)} - \mathbf 1\big)\,dr\Big).$$

If $\rho < 1$, the process is stationary and $x = \mathbf 1$ on $[h,\infty)$, the unconditional
expectation is $\exp\int_0^\infty \mu^\top(x\circ e^\psi - \mathbf 1)\,dr$, a convergent integral.

$r$ is the time left to the end of the window; $\psi_{e'}$ belongs to the exciting type, hence
$A^\top$ under the convention of `remark.indexOrder`.

*Proof.* Box: on $\{\psi_e = 0\}$ the field is $(A^\top(x\circ e^\psi - \mathbf 1))_e \le 0$; on
$\{\psi_e = -(\Gamma^\top\mathbf 1)_e\}$ it is $\ge \beta(\Gamma^\top\mathbf 1)_e - (A^\top\mathbf 1)_e = 0$.
Martingale: with $r(u) = s + h - u$,
$M_u = \prod_{s<T_n\le u} x_{E_n}(r(T_n))\,\exp\big(\psi(r(u))^\top Z(u+) + \int_0^{r(u)}\mu^\top(x\circ e^\psi - \mathbf 1)\big)$.
Between events $\frac{d}{du}\log M = -\psi'^\top Z - \beta\psi^\top Z - \mu^\top(x\circ e^\psi - \mathbf 1)$;
at a type-$e$ event $M$ is multiplied by $x_e e^{\psi_e}$. Compensating with $\lambda = \mu + AZ$,
the $\mu$ terms cancel and the drift is $M(-\psi' - \beta\psi + A^\top(x\circ e^\psi - \mathbf 1))^\top Z = 0$.
$M \in [0,1]$, so it is a martingale; $M_{s+h}$ and $M_s$ are the two sides.
Stationary case: start at $s - v$ with weight one on $(s-v, s]$; for $r \ge h$,
$\psi' \ge K^\top\psi$, and $K^\top$ is Metzler, so $0 \ge \psi(r) \ge e^{K^\top(r-h)}\psi(h) \to 0$
exponentially (`prop.hurwitzCriterion`); $\mathbb E\exp(\psi(h+v)^\top Z) \to 1$ by bounded
convergence, the law of $Z$ not depending on $v$. $\square$

The proof uses the intensity alone. The notes state the cluster representation
(`prop.clusterRepresentation`) only for the stationary version, so a cluster argument for the
process with no past, or from a state $z$, would rest on something the notes do not state.
The docstring of `count_generating_function` says "by the cluster representation"; the
martingale is the argument the notes give. Exercise `exercise.meanFromGeneratingFunction`
recovers `eq.forwardMeanCounts` by differentiating at $x = \mathbf 1$: the derivative of
$\psi(h)$ in the direction $e_{e'}$ is $\Phi(h)^\top A^\top e_{e'}$.

**The rate** (`corol.decouplingRate`). Let $\rho < 1$, $x = \mathbf 1 - (1-\eta)\mathbf 1_{\lim}$.
Then $\psi$ is non-increasing to a zero $\psi_\infty$ of the field,
$\frac1h\log\mathbb E[\eta^{N_{\lim}(s+h) - N_{\lim}(s)}\mid\mathfrak F_s] \to -c(\eta)$ with
$c(\eta) := -\mu^\top(x\circ e^{\psi_\infty} - \mathbf 1)$, and
$c(\eta) = (1-\eta)\lambda^*_{\lim} + O((1-\eta)^2)$.

*Proof.* $v = \psi'$ solves $v' = DF(\psi)v$, a Metzler system, from $v(0) = A^\top(x - \mathbf 1) \le 0$,
so $v \le 0$. Expansion: $\psi' \ge K^\top\psi - (1-\eta)A^\top\mathbf 1_{\lim}$ gives
$\psi_\infty \ge (1-\eta)K^{-\top}A^\top\mathbf 1_{\lim} = O(1-\eta)$, so $\psi_\infty$ is the
implicit-function branch through $0$ ($DF(0) = K^\top$ invertible), with derivative
$K^{-\top}A^\top\mathbf 1_{\lim}$; then
$\dot c = \mu^\top(\mathbf 1_{\lim} - K^{-\top}A^\top\mathbf 1_{\lim}) = -\beta\mu^\top K^{-\top}\mathbf 1_{\lim}
= \mathbf 1_{\lim}^\top(I-\Gamma)^{-1}\mu = \lambda^*_{\lim}$. $\square$

### The spread pinned at one tick

Touch walks $\Upsilon^b = S^{b,1}_0 + N_3 - N_2$, $\Upsilon^a = S^{a,1}_0 + N_4 - N_1$;
$\chi^\partial$ the first time either leaves $[1,\bar S]$ (`eq.touchWalks`).

`prop.spreadPinnedAtOneTick`, opening spread one tick:

1. on $[0,\chi^\partial)$ the idealised book keeps its best prices, its touches are the walks,
   every limit event has $\zeta^* = 0$, and $\chi^\partial \le \chi^\emptyset$;
2. on $\{\chi^\partial > t\}$, $\mathbb P(\chi^{\neq} > t\mid\mathfrak F^N) = \eta^{N_{\lim}(t)}$, and
   $0 \le \mathbb E[\eta^{N_{\lim}(t)}] - \mathbb P(\chi^{\neq} > t) \le \mathbb E[\eta^{N_{\lim}(t)}; \chi^\partial \le t]$;
3. at an exit through $\bar S + 1$, $\chi^{\neq} \le \chi^\partial$ for every $\eta$ (the exit event
   has $\zeta^* = -1$); at $\eta = 1$, $\chi^{\neq} \ge \chi^\partial$, with equality there.

*Proof.* Induction before $\chi^\partial$: a market buy finds $\Upsilon^a \ge 2$, a limit sell
finds $\Upsilon^a \le \bar S - 1$ at one tick and has $\zeta^* = 1 - 1 - 0 = 0$. The rest follows
from the survival formula. $\square$

In this regime $\mathbb E[\eta^{N_{\lim}}]$ is the generating function above, and it decays
at the rate $c(\eta)$.

---

## 4. The distance between the mid-prices

The geometric book now carries the sizes of the flow. $\Delta_n X := X_{T_n} - X_{T_{n-1}}$.

**Outer size** (`def.outerSize`).
$\hat S^b_n = S^{b,1}_{T_{n-1}}$ if the bid rises, $S^{b,1}_{T_n}$ if it falls, $0$ otherwise;
$\hat S^a_n = S^{a,1}_{T_n}$ if the ask rises, $S^{a,1}_{T_{n-1}}$ if it falls, $0$ otherwise:
the size at the outer of the two values of the best price, read where that value is best.

**Touch identity** (`prop.touchIdentity`). On any book with both sides occupied before and
after the event, with $e_n = e^b_n + e^a_n$ split as in the proof of
`prop.signedSizeContribution`,

$$e^b_n - \Delta_n S^{b,1} = \operatorname{sgn}(\Delta_n P^b)\,\hat S^b_n, \qquad
e^a_n + \Delta_n S^{a,1} = \operatorname{sgn}(\Delta_n P^a)\,\hat S^a_n,$$

and over a window on which both sides stay occupied

$$\mathrm{OFI}_{t,w} - (S^{b,1}_t - S^{b,1}_{t-w}) + (S^{a,1}_t - S^{a,1}_{t-w})
= \sum_{t-w<T_n\le t}\big(\operatorname{sgn}(\Delta_nP^b)\hat S^b_n + \operatorname{sgn}(\Delta_nP^a)\hat S^a_n\big).$$

*Proof.* Bid unchanged: $e^b_n = \Delta_n S^{b,1}$. Rising: $e^b_n = S^{b,1}_{T_n}$, left side
$S^{b,1}_{T_{n-1}}$. Falling: $e^b_n = -S^{b,1}_{T_{n-1}}$, left side $-S^{b,1}_{T_n}$. Ask
mutatis mutandis; sum and telescope. $\square$

The right-hand side is a sum of moves in ticks, each weighted by its outer size per tick. Under
`assumption.idealisedBook` every move is one tick onto or off a queue of $\bar S$, the weight is
$\bar S$, and the identity is `eq.idealisedUpdate` with `eq.idealisedResidual`
(`corol.touchIdentityUnderTheAssumption`; the step is the one of `exercise.idealisedUpdate`).
On the idealised book the depth sum of `distance_terms`, `IdealisedDepthMismatch`, is
identically zero.

**Contributions under the geometric placement** (`prop.geometricContribution`). Both sides
occupied before and after:
a market buy contributes $q_n \wedge S^{a,1}_{T_{n-1}}$, a market sell
$-(q_n \wedge S^{b,1}_{T_{n-1}})$, a limit order $\varpi_{E_n}q_n\mathbf 1\{\zeta_n \le \phi_{T_n-}/\tau - 1\}$.
*Proof.* A market buy that leaves the ask gives $-\Delta_n S^{a,1} = q_n$, one that clears it
gives $S^{a,1}_{T_{n-1}}$ however far it walks. A limit buy rests in full; behind the bid it
contributes zero, at it $\Delta_n S^{b,1} = q_n$, above it $S^{b,1}_{T_n} = q_n$. $\square$

`corol.thinnedImbalance`: with unit sizes and no withdrawals,
$\mathrm{OFI}^{\mathrm{geo}}_{t,t} - \mathrm{OFI}^{\mathrm{id}}_{t,t} = -\sum \varpi_{E_n}$
over the limit events placed behind their touch; at $\eta = 1$ both are $\varpi^\top N(t)$
(`test_at_depth_decay_one_with_unit_sizes_the_imbalances_agree`).

**Depth** (`prop.depthAccumulates`). No withdrawals, no empty side: the whole bid of the
geometric book is the opening bid plus the limit buys minus the market sells, and the increment
over $(s, s+h]$ has conditional mean
$\bar q(e_3 - e_2)^\top(h\lambda^* + A\Phi(h)(Z(s+) - m))$ by `eq.forwardMeanCountsDeviation`.
When $\lambda^*_3 > \lambda^*_2$ the geometric book thickens at a constant mean rate; the
idealised book caps every price at $\bar S$, so the same excess moves its best prices.

**Decomposition** (`prop.distanceDecomposition`). For $t < \chi^\emptyset$ and no empty side of
the geometric book,

$$\frac{2\bar S}{\tau}(P^{m,\mathrm{geo}}_t - P^{m,\mathrm{id}}_t)
= \underbrace{\mathrm{OFI}^{\mathrm{geo}}_{t,t} - \mathrm{OFI}^{\mathrm{id}}_{t,t}}_{\texttt{ImbalanceMismatch}}
- \underbrace{\big[(S^{b,1,\mathrm{geo}}_t - S^{b,1,\mathrm{id}}_t) - (S^{a,1,\mathrm{geo}}_t - S^{a,1,\mathrm{id}}_t)\big]}_{\texttt{TouchSizeMismatch}}
- \underbrace{\sum_{T_n \le t}\Big[\operatorname{sgn}(\Delta_nP^{b,\mathrm{geo}})\big(\hat S^{b,\mathrm{geo}}_n - \bar S\tfrac{|\Delta_nP^{b,\mathrm{geo}}|}{\tau}\big) + \text{ask}\Big]}_{\texttt{DepthMismatch}} .$$

*Proof.* The touch identity on the geometric book, with $\bar S|\Delta_nP|/\tau$ added and
subtracted in each signed term, minus the corollary on the idealised book; the opening books
coincide. $\square$

With its sign the touch-size term is $(2\bar S/\tau)(\varepsilon^{\mathrm{geo}}_{t,t} - \varepsilon^{\mathrm{id}}_{t,t})$,
$\varepsilon^{\mathrm{geo}}$ being `eq.idealisedResidual` on the geometric book. The depth term
vanishes on every move one tick onto or off a queue of $\bar S$.

**Mirror** (`prop.mirrorSymmetry`). Direction-symmetric specification, starting state with
$\Sigma z = z$, opening book symmetric about $P^m_0$. With $G_t$ the event that, on the path
and on its mirror $(T_n, \Sigma(E_n))$ with the same marks, no side of either book is exhausted
and no limit price is floored, $(P^{m,\mathrm{geo}}_t - P^{m,\mathrm{id}}_t)\mathbf 1_{G_t}$ has a
law symmetric about zero.
*Proof.* $p \mapsto 2P^m_0 - p$ maps the grid to itself and exchanges the sides; matching,
both placements and the size-weighted withdrawal draw commute with it, the type replaced by
its mirror. The mirror has intensity $\Sigma\lambda = \mu + A\Sigma Z$, so it has the law of the
path. $\square$
Pathwise, a withdrawal of the mirror must draw the reflected level; the simulator draws in the
order of `levels_map`, so its own mirrored run agrees with the reflection in law, not path by
path.

**Second moments** (`prop.distanceSecondMoments`). Under the law conditional on no
exhaustion on $(0,t]$, let $\gamma_t = \mathrm{Cov}(P^{m,\mathrm{geo}}_t, \varpi^\top N(t))/(\tau\,\mathrm{Var}(\varpi^\top N(t)))$,
$\xi_t = (P^{m,\mathrm{geo}}_t - P^m_0)/\tau - \gamma_t\varpi^\top N(t)$ and
$Q_t = (\gamma_t - 1/(2\bar S))^2\mathrm{Var}(\varpi^\top N(t)) + \mathrm{Var}(\xi_t)$. Then
$|\mathrm{Var}((P^{m,\mathrm{geo}}_t - P^{m,\mathrm{id}}_t)/\tau) - Q_t| \le 1 + 2\sqrt{Q_t}$.
*Proof.* $\mathrm{OFI}^{\mathrm{id}}_{t,t} = \varpi^\top N(t)$, so the idealised displacement in
ticks is $\varpi^\top N(t)/(2\bar S) + r_t$, $|r_t| \le 1$. The distance is $X_t - r_t$ with
$\mathrm{Var}(X_t) = Q_t$, and Cauchy–Schwarz bounds the rest. $\square$
The idealised orders have size one whatever the sizes of the flow, so the proposition holds for
any size law of the geometric book.

**Withdrawal contributions** (`prop.geometricWithdrawalContribution`). A withdrawal from the
bid at the drawn price $p_n$ contributes
$\varpi_{E_n}(q_n \wedge S^b_{T_n-}(p_n))\mathbf 1\{p_n = P^b_{T_n-}\}$, both sides occupied
before and after. *Proof.* Behind the bid nothing moves; at it, either the bid stays and
$e^b_n = \Delta_n S^{b,1} = -v_n$, or the queue empties and $e^b_n = -S^{b,1}_{T_{n-1}} = -v_n$,
$v_n = q_n \wedge S^b(p_n)$. $\square$ With unit sizes, `eq.thinnedImbalance` holds with the
withdrawals drawn behind the touch added to the sum.

**First empty side** (`corol.geometricExhaustion`). Without withdrawals, or with unit sizes, the
size on each side of the geometric book is read off the events and the sizes alone (with unit
sizes a withdrawal removes one share wherever it is drawn), so the first time a side empties is
the same at every $\eta$. With unit sizes, $\rho < 1$ and
$\lambda^*_3 \le \lambda^*_2 + \lambda^*_5$ the bid empties in finite time almost surely.
*Proof.* $u = e_3 - e_2 - e_5$; the bid stays occupied only while
$u^\top N > -S^b_0(\tau\mathbb N)$. The functional CLT of Bacry, Delattre, Hoffmann and Muzy
(2013) gives $(N(ns) - ns\lambda^*)/\sqrt n \Rightarrow$ Brownian motion of covariance $D$ in
Skorokhod space; with $u^\top\lambda^* \le 0$ and the portmanteau theorem on the open set
$\{\inf_{s\le1} f < -y\}$, the probability of emptying by $n$ has lower limit at least
$\mathbb P(\inf_{s \le 1}\sqrt{u^\top Du}\,W_s < -y) \to 1$ as $y \downarrow 0$. $\square$

**Depth balance** (`remark.depthBalance`). The truncation $q_n \wedge S(p_n)$ of withdrawals is
the only book-dependent term of the balance. If $\lambda^*_3 > \lambda^*_2 + \lambda^*_5$ the
side is bounded below by a walk of linearly growing mean: no stationary depth. With unit sizes
and $\le$, the bid empties. A stationary depth needs $\lambda^*_3 < \lambda^*_2 + \lambda^*_5$
and sizes not all one, the truncation absorbing the excess of withdrawals, the more often the
thinner the book. The calibration of `config.resilient_order_flow_params()` balances in size
this way, and holds with `resilient_mark_params()` sizes, not with unit sizes.

---

## 5. With withdrawals

**Agreement at a withdrawal** (`lemma.withdrawalAgreement`). Unit sizes, books equal before
$T_n < \chi^\emptyset$: a withdrawal keeps them equal iff the size-weighted draw selects the
best price of its side, with probability
$S^{\mathrm{id}}_{T_n-}/S^{\mathrm{id}}_{T_n-}(\tau\mathbb N) \le 1/\ell$, $\ell$ the number of
levels of the side. *Proof.* The geometric withdrawal cancels $1\wedge S(p_n) = 1$ share at
$p_n$ (`_withdrawal`), the idealised one a share at the touch; the messages coincide iff $p_n$
is the touch, including when the touch holds one share and both empty it. Otherwise the size at
the touch differs by one. Every level behind the touch holds $\bar S \ge S^{\mathrm{id}}$, which
gives the bound. $\square$

**Survival** (`prop.couplingSurvivalWithWithdrawals`). Unit sizes:
$\mathbb P(\chi^{\neq} > t\mid\mathfrak F^N) = \eta^{N_{\lim}(t)}(1-\eta)^{J(t)}\mathbf 1\{\chi^\emptyset > t\}\prod S^{\mathrm{id}}/S^{\mathrm{id}}(\tau\mathbb N)$
over the withdrawals of $(0,t]$ before $\chi^\emptyset$. *Proof.* Chain rule: given
$\mathfrak F^N$ and the earlier marks, on coincidence before event $n$ the books are the
idealised one, $\mathfrak F^N$-measurable, and event $n$ agrees with the factor of its type.
$\square$ The marks of each event (size, offset, level) are drawn afresh, and the level draw is
"otherwise independent of the past" (`def.geometricPlacement` *iii.*). In a deep book the books
part at about the first withdrawal.

**The idealised book drifts, its mid does not.** While the idealised spread exceeds one tick,
the position $S^{b,1,\mathrm{id}} + \bar S P^{b,1,\mathrm{id}}/\tau$ moves by
$(e_3 - e_2 - e_5)^\top\Delta N$ (touch identity with $\hat S = \bar S$, one tick), of mean
$h(\lambda^*_3 - \lambda^*_2 - \lambda^*_5) + O(1)$. When this is negative the bid falls, the
ask rises, and the spread opens until $\chi^\emptyset$. Yet `eq.idealisedMidAsCount`:
$(P^{m,\mathrm{id}}_t - P^{m,\mathrm{id}}_0)/\tau = \varpi^\top N(t)/(2\bar S) + \varepsilon^{\mathrm{id}}_{t,t}/\tau$,
$|\varepsilon^{\mathrm{id}}_{t,t}/\tau| \le 1$, at every spread, for $t < \chi^\emptyset$.

**The stationary rate** (`prop.stationaryDistanceRate`). $\mathcal B_t$ is the geometric book
translated to put its best bid at zero, $\mathcal Y_t = (Z(t), \mathcal B_t)$; $\delta_e(y)$ the
move of the geometric mid in ticks at a type-$e$ event in state $y$ (random through the marks,
expectation $\mathbb E^{\mathrm{mk}}$); $\bar\delta(y) = \sum_e\lambda_e(z)\mathbb E^{\mathrm{mk}}\delta_e(y)$;
$\bar\varpi = (I-\Gamma)^{-\top}\varpi$, the expected signed pressure of the cluster of an event,
with $\varpi^\top D\varpi = \sum_e \lambda^*_e\bar\varpi_e^2$.

- H0, translation invariance: no side of the geometric book is ever empty and no limit price
  meets the floor, so every message depends on the book through $\mathcal B$ alone and
  $\mathcal Y$ is Markov. The reference price $p_0$ of the footnote of `def.geometricPlacement`
  (`OrderFlowSimulator.reference_price`) and the floor `max(1, price)` are fixed outside the
  book and break it.
- H1, stationarity of $\mathcal Y$.
- H2, solvability: $g \in L^2$ with $\mathcal L g = -\bar\delta$, and corrected moves
  $\tilde\delta_e(y) = \delta_e(y) + g(y'_e) - g(y)$ with
  $\mathbb E[\sum_e\lambda_e\mathbb E^{\mathrm{mk}}\tilde\delta_e^2] < \infty$.

Direction-symmetric, $\rho < 1$, idealised book opening at $0$ from a book satisfying part
*iii.*; $\gamma_t$, $\xi_t$ as in `prop.distanceSecondMoments` with the geometric mid replaced
by its increment; $\Delta_t = (P^{m,\mathrm{geo}}_t - P^{m,\mathrm{geo}}_0)/\tau - \varpi^\top N(t)/(2\bar S)$.
Then

$$\gamma_t \to \gamma = \frac{\mathbb E[\sum_e\lambda_e(Z(0))\bar\varpi_e\mathbb E^{\mathrm{mk}}\tilde\delta_e(\mathcal Y_0)]}{\varpi^\top D\varpi},\qquad
\frac{\mathrm{Var}(\xi_t)}{t} \to \sigma_\perp^2 = \mathbb E\Big[\sum_e\lambda_e(Z(0))\,\mathbb E^{\mathrm{mk}}(\tilde\delta_e - \gamma\bar\varpi_e)^2\Big],$$

$$\frac{\mathrm{Var}(\Delta_t)}{t} \to \Big(\gamma - \frac{1}{2\bar S}\Big)^2\varpi^\top D\varpi + \sigma_\perp^2,$$

and on $\{t < \chi^\emptyset\}$ the distance of the increments of the two mids, in ticks, is
within one of $\Delta_t$. $\sigma_\perp^2 \ge \mathbb E[\sum_e\lambda_e\mathrm{Var}^{\mathrm{mk}}\tilde\delta_e]$.

*Proof.* Dynkin: $\Delta P^{m,\mathrm{geo}}/\tau = M^{\mathrm{geo}}_t + g(\mathcal Y_0) - g(\mathcal Y_t)$,
$M^{\mathrm{geo}}$ jumping by $\tilde\delta_{E_n}$. By `eq.countIncrementIdentity` and
$\varpi^\top\lambda^* = 0$, $\varpi^\top N(t) = \bar\varpi^\top(M(t) - M(0)) - \varpi^\top\Gamma(I-\Gamma)^{-1}(Z(t) - Z(0))$.
The martingales jump together; their covariation and $\langle M^{\mathrm{geo}}\rangle$ have
expectations $t$ times the stationary rates (H1); the rest is bounded in $L^2$ (H1, H2,
`thm.lyapunov`) and contributes $O(\sqrt t)$. $\Delta_t = \xi_t + (\gamma_t - 1/(2\bar S))\varpi^\top N(t)$
with uncorrelated terms. $\square$

Ergodicity, which the scratch derivation assumed, is not used: only stationary expectations
enter. The rate is a property of the geometric book alone; the idealised book enters only
through `eq.idealisedMidAsCount`. $\mathrm{Var}(\xi_t) = o(t)$ — an effective impact alone —
needs $\tilde\delta_E = \gamma\bar\varpi_E$ almost surely. H1 and H2 are not proved for the
geometric book, whose state space is a space of books; the proposition fixes the form of the
answer.

`remark.withdrawalsDeleted`: deleting the withdrawal coordinates without choosing
$(\Gamma, \lambda^*)$ anew by `eq.baselineFromTarget` may leave $\lambda^*_3 > \lambda^*_2$; the
geometric book thickens (`prop.depthAccumulates`), at $\eta = 1$ its best queues are walks of
positive drift and its mid stops once neither is cleared again, and the distance grows at the
idealised rate $\varpi^\top D\varpi/(2\bar S)^2$. The comparison then measures accumulation, not
placement.

`remark.twoRegimes` compares the two settings: without withdrawals the coupling is informative
and, at $\eta = 1$ with unit sizes, exact in the imbalance, but the geometric book has no
stationary depth and no effective impact as a limit; with withdrawals the coupling parts at
about the first withdrawal, the geometric depth may be stationary, and
`prop.stationaryDistanceRate` gives the rate as a property of the geometric book.
