# The idealised flow against the Hawkes flow

The idealised placement of `example.idealisedPlacement` and the geometric placement of
`def.geometricPlacement`, driven by the same events from the same book: when their
mid-prices first differ, and how far apart they are after.

**Sources.** The statements are those of `sec.idealisedAgainstHawkes`, the last subsection
of `sec.priceFormation` in [`tex/notes/microstructure/`](tex/notes/microstructure/); the
symbols are the macros of [`tex/include/notation.tex`](tex/include/notation.tex). This file
restates them with their proofs, keeps as working material the derivations behind the
unnumbered paragraphs that close two of its subsubsections, summarises the numerical evidence,
lists what the notes predict, and maps each statement onto the code and the
test that carry it. The lecture is
`notebooks/lectures/10-the-idealised-book-against-the-hawkes-book.ipynb`.
**If this file and the `.tex` disagree, the `.tex` wins** — fix this file.

---

## 1. The map

Tests are in `tests/lob/test_coupling.py`; functions are in `unito26.lob.coupling` unless
another module is named.

| notes | statement | code | tests |
| --- | --- | --- | --- |
| `def.threeBooks`, `assumption.balancedFlow` | the books CKS, haw-1, haw-q on one path; balance; the event $G$ | `RecordedEvents.drawn`, `.replay`, `CoupledFlows.on` (`.breach`), `simulate.OrderFlowSimulator.driven_by`; `config.balanced_order_flow_params`, `.unit_mark_params`, `.uncertain_size_mark_params`, `.uncertain_size_unit` | `TestTheSimulatorStream`, `TestRecordedEvents`, `TestTheFrozenRecords`, `TestThePair`, `TestTheStop` |
| `eq.sideSize`, `remark.wholeBookImbalance` | a side of haw-1 holds $S^b_0(\tau\mathbb N) + (\varpi^b)^\top N(t)$, $S^b_0(\tau\mathbb N) = (L-1)\bar S + S^{b,1}_0$; the whole-book imbalance is $S^{b,1}_0 - S^{a,1}_0 + \varpi^\top N(t)$ | `side_vector` | `TestTheSideVectors` |
| `def.partingTime`, `lemma.oneBestPrice`, `corol.partingAtOneQuote`, `exercise.partingAtOneQuote` | $\chi$; one best price per event; exactly one differs at $\chi$ | `CoupledFlows.first_price_discrepancy`, `.parting` (`Parting`, `Mover`); `first_price_discrepancy` | `TestTheParting` |
| `prop.partingProbability` | the probability that an event parts the mid-prices | — | — |
| `corol.quietBook`, `def.firstMoves` | at one tick a best price moves exactly when the last share of a touch is taken; the quiet books; the first moves $\psi^{\mathrm{CKS}}$, $\psi^{\mathrm{haw}\text{-}1}$ | `first_price_moves` (`FirstMoves`), `touch_walks` | `TestTheFirstMoves`, `TestTheParting` |
| `eq.touchWalks`, `prop.cksTouchWalks` | the touches of CKS from the touch walks and their running maximum; $\psi^{\mathrm{CKS}}$ a drawdown | `cks_touch_walks`, `cks_first_move` | `TestTheCKSTouchWalks` |
| `prop.hawkesTouch`, `eq.hawkesTouch` | the touches of haw-1 before $\psi^{\mathrm{haw}\text{-}1}$ from the counts and the draws; $\psi^{\mathrm{haw}\text{-}1}$ the first time one reaches zero | `touch_walks` | `TestTheFirstMoves` |
| `prop.fluidTouch`, `eq.countsFromNoPast`, `exercise.fluidTouch`, `corol.twoRegimes` | the fluid touches $r^b$, $r^a$ from the opening touches, the times $s^*_b$, $s^*_a$ and $s^* = s^*_b \wedge s^*_a$, the two regimes | `fluid_touch`, `fluid_emptying_time` (`OpeningTouch`) | `TestTheFluidTouch` |
| heuristics after `corol.twoRegimes` | $\psi^{\mathrm{CKS}}$ at the diffusive scale $\bar S^2/(\varpi^b)^\top D\varpi^b$, the side at $L^2$ times it | `diffusive_scale` | — |
| `def.discrepancy`, `prop.discrepancyMoments` | $\mathcal D_t$: zero before $\chi$; symmetric and bounded below when the opening touches are equal; flow and placement parts | `cks_mids`, `hawkes_mids`, `variance_split` | `TestTheMidsOnAClock`, `TestTheVarianceSplit` |
| §4 working material: outer sizes, the touch identity | the touch identity on any book | `distance_terms` (`CKSDepthMismatch` is zero) | `TestTheDistance` |
| §4 working material: the contribution of an event, the three-term decomposition | $e_n = \varpi_{E_n}\mathbf 1\{n\notin\mathcal H\}\hat q_n$; the three terms of $2\bar S\mathcal D_t/\tau$ | `distance_terms` (`ImbalanceMismatch`, `TouchSizeMismatch`, `DepthMismatch`) | `TestTheDistance` |
| §4 working material: the placement martingale | $\alpha_n$, the martingale $M^{\mathcal H}$ | `PlacementStatistics.behind_probability` (pooled by type) | `TestThePlacementStatistics` |
| §4 working material: the second-regime rate | the rate $\varpi^\top D\varpi/(2\bar S)^2$, all flow | `second_regime_rate` | `TestTheClosedForm` |
| §4 working material: H1, H2, the effective depth, the first-regime closed form | $\tilde S$ as a regression slope; the impact differences $c$; the flow and the placement rates | `PlacementStatistics.of`, `closed_form_rates(…, 0.0)` (`VarianceRates`) | `TestTheClosedForm`, `TestThePlacementStatistics` |
| §5 working material: the parting with sizes, the fluid scale with sizes | haw-q is never quiet; the fluid scale is unchanged | `CoupledFlows.on` with `uncertain_size_mark_params`, `SizeUnit` | `TestThePair` |
| §5 working material: the decomposition with sizes, what the sizes add | the size term; the conditional variance $\alpha(1-\alpha) + (1-\alpha)\mathrm{Var}\,\xi$ | `distance_terms` on haw-q; `closed_form_rates(…, size_variance)` | `TestTheDistance`, `TestTheClosedForm` |

The figures of the lecture are `visualization.mids_figure`, `touch_walks_figure`,
`first_times_figure`, `discrepancy_fan_figure`, `variance_split_figure` and
`distance_terms_figure`, checked by `TestTheFigures`.

---

## 2. Three flows on one path

**Types and symbols.** As in the notes: 1, 2 the market buy and sell, 3, 4 the limit buy
and sell, 5, 6 the withdrawals from the bid and the ask; $\varpi = (+1,-1,+1,-1,-1,+1)$.
`EventType` numbers them from 0. $D$ is the count covariance rate of `eq.flowVolatility`,
which is why the discrepancy is $\mathcal D$. $\varpi^b$, $\varpi^a$ are the side vectors
(`\sideVector`), not $u$, which is the right Perron vector; $\mathcal H$ is
the set of events placed behind, not $B$, the bid orders. $\Sigma(e)$ is the type with
which $\Sigma$ exchanges $e$.

**The three books** (`def.threeBooks`). The flow $(T_n, E_n, q_n)_{n\ge1}$ of
`def.orderFlowProcess`, with no event before time zero. The opening book has a spread of
one tick and $L$ levels per side, one on every tick; its best bid holds $S^{b,1}_0$ shares
and its best ask $S^{a,1}_0$, with $1 \le S^{b,1}_0, S^{a,1}_0 \le \bar S$, and every other
level $\bar S$. Folded from it:

- **CKS**, by the messages of `example.idealisedPlacement` made of $(T_n, E_n)$;
- **haw-1**, by those of `def.geometricPlacement` made of $(T_n, E_n, 1)$;
- **haw-q**, by those made of $(T_n, E_n, q_n)$, from the opening book with every size
  multiplied by $\bar q$.

The opening book satisfies part *iii.* of `assumption.idealisedBook`, so CKS is the book of
`example.idealisedPlacement`, along which `eq.idealisedUpdate` holds. A quantity of a book
carries its name as a superscript; a quantity indexed by $T_n$ is read after the $n$-th
event, $T_0 := 0$ the opening. $\mathfrak F^N$ is generated by the arrival times and types;
$S^b_t(\tau\mathbb N) := \sum_p S^b_t(p)$ is the size on the whole bid.

CKS draws nothing, so it is $\mathfrak F^N$-measurable. The geometric placement draws an
offset or the level of a withdrawal for each event, and haw-q a size besides; given
$\mathfrak F^N$ and the earlier draws they have the laws of `def.orderFlowProcess` and
`def.geometricPlacement`. The level of a withdrawal is represented by $U_n$, uniform on
$(0,1)$ and independent of everything else: the withdrawal takes the first level of its
side, counted from the touch outwards, at which the cumulated size exceeds $U_n$ times the
size of the side. The **mirror** of the path is $(T_n, \Sigma(E_n))_n$ with the same
$\zeta_n$, $U_n$, $q_n$. (The simulator draws the level over the levels in dict order,
which has the same law; the representation is what makes the mirror a function of the
draws.)

CKS and haw-1 differ only in where the orders go; haw-1 and haw-q only in their sizes. The
imbalance of CKS is $\varpi^\top N$ (`prop.signedSizeContribution`), so a size other than
one acts on `eq.idealisedUpdate` as an uncertainty in the observation of each order's size.

**Balance** (`assumption.balancedFlow`). The specification is direction-symmetric with
$\rho < 1$, $\lambda^*_3 = \lambda^*_2 + \lambda^*_5$ and $\lambda^*_4 = \lambda^*_1 +
\lambda^*_6$, and the opening best bid lies above one tick. $\Sigma\lambda^* = \lambda^*$,
so the two balance conditions are one.

**The event $G$.** Throughout, the notes work on the event $G$ that on the horizon, on the
path and on its mirror, no side of any of the three books is empty and no limit price meets
the floor. Every statement is made on $G$ and laws are taken on it; the conditional laws
of the draws given the path and the earlier draws are taken to be those of the definitions,
which $G$ changes by the probability of its complement. $G$ is invariant under the exchange
of the path with its mirror, by its definition. Where this matters:

- the variance split (*iv.* of `prop.discrepancyMoments`) needs an $\mathfrak
  F^N$-measurable conditioning event. With unit sizes the no-empty-side part of $G$ is one
  (the sides of haw-1 are `eq.sideSize`, CKS is a function of the path); the floor part
  depends on the offsets and is not, and *iv.* holds exactly on the first part alone. With
  random sizes the emptying of a side of haw-q depends on the sizes, and the split for
  haw-q holds on the draws that keep its sides occupied — in the code, on the runs kept;
- `CoupledFlows` stops before the first event that would empty a side of either book and
  records it in `.breach`; `hawkes_mids` runs past an empty side, as the simulator does,
  and reads NaN while a side is empty.

**In the code.** `RecordedEvents.drawn(process, horizon)` records one path; `.replay()`
gives a `Replay` that yields it again, and `OrderFlowSimulator.driven_by(replay, marks,
reference_price, rng)` places it with fresh marks. `CoupledFlows.on(events, marks,
size_unit, uniform_depth, touches, levels, rng)`, with `touches` the price and the size of
each opening touch, folds CKS and one Hawkes book — haw-1 with
`config.unit_mark_params()` and `SizeUnit(1)`, haw-q with
`config.uncertain_size_mark_params()` and `config.uncertain_size_unit()` — reading sizes in
units of `size_unit`, so that haw-1 is haw-q at zero size variance. Its `frame` has a row
per event with, for each book under the prefixes `CKS` and `Haw`, the mid, the best prices,
the touch sizes and $e_n$.

**The side sizes** (`eq.sideSize`). With orders of one share a withdrawal from an occupied
side removes one share wherever it is drawn; while the bid of haw-1 is occupied, a limit
buy rests in full on it (`eq.limitPrice`), a market sell removes one share, and nothing
else changes it. With $\varpi^b := e_3 - e_2 - e_5$, $\varpi^a := e_4 - e_1 - e_6$
(`side_vector(BUY)`, `side_vector(SELL)`):

$$S^{b,\mathrm{haw}\text{-}1}_t(\tau\mathbb N) = S^b_0(\tau\mathbb N) + (\varpi^b)^\top
N(t), \qquad S^{a,\mathrm{haw}\text{-}1}_t(\tau\mathbb N) = S^a_0(\tau\mathbb N) +
(\varpi^a)^\top N(t),$$

with $S^b_0(\tau\mathbb N) = (L-1)\bar S + S^{b,1}_0$ and $S^a_0(\tau\mathbb N) =
(L-1)\bar S + S^{a,1}_0$ the sides of the opening book, and $\varpi^b - \varpi^a = \varpi$.
Under balance $(\varpi^b)^\top\lambda^* = 0$, so by `eq.forwardMeanCountsDeviation` from no
past the mean of $(\varpi^b)^\top N(t)$ is bounded in $t$ (it is $-(\varpi^b)^\top
A\Phi(t)m$, about $-0.43$ shares in the long run on the base case below), and its variance
grows as $t(\varpi^b)^\top D\varpi^b$. A side of the opening book, of more than $(L-1)\bar S$
shares and at most $L\bar S$, lasts of the order of $(L\bar S)^2/(\varpi^b)^\top D\varpi^b$,
$L^2$ times the time in which the walk moves by $\bar S$. A limit buy meets the floor only
when $\zeta_n \ge P^a_{T_n-}/\tau - 1$, of probability $(1-\eta)^{P^a_{T_n-}/\tau - 1}$.

**The whole-book imbalance** (`remark.wholeBookImbalance`). $S^{b,\mathrm{haw}\text{-}1}_t
(\tau\mathbb N) - S^{a,\mathrm{haw}\text{-}1}_t(\tau\mathbb N) = S^{b,1}_0 - S^{a,1}_0 +
\varpi^\top N(t)$, whatever the draws: the imbalance of the opening touches plus the signed
count. CKS has the same: every event changes its sides as it changes those of haw-1,
except a limit order sent to the opposite touch, which lowers both sides by one share. CKS
turns this imbalance into a mid-price at the fixed depth $\bar S$ per tick; haw-1 has no
fixed depth.

---

## 3. The first time the mid-prices differ

**Parting time** (`def.partingTime`). $\chi := \inf\{t \ge 0 : P^{m,\mathrm{CKS}}_t \ne
P^{m,\mathrm{haw}\text{-}1}_t\}$. In the code, `CoupledFlows.first_price_discrepancy` is
the index of the event, `.parting` the `Parting` with its type, the book that moved
(`Mover`) and the side; `first_price_discrepancy(...)` folds the books alone, for fans.

**Lemma** (`lemma.oneBestPrice`). In each book an event moves at most one best price, up if
$\varpi_{E_n} = +1$, down if $-1$. If the best prices of CKS and haw-1 agree before an event
that moves a best price in both, it moves the same one.

*Proof.* Types 1, 3, 5; their mirrors are the same. A market buy trades at the best ask in
every book (one share in CKS and haw-1, $q_n$ shares walking the ask in haw-q) and changes
nothing else; removing the lowest asks can only raise the best ask. A geometric limit buy
is priced below the best ask (`eq.limitPrice`) and rests in full on the bid: only the best
bid moves, up or not at all. In CKS a limit buy joins the best bid or opens a level one tick
above it; or, at a full best bid facing a spread of one tick, it trades one share at the
best ask, which can only rise. A withdrawal from the bid changes only the bid, and can only
lower its best price. A type moves different best prices in CKS and haw-1 only when CKS
sends a limit order to the opposite touch, at a spread of one tick; if the best prices
agree, haw-1's spread is one tick as well, and its limit buy is priced at
$P^b_{T_n-} - \tau\zeta_n$, at or behind the best bid, and moves nothing. $\square$

**Corollary** (`corol.partingAtOneQuote`). $\chi$ is the first time a best price of CKS
differs from that of haw-1, and at $\chi$ exactly one differs. *Proof*
(`exercise.partingAtOneQuote`): if the best prices agree before an event, by the lemma the
books either move the same best price, or one moves a best price and the other none, so at
most one best price differs after it, and the mid-prices differ exactly when one does.
$\square$

The queues may differ long before $\chi$; the mid-prices see only the best prices.

**Proposition** (`prop.partingProbability`). Let the best prices of CKS and haw-1 agree
before the $n$-th event, at a spread of $k$ ticks. The *side of the event* is the side on
which its CKS message acts: the opposite side for a market order and for a limit order at
a full touch facing a spread of one tick, its own side otherwise. Before the event:
$S^{\mathrm{CKS}}$, $S^{\mathrm{haw}\text{-}1}$ the touches of that side;
$S^{\mathrm{haw}\text{-}1}(\tau\mathbb N)$ the size on it in haw-1; $g$ the ticks from the
touch of haw-1 to the next occupied price behind it. Each book moves the best price of the
side of the event, by $j^{\mathrm{CKS}}$ and $j^{\mathrm{haw}\text{-}1}$ ticks, and no
other. The event parts the mid-prices exactly when $j^{\mathrm{CKS}} \ne
j^{\mathrm{haw}\text{-}1}$. For a limit order the *own touch* is the CKS touch on the side
of the order. Given $\mathfrak F^N$ and the earlier draws:

| event | $j^{\mathrm{CKS}}$ | probability of parting |
| --- | --- | --- |
| market order, $S^{\mathrm{CKS}} \ge 2$ | $0$ | $\mathbf 1\{S^{\mathrm{haw}\text{-}1} = 1\}$ |
| market order, $S^{\mathrm{CKS}} = 1$ | $1$ | $1 - \mathbf 1\{S^{\mathrm{haw}\text{-}1} = 1,\ g = 1\}$ |
| limit order, $k = 1$, own touch $< \bar S$ | $0$ | $0$ |
| limit order, $k = 1$, own touch $= \bar S$ | $\mathbf 1\{S^{\mathrm{CKS}} = 1\}$ | $\mathbf 1\{S^{\mathrm{CKS}} = 1\}$ |
| limit order, $k \ge 2$, $S^{\mathrm{CKS}} < \bar S$ | $0$ | $1 - (1-\eta)^{k-1}$ |
| limit order, $k \ge 2$, $S^{\mathrm{CKS}} = \bar S$ | $1$ | $1 - \eta(1-\eta)^{k-2}$ |
| withdrawal, $S^{\mathrm{CKS}} \ge 2$ | $0$ | $\mathbf 1\{S^{\mathrm{haw}\text{-}1} = 1\}/S^{\mathrm{haw}\text{-}1}(\tau\mathbb N)$ |
| withdrawal, $S^{\mathrm{CKS}} = 1$ | $1$ | $1 - \mathbf 1\{S^{\mathrm{haw}\text{-}1} = 1,\ g = 1\}/S^{\mathrm{haw}\text{-}1}(\tau\mathbb N)$ |

*Proof.* By the lemma and the corollary the event parts the mid-prices exactly when the
books move their best prices differently; by the proof of the lemma each moves at most the
best price of the side of the event (haw-1 moves nothing when CKS sends a limit order to the
opposite touch), so exactly when $j^{\mathrm{CKS}} \ne j^{\mathrm{haw}\text{-}1}$.

*CKS.* The opening has a level on every tick; CKS opens a level only one tick inside a
touch and empties one only at a touch, so each side keeps a level on every tick behind its
touch, of $\bar S$ by part *iii.*; a best price moves by one tick or not at all. A market
order or a withdrawal moves its touch exactly when it holds one share. A limit order at
$k \ge 2$ opens a level one tick inside exactly when its touch holds $\bar S$, and joins it
otherwise; at $k = 1$ it joins its touch if that holds less than $\bar S$, and otherwise
trades one share at the opposite touch, the touch of the side of the event, which moves
exactly when it held one share.

*haw-1.* A market order takes one share from the touch, which moves by $g$ exactly when it
held one. A limit order at $k \ge 2$ is priced $k - 1 - \zeta_n$ ticks inside its touch, so
it moves it by $j \in \{1,\dots,k-1\}$ with probability $\eta(1-\eta)^{k-1-j}$
(`eq.priceOffset`) and leaves it with probability $(1-\eta)^{k-1}$; at $k = 1$ it moves no
best price. A withdrawal moves the touch exactly when it draws it, with probability
$S^{\mathrm{haw}\text{-}1}/S^{\mathrm{haw}\text{-}1}(\tau\mathbb N)$, and the touch holds one
share; then by $g$.

The offsets are independent of $\mathfrak F^N$ and the earlier draws; the level of a
withdrawal is drawn on the book before the event. Each entry is the probability that the
two moves differ: for a market order, $j^{\mathrm{haw}\text{-}1} \ne 0$ exactly when
$S^{\mathrm{haw}\text{-}1} = 1$, and $j^{\mathrm{haw}\text{-}1} = 1$ exactly when moreover
$g = 1$; for a limit order at $k = 1$, $j^{\mathrm{haw}\text{-}1} = 0$; at $k \ge 2$,
$\mathbb P(j^{\mathrm{haw}\text{-}1} \ne 0) = 1 - (1-\eta)^{k-1}$ and
$\mathbb P(j^{\mathrm{haw}\text{-}1} \ne 1) = 1 - \eta(1-\eta)^{k-2}$; for a withdrawal,
$\mathbb P(j^{\mathrm{haw}\text{-}1} \ne 0) = \mathbf 1\{S^{\mathrm{haw}\text{-}1} =
1\}/S^{\mathrm{haw}\text{-}1}(\tau\mathbb N)$ and $\mathbb P(j^{\mathrm{haw}\text{-}1} = 1)
= \mathbf 1\{S^{\mathrm{haw}\text{-}1} = 1, g = 1\}/S^{\mathrm{haw}\text{-}1}(\tau\mathbb
N)$. In both books a market order acts on the side of the event as a withdrawal that draws
the touch, and its rows are those of the withdrawal with the probability of that draw set to
one. $\square$

**Corollary** (`corol.quietBook`). At a spread of one tick, an event moves a best price of
CKS, or of haw-1, exactly when it takes the last share of one of the touches of that book.
While the spread is one tick and every touch of the two books holds at least two shares, no
event moves a best price of either: the books are *quiet*.

*Proof.* The proof above at $k = 1$. In CKS a market order or a withdrawal takes one share
from a touch, and a limit order joins its touch or takes one share from the opposite touch;
a best price moves exactly when the touch that loses the share held one. In haw-1 a limit
order rests at or behind its touch and moves no best price, and a market order or a
withdrawal takes one share from a touch or from behind it; a best price moves exactly when
that share is the last of a touch. $\square$

**Definition** (`def.firstMoves`). The *first move* of CKS is $\psi^{\mathrm{CKS}} :=
\inf\{t \ge 0 : P^{b,\mathrm{CKS}}_t \ne P^b_0 \text{ or } P^{a,\mathrm{CKS}}_t \ne P^a_0\}$,
the first time a best price of CKS moves; $\psi^{\mathrm{haw}\text{-}1}$ likewise.

`first_price_moves(...)` returns `FirstMoves(cks, hawkes, cks_time, hawkes_time)`, and
`touch_walks(...)` the touch sizes of both books up to each first move.

**Touch walks** (`eq.touchWalks`). $\Upsilon^b(t) := S^{b,1}_0 + (\varpi^b)^\top N(t)$,
$\Upsilon^a(t) := S^{a,1}_0 + (\varpi^a)^\top N(t)$, and $\bar\Upsilon(t) := \max(\bar S,
\max_{s\le t}\max(\Upsilon^b(s), \Upsilon^a(s)))$, their running maximum floored at $\bar S$.

**Proposition** (`prop.cksTouchWalks`). For $t < \psi^{\mathrm{CKS}}$,
$S^{b,1,\mathrm{CKS}}_t = \Upsilon^b(t) - (\bar\Upsilon(t) - \bar S)$ and
$S^{a,1,\mathrm{CKS}}_t = \Upsilon^a(t) - (\bar\Upsilon(t) - \bar S)$, and

$$\psi^{\mathrm{CKS}} = \inf\{t : \bar\Upsilon(t) - \min(\Upsilon^b(t), \Upsilon^a(t)) = \bar S\}.$$

$\psi^{\mathrm{CKS}}$ is $\mathfrak F^N$-measurable, and under balance the means of
$\Upsilon^b(t) - S^{b,1}_0$ and $\Upsilon^a(t) - S^{a,1}_0$ are bounded in $t$.

*Proof.* Write $x^b$, $x^a$ for the right-hand sides: the opening touches at zero, since
$\bar\Upsilon(0) = \bar S$, and at most $\bar S$ since $\bar\Upsilon$ dominates both walks.
Induction on the events before $\psi^{\mathrm{CKS}}$, before which no best price of CKS has
moved, so its spread is one tick. A limit buy raises $\Upsilon^b$ by one, and $\bar\Upsilon$
by one exactly when $\Upsilon^b = \bar\Upsilon$, i.e. $x^b = \bar S$. If $x^b < \bar S$ it
joins the best bid and $x^b$ rises with it; if $x^b = \bar S$ the best bid is full, the
order trades a share at the best ask, $x^b$ stays and $x^a$ falls by one, as the touches do.
A market sell or a withdrawal from the bid lowers $\Upsilon^b$ by one, leaves
$\bar\Upsilon$, and takes a share from the best bid. The ask is the same. At a spread of one
tick a best price of CKS moves exactly at an event that takes the last share of a touch,
where $\min(x^b, x^a)$ reaches zero; each event changes $x^b$, $x^a$ by at most one. From no
past `eq.forwardMeanCountsDeviation` gives $\mathbb E N(t) - t\lambda^* = -A\Phi(t)m$,
bounded since $\rho < 1$, and $(\varpi^b)^\top\lambda^* = (\varpi^a)^\top\lambda^* = 0$.
$\square$

The cap removes from both walks the same $\bar\Upsilon - \bar S$, the number of limit
orders CKS has sent to the opposite touch, and so couples the two sides:
$\psi^{\mathrm{CKS}}$ is the first time one walk falls $\bar S$ below $\bar\Upsilon$.
`cks_touch_walks(events, uniform_depth, touches)` returns the walks, the running maximum and
the touches they give; `cks_first_move(events, uniform_depth, touches)` returns
$\psi^{\mathrm{CKS}}$ without folding a book.

The touches of haw-1 have no cap, and they depend on the draws as well as on the path.

**Proposition** (`prop.hawkesTouch`). For $t < \psi^{\mathrm{haw}\text{-}1}$
(`eq.hawkesTouch`),

$$S^{b,1,\mathrm{haw}\text{-}1}_t = S^{b,1}_0 + \sum_{n:T_n\le t,\,E_n=3}\mathbf 1\{\zeta_n =
0\} - N_2(t) - \sum_{n:T_n\le t,\,E_n=5}\mathbf 1\{p_n = P^b_{T_n-}\},$$

and likewise the ask, with the types 4, 1, 6. Given $\mathfrak F^N$ and the earlier draws,
$\{\zeta_n = 0\}$ has probability $\eta$ and $\{p_n = P^b_{T_n-}\}$ probability
$S^{b,1,\mathrm{haw}\text{-}1}_{T_n-}/S^{b,\mathrm{haw}\text{-}1}_{T_n-}(\tau\mathbb N)$, the
denominator being `eq.sideSize`. $\psi^{\mathrm{haw}\text{-}1}$ is the first time one of the
two right-hand sides reaches zero.

*Proof.* Before $\psi^{\mathrm{haw}\text{-}1}$ no best price of haw-1 has moved, so its
spread is the opening tick. A limit buy is priced at $P^a_{T_n-} - \tau(1 + \zeta_n) =
P^b_{T_n-} - \tau\zeta_n$ (`eq.limitPrice`): it joins the best bid exactly when $\zeta_n =
0$, probability $\eta$ by `eq.priceOffset`, and goes behind it otherwise. A market sell takes
one share from the best bid; a withdrawal from the bid one share from the level it draws,
the best bid with the probability stated (`def.geometricPlacement` *iii.*). The other three
types act on the ask. By `corol.quietBook` a best price of haw-1 moves exactly at an event
that takes the last share of a touch, at which one right-hand side reaches zero; each event
changes them by at most one. $\square$

**Why $\bar S \to \infty$.** Before their first moves the touches of the two books are walks
from openings of the order of $\bar S$. The best bid of haw-1 drifts at $\eta\lambda^*_3 -
\lambda^*_2 - \lambda^*_5 S^{b,1,\mathrm{haw}\text{-}1}_t/S^{b,\mathrm{haw}\text{-}1}_t(\tau\mathbb
N)$, of order one, negative if $\eta\lambda^*_3 < \lambda^*_2$, and then empties in a time of
the order of $\bar S$. The touch walks of CKS have no drift under balance, and the drawdown of
the order of $\bar S$ that gives $\psi^{\mathrm{CKS}}$ takes a time of the order of $\bar S^2$.
At a fixed $\bar S$ either book may move first; as $\bar S$ grows the two scales separate, so the
limit is taken with opening touches in proportion: the counts follow their means over horizons
proportional to $\bar S$, and each touch of haw-1 follows an ordinary differential equation.

**Proposition** (`prop.fluidTouch`). Let $\bar S \to \infty$ with $L$, $\eta$ and the
specification fixed, and with $S^{x,1}_0/\bar S \to r^x(0) \in (0, 1]$ for $x \in \{b,
a\}$. Let $L_x := L - 1 + r^x(0)$, the limit of $S^x_0(\tau\mathbb N)/\bar S$, and let
$r^x$ solve (`eq.fluidTouch`)

$$(r^x)'(s) = \eta\lambda^*_3 - \lambda^*_2 - \frac{\lambda^*_5}{L_x}r^x(s)$$

from $r^x(0)$, i.e. $r^x(s) = r^x_\infty + (r^x(0) - r^x_\infty)e^{-\lambda^*_5 s/L_x}$ with
$r^x_\infty := L_x(\eta\lambda^*_3 - \lambda^*_2)/\lambda^*_5$. Let $r^b$ and $r^a$ be
positive on $[0, s_1]$. Then in probability $\sup_{s\le s_1}|S^{b,1,\mathrm{haw}\text{-}1}_{\bar
S s}/\bar S - r^b(s)| \to 0$, $\sup_{s\le s_1}|S^{a,1,\mathrm{haw}\text{-}1}_{\bar S s}/\bar
S - r^a(s)| \to 0$, and $\mathbb P(\psi^{\mathrm{haw}\text{-}1} > \bar S s_1) \to 1$.

*Proof.* Three steps. Doob's inequality: $\mathbb E\sup_{t\le T}X(t)^2 \le 4\mathbb
E X(T)^2$ for a square-integrable martingale. Gronwall's inequality: a bounded $f \ge 0$
with $f(s) \le a + b\int_{(0,s]}f(s'-)\mu(ds')$, $\mu$ with finitely many atoms, satisfies
$f(s) \le ae^{b\mu((0,s])}$.

1. *LLN for the counts.* $M := N - \Lambda$. From no past $Z(0+) = 0$, and integrating
   `eq.stateDynamics` and `eq.intensityFromState` over $(0, t]$ gives at every $t$
   (`eq.countsFromNoPast`)
   $$N(t) - t\lambda^* = (I-\Gamma)^{-1}M(t) - \Gamma(I-\Gamma)^{-1}Z(t+).$$
   Doob: $\mathbb E\sup_{t\le T}M_e(t)^2 \le 4\mathbb E N_e(T) = O(T)$. The proof of
   `thm.lyapunov` starts from $Z(0) = 0$ and shows that the second moment converges, so the
   second moments of $Z(t+)$ are bounded in $t$, and so are those of $N_e(k+1) - N_e(k) =
   Z_e((k+1)+) - Z_e(k+) + \beta\int_k^{k+1}Z_e$. Since $\sup_{(k,k+1]}Z_e(t+) \le Z_e(k+) +
   N_e(k+1) - N_e(k)$, Chebyshev and a union bound over the unit intervals give
   $\mathbb P(\sup_{t\le T}|Z(t+)| > T^{3/4}) = O(T^{-1/2})$. With $T = \bar S s_1$ and the
   martingale term bounded by Doob and Chebyshev, $N^{\bar S}(s) := N(\bar S s)/\bar S$
   satisfies $\sup_{s\le s_1}|N^{\bar S}(s) - s\lambda^*| \to 0$, and by `eq.sideSize` and
   balance $S^{b,\mathrm{haw}\text{-}1}_{\bar S s}(\tau\mathbb N)/\bar S \to L_b$ uniformly.
2. *The draws.* $\delta_n := \mathbf 1\{\zeta_n = 0\} - \eta$ for a limit buy, $\delta_n :=
   \mathbf 1\{p_n = P^b_{T_n-}\} - S^{b,1}_{T_n-}/S^b_{T_n-}(\tau\mathbb N)$ for a withdrawal
   from the bid, zero otherwise: conditional mean zero, $|\delta_n| \le 1$. Given $\mathfrak
   F^N$ the partial sums $J_3$, $J_5$ over limit buys and bid withdrawals are martingales in
   the order of the events with orthogonal increments; Doob gives $\mathbb E\sup_{t\le
   T}J_e(t)^2 \le 4\mathbb E N_e(T) = O(T)$, so $\sup_{s\le s_1}|J_e(\bar S s)|/\bar S \to 0$.
3. *Gronwall.* $x(s) := S^{b,1}_{\bar S s}/\bar S$, $y(s) := S^b_{\bar S s}(\tau\mathbb
   N)/\bar S$, and $\tilde x$ the right-hand side of `eq.hawkesTouch` at $\bar S s$ over
   $\bar S$, for $s \le \psi^{\mathrm{haw}\text{-}1}/\bar S$: $\tilde x = x$ before, $\tilde x
   = 0$ at $\psi^{\mathrm{haw}\text{-}1}/\bar S$ if the event there takes the last share of the
   best bid, and
   $$\tilde x(s) = \frac{S^{b,1}_0}{\bar S} + \eta N^{\bar S}_3(s) - N^{\bar S}_2(s) -
   \int_{(0,s]}\frac{\tilde x(s'-)}{y(s'-)}dN^{\bar S}_5(s') + \frac{J_3(\bar S s) - J_5(\bar
   S s)}{\bar S},$$
   against $r^b(s) = r^b(0) + (\eta\lambda^*_3 - \lambda^*_2)s - \int_0^s\lambda^*_5 r^b/L_b$.
   Subtract; use $|\tilde x/y - r^b/L_b| \le |\tilde x - r^b|/y + |r^b||1/y - 1/L_b|$ with $y
   \ge L_b/2$, which holds on $[0, s_1]$ with probability tending to one. For $s \le s_1 \wedge
   \psi^{\mathrm{haw}\text{-}1}/\bar S$, $|\tilde x(s) - r^b(s)| \le \bar\delta_{\bar S} +
   \frac2{L_b}\int_{(0,s]}|\tilde x(s'-) - r^b(s')|dN^{\bar S}_5(s')$, with $\bar\delta_{\bar
   S}$ the supremum over $s \le s_1$ of $|S^{b,1}_0/\bar S - r^b(0)| + \eta|N^{\bar S}_3 -
   \lambda^*_3 s| + |N^{\bar S}_2 - \lambda^*_2 s| + |J_3 - J_5|/\bar S + \sup|r^b|\sup|1/y -
   1/L_b|\,N^{\bar S}_5(s_1) + |\int_0^s r^b\,(dN^{\bar S}_5 - \lambda^*_5 ds')|/L_b$. All tend
   to zero by the hypothesis on the opening and steps 1 and 2, the last after an integration
   by parts. Gronwall for $dN^{\bar S}_5$, atoms $1/\bar S$: $\sup_{s\le
   s_1\wedge\psi/\bar S}|\tilde x - r^b| \le \bar\delta_{\bar S}e^{2N^{\bar S}_5(s_1)/L_b} \to
   0$. On the event that $\psi^{\mathrm{haw}\text{-}1} \le \bar S s_1$ and the event at
   $\psi^{\mathrm{haw}\text{-}1}$ empties the best bid, the left side is at least $r^b(\psi/\bar
   S) \ge \min_{[0,s_1]}r^b > 0$, since $\tilde x$ vanishes there, so that event has
   probability tending to zero. The ask is the same, from its own opening, with the types 4,
   1, 6, of the same intensities. Hence $\mathbb P(\psi^{\mathrm{haw}\text{-}1} > \bar S s_1)
   \to 1$, and on that event $x = \tilde x$ on $[0, s_1]$, which gives the two limits.
   $\square$

**Corollary** (`corol.twoRegimes`). As $\bar S \to \infty$:

- *i.* if $\eta\lambda^*_3 < \lambda^*_2$, the fluid touch of the side $x$ reaches zero at
  $$s^*_x = \frac{L_x}{\lambda^*_5}\log\Big(1 + \frac{\lambda^*_5 r^x(0)}{L_x(\lambda^*_2 -
  \eta\lambda^*_3)}\Big),$$
  and, with $s^* := s^*_b \wedge s^*_a$, $\chi/\bar S \to s^*$ and
  $\psi^{\mathrm{haw}\text{-}1}/\bar S \to s^*$ in probability, and $\mathbb P(\chi =
  \psi^{\mathrm{haw}\text{-}1}) \to 1$: a touch of haw-1 empties first;
- *ii.* if $\eta\lambda^*_3 \ge \lambda^*_2$, the fluid touches are positive on $[0,
  \infty)$ and $\chi/\bar S \to \infty$ in probability. At equality $r^x(s) =
  r^x(0)e^{-\lambda^*_5 s/L_x}$.

*Proof.* By step 1 and balance, $\sup_{t\le\bar S s_1}|\Upsilon^{b}(t) - S^{b,1}_0|/\bar S
\to 0$ and likewise for the ask. Since $\bar\Upsilon(0) = \bar S$ and the opening touches
are at least $\bar S\min(r^b(0), r^a(0))/2$ for $\bar S$ large, $\bar\Upsilon -
\min(\Upsilon^b, \Upsilon^a) < \bar S$ on $[0, \bar S s_1]$ with probability tending to one:
$\mathbb P(\psi^{\mathrm{CKS}} > \bar S s_1) \to 1$, the touches of CKS holding at least two
shares there. *i.* $s^*_x$ is `exercise.fluidTouch`. Let $s_- < s^* < s_+$, and $x$ a side
with $s^*_x = s^*$. The proposition on $[0, s_-]$ gives $\psi^{\mathrm{haw}\text{-}1} > \bar
S s_-$. Its proof up to its last display does not use the sign of $r^x$; on $[0, s_+]$ it
shows that on $\{\psi^{\mathrm{haw}\text{-}1} > \bar Ss_+\}$ the touch of the side $x$ is
near $\bar S r^x(s_+) < 0$, impossible; so $\psi^{\mathrm{haw}\text{-}1} \le \bar S s_+$ with
probability tending to one. Then $\psi^{\mathrm{haw}\text{-}1} <
\psi^{\mathrm{CKS}}$, and by `corol.quietBook` the event at $\psi^{\mathrm{haw}\text{-}1}$
moves no best price of CKS, so $\chi = \psi^{\mathrm{haw}\text{-}1}$. *ii.* $r^b$ and $r^a$
are positive on every $[0, s_1]$, so
$\mathbb P(\psi^{\mathrm{haw}\text{-}1} > \bar S s_1) \to 1$ for every $s_1$, and $\chi \ge
\psi^{\mathrm{CKS}} \wedge \psi^{\mathrm{haw}\text{-}1}$. $\square$

The threshold is $\eta = \lambda^*_2/\lambda^*_3$: the rate at which limit buys join the
touch of haw-1 against the rate at which market sells take from it. `fluid_touch(params,
marks, levels, opening, scaled_time)` is $r^x$ and `fluid_emptying_time(params, marks,
levels, opening)` is $s^*_x$, infinite in the second regime, with `opening` the
`OpeningTouch` $r^x(0)$.

**Heuristics after the corollary** (unnumbered paragraphs in the notes). The regime is decided by
the sign of $\eta\lambda^*_3 - \lambda^*_2$; the withdrawals pull the touch towards
$r^x_\infty\bar S$. In the first regime the limit decides which book moves first and gives
$\chi \approx \bar S s^*$; CKS plays no part. At a finite $\bar S$ the touch of haw-1 fluctuates
about $\bar S r^x(t/\bar S)$ by $O(\sqrt{\bar S})$, so $\chi/\bar S$ falls short of $s^*$ on
average, and by more near the threshold, where the fluid touch meets zero at a small slope. In the
second regime the corollary says only that neither book moves on the scale $\bar S$.

CKS does not depend on $\eta$ and moves by the fluctuations of its walks. By the functional
central limit theorem of `BDHM13som` applied to $(\varpi^b)^\top N$ and $(\varpi^a)^\top N$,
whose drifts vanish under balance, the walks move by $\bar S$ in a time of the order of $\bar
S^2/(\varpi^b)^\top D\varpi^b$ (`diffusive_scale(params, uniform_depth)`). On that scale
$\psi^{\mathrm{CKS}}$ is the drawdown of `prop.cksTouchWalks` read on a Brownian motion $(W^b,
W^a)$ started at $(r^b(0) - 1, r^a(0) - 1)$, with $\mathrm{Cov}(W^x(s), W^y(s)) =
s(\varpi^x)^\top D\varpi^y$: $\psi^{\mathrm{CKS}}/\bar S^2$ is near in law to the first $s$ with
$\max(0, \sup_{s'\le s}\max(W^b, W^a)(s')) - \min(W^b, W^a)(s) = 1$, a function of the path.

The touch of haw-1 relaxes, at the rate $\lambda^*_5/(L_x\bar S)$ per share of deviation, towards
$(r^x_\infty/L_x)S^{x,\mathrm{haw}\text{-}1}_t(\tau\mathbb N)$, which by `eq.sideSize` is
$r^x_\infty\bar S$ plus a multiple of a driftless walk, and it fluctuates about that centre by
$O(\sqrt{\bar S})$. It reaches zero by a large deviation of the fluctuation, or when its side is
nearly exhausted, on the scale $(L\bar S)^2/(\varpi^b)^\top D\varpi^b$, $L^2$ times that of CKS.
Both first moves are on the scale $\bar S^2$, and $L$, not $\bar S$, orders them: on a book of
many levels $\chi = \psi^{\mathrm{CKS}}$, a function of the path. The first move of haw-1 is not
exponential in $\bar S$, since the side is a driftless walk that empties in finite time. Two steps
are not proved: the Ornstein–Uhlenbeck behaviour of the touch of haw-1 about its moving centre,
and the continuity of the drawdown functional at Brownian paths.

### Evidence for §3

Base case `config.balanced_order_flow_params()`: the resilient shape at $\rho = 0.5$, $\beta
= 4$, $\lambda^* = (1, 1, 2.5, 2.5, 1.5, 1.5)$, $\mu = (0.442, 0.442, 0.521, 0.521, 1.140,
1.140)$; $\bar S = 20$, $L = 10$; both opening touches full, $S^{b,1}_0 = S^{a,1}_0 = \bar
S$, so $r^b(0) = r^a(0) = 1$ and $L_b = L_a = L$; threshold $\eta = 0.4$; $(\varpi^b)^\top
D\varpi^b = 2.9849$, $(\varpi^b)^\top D\varpi^a = 0.0767$. Every number in this note is for
the full opening unless another is stated.

- *Lemma, corollaries.* 240 paths × 10 values of $\eta$, 1000 s: exactly one best price
  differs at $\chi$ on every pair; $\chi = \psi^{\mathrm{CKS}} \wedge
  \psi^{\mathrm{haw}\text{-}1}$ except on 1–4 of 240 paths at $\eta \le 0.4$ (the same move),
  none above.
- *`prop.cksTouchWalks`.* The formula equals the first move of the folded CKS book on every
  one of 360 paths at each $\bar S \in \{10, 20, 40\}$, and on 1200 paths at $\bar S \in \{1,
  2, 3, 5\}$, on 664 of which the cap acted before the move.
- *`prop.partingProbability`.* $\mathbf 1\{\chi \le T_n\} - \sum_{m\le n, T_m\le\chi} p_m$
  is a martingale, so $\mathbb E\sum_{n:T_n\le\chi}p_n = 1$, type by type too. 600 paths ×
  400 s: total $0.997\,(0.004)$ at $\eta = 0.2$, $1.000$ at 0.4 and 0.7; by type the
  compensator and the frequency agree to $0.001$ (market $0.773/0.773$, limit
  $0.052/0.053$, withdrawal $0.172/0.173$ at $\eta = 0.2$). At $\bar S = 1, 2, 3$, with a
  spread of two ticks before $\chi$ on 108 to 640 of 2000 paths: $0.985$–$0.997$, within
  error, and the lemma never violated.
- *`prop.fluidTouch`.* Touch of haw-1 over $\bar S$ against $r$, 96 paths per cell: within
  1–2% at $\eta = 0.5$, $\bar S = 80$ and at $\eta = 0.7$, $\bar S = 20$; at $\eta = 0.35$,
  $\bar S = 160$, within 2% to $s = 2$. The side over $\bar S$ stays at $10.0 \pm 0.1 = L$.
- *`corol.twoRegimes` i.* $\psi^{\mathrm{haw}\text{-}1}/\bar S$ approaches $s^*$ from below
  and slowly, the gap shrinking by about $1/\sqrt2$ per doubling of $\bar S$ ($\eta = 0.2$:
  $1.51, 1.52, 1.59, 1.63$ at $\bar S = 20, 40, 80, 160$ against $1.749$): the touch reaches
  zero when its $O(\sqrt{\bar S})$ fluctuation meets the fluid curve. The gap is largest near
  the threshold, where the slope at $s^*$ is small.
- *$\chi$ at $\bar S = 20$.* Mean $19.4$ s at $\eta = 0.1$ rising to $38.5$ s at $\eta \ge
  0.5$; CKS moves first on 59 of 240 paths at $\eta = 0.1$ and on all above $0.5$.
- *The race as $\bar S$ grows.* 48 paths, each cut at $2.5\bar Ss^*$: haw-1 moves before CKS on
  a share $0.81, 1, 1, 1$ of them at $\eta = 0.1$, $0.63, 0.94, 0.98, 1$ at $0.2$ and $0.44,
  0.79, 0.94, 1$ at $0.3$, for $\bar S = 20, 40, 80, 160$ (s.e. at most $0.07$). With
  $\mathbb E\psi^{\mathrm{CKS}} \approx k\bar S^2/(\varpi^b)^\top D\varpi^b$, $k = 0.313$ pooled
  over $\bar S = 10, 20, 40$, the two first moves meet at $\bar S_\times = s^*(\varpi^b)^\top
  D\varpi^b/k = 11.6, 16.7, 29.8$; the share is below one half only at $\eta = 0.3$, $\bar S =
  20$, the one case below its $\bar S_\times$.
- *The second regime, CKS.* $\mathbb E\psi^{\mathrm{CKS}}$ over $\bar S^2/(\varpi^b)^\top
  D\varpi^b$ is $0.316, 0.308, 0.307, 0.309$ (s.e. 0.011) at $\bar S = 10, \dots, 80$; the
  Brownian problem at the base correlation gives $0.32$. Without the coupling of the cap,
  two sides each reflected at its own cap, the constant would be $0.61$. At $\bar S = 20$
  the scale is $134$ s and $\mathbb E\psi^{\mathrm{CKS}} = 41$ s.
- *The second regime, haw-1.* The first move of haw-1 comes with the exhaustion of its
  side (24 paths each; medians):

  | $\eta$ | $L$ | $\bar S$ | $\psi^{\mathrm{haw}\text{-}1}$ | over $\bar S^2$ | exhaustion of a side | $\psi^{\mathrm{haw}\text{-}1} \le$ exhaustion |
  |---|---|---|---|---|---|---|
  | 0.9 | 2 | 10 | 122 s | 1.22 | 122 s | every path |
  | 0.9 | 2 | 20 | 472 s | 1.18 | 473 s | every path |
  | 0.9 | 2 | 40 | 2840 s | 1.77 | 2973 s | every path |
  | 0.7 | 10 | 10 | 2444 s | 24.4 | 3289 s | every path |
  | 0.7 | 10 | 20 | 12598 s | 31.5 | 12630 s | every path |

  At $\eta = 0.5$ ($r^x_\infty = 1.67$) a best price of haw-1 moved within $9\bar S + 10$ s on
  23, 2, 0, 0 of 96 paths at $\bar S = 20, 40, 80, 160$; at $\eta \ge 0.7$, $L = 10$, $\bar S
  = 20$, on none within 1500 s, short against the life of a side ($\approx 13\,400$ s).

---

## 4. The discrepancy of the mid-prices

**Definition** (`def.discrepancy`). $\mathcal D_t := P^{m,\mathrm{CKS}}_t -
P^{m,\mathrm{haw}\text{-}1}_t$, on the grid $\tfrac\tau2\mathbb Z$. `cks_mids(events,
uniform_depth, touches, levels, clock)` and `hawkes_mids(events, marks, size_unit,
uniform_depth, touches, levels, clock, rng)` read the two mids on a clock.

**Proposition** (`prop.discrepancyMoments`). On $G$: *i.* $\mathcal D_t = 0$ on $\{\chi >
t\}$. *ii.* If $S^{b,1}_0 = S^{a,1}_0$, the law of $\mathcal D_t$ is symmetric about zero;
$\mathbb E\mathcal D_t = 0$. *iii.* Under the hypothesis of *ii.*, $\mathrm{Var}\,\mathcal
D_t = \mathbb E[\mathcal D_t^2; \chi \le t] \ge (\tau/2)^2 \mathbb P(\mathcal D_t \ne 0)$.
*iv.* $\mathrm{Var}\,\mathcal D_t = \mathrm{Var}(\mathbb
E[\mathcal D_t \mid \mathfrak F^N]) + \mathbb E[\mathrm{Var}(P^{m,\mathrm{haw}\text{-}1}_t
\mid \mathfrak F^N)]$, the *flow part* and the *placement part* (see §2 on the event). All
four hold for $\chi^{\mathrm{haw}\text{-}q}$, $\mathcal D^{\mathrm{haw}\text{-}q}_t$.

*Proof.* *i.* is the definition. *ii.* The reflection $p \mapsto 2P^m_0 - p$ maps the tick
grid to itself, exchanges bid and ask, and maps the opening book to itself, its two touches
being equal. On $G$ every message of
the path and of its mirror is that of `example.idealisedPlacement` or of parts *i.*–*iii.*
of `def.geometricPlacement` (neither the floor nor the price of an empty side is used), and
these commute with the reflection, the type replaced by its mirror: the CKS rules are the
same on both sides; a limit buy at $P^a - \tau(1 + \zeta_n)$ reflects to a limit sell at the
reflected best bid plus $\tau(1 + \zeta_n)$; a withdrawal defined by $U_n$ from the touch
outwards reflects to the withdrawal of the other side that the same $U_n$ defines. By
induction, on $G$ the mirror's books are the reflections, and its discrepancy is $-\mathcal
D_t$. By `eq.directionSymmetry` the mirror has intensity $\Sigma\lambda = \mu + A\Sigma Z$: a
Hawkes process of the same specification, no past, the law of the path; $(\zeta_n, U_n,
q_n)$ are independent of both. The exchange preserves the law of the path and its draws and
leaves $G$ invariant, so on $G$, $-\mathcal D_t \overset{d}{=} \mathcal D_t$. *iii.* By *i.*,
*ii.*, and $\mathcal D_t \ne 0 \Rightarrow |\mathcal D_t| \ge \tau/2$. *iv.* Total variance;
CKS is $\mathfrak F^N$-measurable. None of the arguments uses the sizes, and the reflection
leaves them unchanged. $\square$

`variance_split(discrepancies)` takes an array of shape `(paths, mark seeds, times)` and
returns `Mean`, `StandardError`, `Total`, `FlowPart`, `PlacementPart` at each time, with
unbiased parts: `PlacementPart` is the mean of the within-path variances, `FlowPart` the
variance of the path means less `PlacementPart` over the number of mark seeds, and `Total` their
sum. On a small sample `FlowPart` can be negative.

### Working material behind the closing paragraphs (not in the notes)

The notes close `sec.discrepancy` with unnumbered paragraphs: the identity that ties the imbalance
of any book to the moves of its best prices, the three ways haw-1 departs from it, what can be
hoped for of the variance in each regime, and what random sizes change. The statements below,
and those of §5, are the derivations behind those paragraphs and behind the package and the
notebook; none carries a label in the notes.

**Outer sizes.** With $\Delta_n X := X_{T_n} - X_{T_{n-1}}$:
$\hat S^b_n = S^{b,1}_{T_{n-1}}$ if $\Delta_nP^b > 0$, $S^{b,1}_{T_n}$ if $\Delta_nP^b < 0$,
zero otherwise; $\hat S^a_n = S^{a,1}_{T_n}$ if $\Delta_nP^a > 0$, $S^{a,1}_{T_{n-1}}$ if
$\Delta_nP^a < 0$, zero otherwise: the size at the outer of the two values, on the book in
which that value is best.

**The touch identity.** With both sides occupied before and after the
event, and $e = e^b + e^a$ split as in `eq.orderFlowContribution`,
$e^b - \Delta_nS^{b,1} = \mathrm{sgn}(\Delta_nP^b)\hat S^b_n$ and $e^a + \Delta_nS^{a,1} =
\mathrm{sgn}(\Delta_nP^a)\hat S^a_n$; over a window,

$$\mathrm{OFI}_{t,w} - (S^{b,1}_t - S^{b,1}_{t-w}) + (S^{a,1}_t - S^{a,1}_{t-w}) =
\sum_{t-w<T_n\le t}\big(\mathrm{sgn}(\Delta_nP^b)\hat S^b_n + \mathrm{sgn}(\Delta_nP^a)\hat
S^a_n\big).$$

*Proof.* Bid unmoved: both indicators one, $e^b = \Delta_nS^{b,1}$. Up: only the first,
$e^b = S^{b,1}_{T_n}$, left side $S^{b,1}_{T_{n-1}} = \hat S^b_n$. Down: only the second,
$e^b = -S^{b,1}_{T_{n-1}}$, left side $-S^{b,1}_{T_n} = -\hat S^b_n$. The ask likewise; sum
and telescope. $\square$

It uses no property of the mechanism. A move contributes its ticks weighted by its outer
size per tick, which is $\bar S$ under `assumption.idealisedBook`.

**The touch identity under the idealised assumption.** Under the assumption every move is
by one tick with outer size $\bar S$, and the identity is `eq.idealisedUpdate` with the
residual `eq.idealisedResidual`. *Proof.* Parts *ii.*–*iv.*, as in
`exercise.idealisedUpdate`; the right-hand side is $2\bar S\Delta P^m_{t,w}/\tau$. $\square$

**The contribution of an event.** $\mathcal H$ is the set of the indices $n$ of the limit
orders and withdrawals that haw-1 places behind the touch of their side. Then
$e^{\mathrm{haw}\text{-}1}_n = \varpi_{E_n}\mathbf 1\{n \notin \mathcal H\}$,
$\mathrm{OFI}^{\mathrm{haw}\text{-}1}_{t,t} = \varpi^\top N(t) - \sum_{n\in\mathcal H, T_n\le
t}\varpi_{E_n}$, $\mathrm{OFI}^{\mathrm{CKS}}_{t,t} = \varpi^\top N(t)$.

*Proof.* More generally, an event of size $q$ on a geometric
book contributes $e = \varpi_{E_n}\mathbf 1\{n\notin\mathcal H\}\hat q_n$, with $\hat q_n :=
q \wedge S$ for a market order or a withdrawal at the touch, $S$ the touch it acts on, and
$\hat q_n := q$ otherwise. A market buy changes only the ask: if $q < S$ the ask stays and
$e^a = -\Delta_nS^{a,1} = q$; otherwise it rises and $e^a = S^{a,1}_{T_{n-1}} = S$, however
far it walks. A limit buy rests in full on the bid: behind the best bid $e = 0$; at it $e^b
= q$; above it the bid rises and $e^b = S^{b,1}_{T_n} = q$. A withdrawal from the bid removes
$q \wedge S^b(p_n)$ at its price and changes only the bid: behind, $e = 0$; at the touch,
either the bid stays and $e^b = -(q \wedge S)$, or the queue empties, the bid falls and $e^b
= -S^{b,1}_{T_{n-1}} = -(q \wedge S)$. Sell types likewise; the sign is $\varpi_{E_n}$. With
$q = 1$ this is the claim; CKS is `prop.signedSizeContribution`. $\square$

**The three-term decomposition.**

$$\frac{2\bar S}{\tau}\mathcal D_t = \sum_{n\in\mathcal H, T_n\le t}\varpi_{E_n}
- \big[(S^{b,1,\mathrm{CKS}}_t - S^{b,1,\mathrm{haw}\text{-}1}_t) - (S^{a,1,\mathrm{CKS}}_t -
S^{a,1,\mathrm{haw}\text{-}1}_t)\big]
+ \sum_{T_n\le t}\Big[\mathrm{sgn}(\Delta_nP^{b})\Big(\hat S^{b}_n - \bar S\frac{|\Delta_n
P^{b}|}{\tau}\Big) + \mathrm{sgn}(\Delta_nP^{a})\Big(\hat S^{a}_n - \bar S\frac{|\Delta_n
P^{a}|}{\tau}\Big)\Big],$$

the last sum read on haw-1.

*Proof.* CKS: `prop.idealisedUpdate` over $(0, t]$ with the lemma and
`eq.idealisedResidual`: $2\bar S(P^{m,\mathrm{CKS}}_t - P^m_0)/\tau = \varpi^\top N(t) -
(S^{b,1,\mathrm{CKS}}_t - S^{b,1}_0) + (S^{a,1,\mathrm{CKS}}_t - S^{a,1}_0)$. haw-1: the
touch identity over $(0, t]$, adding and subtracting $\bar S|\Delta_nP|/\tau$ in each signed
term, whose signed sum is $2\bar S(P^{m,\mathrm{haw}\text{-}1}_t - P^m_0)/\tau$. Subtract,
and use the lemma for $\mathrm{OFI}^{\mathrm{haw}\text{-}1}$. $\square$

The three terms: the events haw-1 places behind its touches; the mismatch of the touches at
$t$, bounded when those of haw-1 are; the mismatch of the depth haw-1 moves through, zero on
every move by one tick onto or off a queue of $\bar S$. `distance_terms(pair)` returns
`Distance` $= 2\bar S\mathcal D_t/\tau$ and the three terms as `ImbalanceMismatch`,
`TouchSizeMismatch`, `DepthMismatch`, with `Distance = ImbalanceMismatch -
TouchSizeMismatch - DepthMismatch`; `DepthMismatch` is CKS less haw-1 and `CKSDepthMismatch`
the CKS sum alone, zero by `prop.idealisedUpdate`.

**The placement martingale.** $\alpha_n := \mathbb P(n \in \mathcal H \mid
\mathfrak F^N, \text{earlier draws})$ is $(1-\eta)^{k_n}$ for a limit order, with $k_n :=
\phi^{\mathrm{haw}\text{-}1}_{T_n-}/\tau$ the spread of haw-1 before the event (after
$\chi$ the spreads of the two books differ), $1 - S^{\mathrm{haw}\text{-}1}/
S^{\mathrm{haw}\text{-}1}(\tau\mathbb N)$ for a withdrawal, zero for a market order.
$M^{\mathcal H}_t := \sum_{T_n\le t}\varpi_{E_n}(\mathbf 1\{n\in\mathcal H\} - \alpha_n)$ has
$\mathbb E[M^{\mathcal H}_t\mid\mathfrak F^N] = 0$, $\mathbb E[(M^{\mathcal
H}_t)^2\mid\mathfrak F^N] = \mathbb E[\sum_{T_n\le t}\alpha_n(1-\alpha_n)\mid\mathfrak F^N]$,
and $\mathrm{OFI}^{\mathrm{haw}\text{-}1}_{t,t} = \varpi^\top N(t) - \sum_{T_n\le
t}\varpi_{E_n}\alpha_n - M^{\mathcal H}_t$.

*Proof.* A limit order lands behind exactly when $\zeta_n \ge k$, probability
$(1-\eta)^k$; a withdrawal exactly when it does not draw the touch. With $\mathcal G_n$
generated by $\mathfrak F^N$ and the draws of the first $n$ events, $\alpha_n$ is $\mathcal
G_{n-1}$-measurable and the $n$-th draws are made, given $\mathcal G_{n-1}$, on the book the
earlier events left; the partial sums are a martingale in $(\mathcal G_n)$, increments
bounded by one, of conditional variance $\alpha_n(1-\alpha_n)$ since $\varpi_e^2 = 1$,
orthogonal; the number of events in $(0, t]$ is $\mathcal G_0$-measurable. The identity is
the lemma. $\square$

**The second-regime rate.** If $\eta\lambda^*_3 > \lambda^*_2$ and $t$
is short against $(L\bar S)^2/(\varpi^b)^\top D\varpi^b$: on $\{\psi^{\mathrm{haw}\text{-}1} >
t\}$, $\mathcal D_t = P^{m,\mathrm{CKS}}_t - P^m_0$ is $\mathfrak F^N$-measurable, and

$$\mathrm{Var}(\mathcal D_t/\tau) = \frac{\varpi^\top D\varpi}{(2\bar S)^2}t + O(\sqrt t) +
O\big(t\,\mathbb P(\psi^{\mathrm{haw}\text{-}1} \le t)^{1/2}\big),$$

the last term bounding the placement part (`second_regime_rate(params, uniform_depth)`).

*Proof.* On $\{\psi^{\mathrm{haw}\text{-}1} > t\}$ the mid of haw-1 stays at $P^m_0$.
$(P^{m,\mathrm{CKS}}_t - P^m_0)/\tau = \varpi^\top N(t)/(2\bar S) +
\varepsilon^{\mathrm{CKS}}_{t,t}/\tau$ with $|\varepsilon^{\mathrm{CKS}}_{t,t}| \le \tau$ by
`eq.idealisedUpdate`. By `eq.countsFromNoPast`, $\varpi^\top N(t) = \varpi^\top(I -
\Gamma)^{-1}M(t)$ up to a term bounded in mean square, since $\varpi^\top\lambda^* = 0$. The
components of $M$ have no common jumps (`eq.noCommonJumps`) and $\mathbb E M_e(t)^2 =
\mathbb E\Lambda_e(t) = t\lambda^*_e + O(1)$ from no past; so the variance is
$t\varpi^\top D\varpi + O(1)$ by `eq.flowVolatility`. Bounded terms contribute $O(\sqrt t)$
by Cauchy–Schwarz. The last term bounds $\mathbb E[\mathcal D_t^2 - (P^{m,\mathrm{CKS}}_t -
P^m_0)^2; \psi^{\mathrm{haw}\text{-}1} \le t]/\tau^2$ and the placement part
$\mathbb E\,\mathrm{Var}(P^{m,\mathrm{haw}\text{-}1}_t\mid\mathfrak F^N) \le \mathbb
E[(P^{m,\mathrm{haw}\text{-}1}_t - P^m_0)^2; \psi^{\mathrm{haw}\text{-}1} \le t]$, by
Cauchy–Schwarz, the fourth moments being $O(t^2)$. $\square$

**Hypotheses for the first regime.** *H1, constant placement:* $\alpha_n = \alpha_{E_n}$
for $\alpha \in [0,1]^{d_E}$. *H2, fixed depth:* there is $\tilde S > 0$ with $2\tilde
S(P^{m,\mathrm{haw}\text{-}1}_t - P^m_0)/\tau = \mathrm{OFI}^{\mathrm{haw}\text{-}1}_{t,t} +
R_t$, $\mathbb E R_t^2$ bounded in $t$. By the touch identity, $-R_t$ is
$(S^{b,1,\mathrm{haw}\text{-}1}_t - S^{b,1}_0) - (S^{a,1,\mathrm{haw}\text{-}1}_t -
S^{a,1}_0)$ plus
the last sum of the decomposition with $\tilde S$ for $\bar S$. When
$\mathrm{Var}\,P^{m,\mathrm{haw}\text{-}1}_t \to \infty$, H2 and Cauchy–Schwarz identify the
depth:

$$\tilde S = \lim_{t\to\infty}\frac\tau2\,\frac{\mathrm{Cov}(\mathrm{OFI}^{\mathrm{haw}\text{-}1}_{t,t},
P^{m,\mathrm{haw}\text{-}1}_t)}{\mathrm{Var}\,P^{m,\mathrm{haw}\text{-}1}_t},$$

the slope of the regression of the imbalance on the mid in half ticks; with the touches of
haw-1 bounded in mean square, the imbalance may be replaced by the signed sum of the outer
sizes of the moves, $K_t := \sum_{T_n\le t}(\mathrm{sgn}(\Delta_nP^b)\hat S^b_n +
\mathrm{sgn}(\Delta_nP^a)\hat S^a_n)$, regressed on $\Pi_t := 2(P^{m,\mathrm{haw}\text{-}1}_t -
P^m_0)/\tau$. That is the estimator of `PlacementStatistics.of`. The mean outer size per tick
crossed, $\sum\hat S_n/\sum|\Delta_nP|/\tau$, is a different statistic, and the two need not
agree. With $\circ$ the entrywise product,

$$c := \frac{\mathbf 1}{2\bar S} - \frac{\mathbf 1 - \alpha}{2\tilde S}:$$

an event of type $e$ moves the CKS mid by $\varpi_e/(2\bar S)$ ticks, and under H1–H2 that
of haw-1 by $\varpi_e(1 - \alpha_e)/(2\tilde S)$ in mean; $c_e$ is the difference.

**The first-regime closed form.** Under H1 and H2, with $O(1)$ bounded in
mean square uniformly in $t$,

$$\frac{\mathcal D_t}{\tau} = (\varpi\circ c)^\top N(t) + \frac{M^{\mathcal H}_t}{2\tilde S} + O(1),$$

if $S^{b,1}_0 = S^{a,1}_0$,

$$\mathbb E\Big[\frac{\mathcal D_t}{\tau}\Big|\mathfrak F^N\Big] = (\varpi\circ
c)^\top(N(t) - t\lambda^*) + O(1),$$

and

$$\mathrm{Var}\Big(\frac{\mathcal D_t}{\tau}\Big) = t(\varpi\circ c)^\top D(\varpi\circ c) +
t\sum_e\frac{\alpha_e(1-\alpha_e)\lambda^*_e}{(2\tilde S)^2} + O(\sqrt t),$$

the flow part and the placement part.

*Proof.* Under H1 $\sum\varpi_{E_n}\alpha_n = (\varpi\circ\alpha)^\top N(t)$, so by H2 and
the placement martingale $(P^{m,\mathrm{haw}\text{-}1}_t - P^m_0)/\tau =
(\varpi\circ(\mathbf 1 - \alpha))^\top N(t)/(2\tilde S) - M^{\mathcal H}_t/(2\tilde S) +
R_t/(2\tilde S)$. CKS gives $\varpi^\top N(t)/(2\bar S) + O(1)$; subtract for the first
identity. If the opening touches are equal, the exchange of the path with its mirror maps an
event of type $e$ placed behind to one of type $\Sigma(e)$ placed behind, on the reflected
book, and preserves the law of the path and its draws; so under H1 $\alpha_{\Sigma(e)} =
\alpha_e$. The entries of $c$ then agree on each pair while those of $\varpi$ have opposite
signs, so $(\varpi\circ c)^\top\lambda^* = 0$ by $\Sigma\lambda^* = \lambda^*$; with
$\mathbb E[M^{\mathcal H}_t\mid\mathfrak F^N] = 0$ this gives the second. Variance: the flow
term as in the previous proof; $\mathrm{Var}\,M^{\mathcal H}_t =
\sum_e\alpha_e(1-\alpha_e)\mathbb E N_e(t) = t\sum_e\alpha_e(1-\alpha_e)\lambda^*_e + O(1)$;
the two uncorrelated; bounded terms $O(\sqrt t)$. The conditional mean is $(\varpi\circ
c)^\top N(t)$ up to $O(1)$, so its variance is the first term and the second is the rest.
$\square$

As $\tilde S \to \infty$ this becomes the second-regime rate. $\alpha_e$ is zero
for a market order, $(1-\eta)^k$ for a limit order at spread $k$, and for a withdrawal one
minus the touch's share of its side, close to one for large $L$. In the code
`PlacementStatistics.of(pairs)` estimates $\alpha$ pooled over the events of the pairs and
$\tilde S$ by the regression of the imbalance on $\Pi_T$ across them, and
`closed_form_rates(params, uniform_depth, statistics, 0.0)` returns the two rates as
`VarianceRates(flow_part, placement_part)`. The closed form is first order: H1 and H2 hold
only approximately, and the split into flow and placement is a first guess.

### Evidence for §4

Fan B: 360 paths × 4 mark seeds, 1500 s; fan A: 120 × 10. A *rate* is the increase of the
variance from 500 s to 1500 s over 1000 s, in ticks²/s; standard errors from 300 bootstrap
resamples of paths. $\varpi^\top D\varpi = 5.8164$; the CKS rate $\varpi^\top
D\varpi/(2\bar S)^2 = 0.00364$.

- *Exact statements.* The decomposition at every one of 359 481 events (20 paths × 600 s ×
  $\eta = 0.1, 0.3, 0.6$), with the signs of `distance_terms`; the touch identity at every
  event of both fans; $\mathrm{OFI}^{\mathrm{haw}\text{-}1} = \varpi^\top N - \sum\varpi\alpha_n
  - M^{\mathcal H}$ to $10^{-12}$; on 3000 independent paths with one mark seed each,
  $\mathrm{Var}\,M^{\mathcal H}_{500}/\mathbb E\sum\alpha_n(1-\alpha_n) = 1.002\,(0.026)$ at
  $\eta = 0.1$ and $1.028\,(0.027)$ at $0.3$; $\mathbb E\mathcal D_{1500}$ within two
  standard errors of zero; $\mathbb P(\mathcal D_{1500} \ne 0) = 0.90$–$0.98$, so the lower
  bound of *iii.* is weak at long horizons.

The closed form with the two estimators of $\tilde S$ (rates in ticks²/s, flow / placement
/ total):

| $\eta$ | $\alpha_L$ | $\alpha_W$ | $\tilde S$: moves / regression | closed form, $\tilde S$ from the moves | closed form, $\tilde S$ by regression | measured |
|---|---|---|---|---|---|---|
| 0.1 | 0.778 | 0.980 | 2.57 / 3.7 | 0.0938 / 0.0349 / 0.129 | 0.0429 / 0.0168 / 0.0598 | 0.0498 (60) / 0.0195 (12) / 0.0691 (62) |
| 0.2 | 0.724 | 0.963 | 8.42 / 9.4 | 0.0070 / 0.0039 / 0.0109 | 0.0057 / 0.0031 / 0.0088 | 0.0061 (9) / 0.0045 (3) / 0.0106 (9) |
| 0.3 | 0.663 | 0.938 | 19.1 / 18.0 | 0.0023 / 0.0009 / 0.0032 | 0.0023 / 0.0010 / 0.0033 | 0.0016 (3) / 0.0015 (1) / 0.0031 (3) |
| 0.4 | 0.589 | 0.901 | 37.3 / 31.6 | 0.0023 / 0.0003 / 0.0025 | 0.0021 / 0.0004 / 0.0025 | 0.0011 (2) / 0.0008 (1) / 0.0019 (2) |
| 0.5 | 0.499 | 0.832 | 49.3 / — | 0.0023 / 0.0002 / 0.0025 | — | 0.0027 (3) / 0.0002 (0) / 0.0029 (3) |
| 0.7 | — | — | $\infty$ | 0.00364 / 0 / 0.00364 | 0.00364 / 0 / 0.00364 | 0.0040 (7) / 0.0000 / 0.0040 (7) |
| 1.0 | — | — | $\infty$ | 0.00364 / 0 / 0.00364 | 0.00364 / 0 / 0.00364 | 0.0040 (7) / 0.0000 / 0.0040 (7) |

At $\eta \ge 0.7$ no best price of haw-1 moved in 1500 s, and the second-regime rate holds
within its error. With $\tilde S$ from the moves the first-regime total is within one
standard error at $\eta = 0.2, 0.3$, within 1.3 at $0.5$, 1.3 times the measured at 0.4 and
1.9 times at 0.1. With $\tilde S$ by regression, the one H2 defines, the factor at 0.1 falls
to 0.87, within 1.5 standard errors, and the split fits there too; at 0.2 the total falls
two standard errors low. Neither estimator fits throughout; the misfit at 0.1 is mostly the
estimator. The remaining misfit has four measured sources:

1. *An event placed behind the touch is not lost:* it joins the depth and acts when the
   touch reaches it. Regressed impacts per event (×2, ticks) of market, limit and withdrawal
   types at $\eta = 0.2$ are $0.112, 0.066, 0.039$ against $(1-\alpha_e)/\tilde S = 0.119,
   0.033, 0.004$ (moves), and they grow with the horizon.
2. *The conditional mean is not linear in the counts:* the linear part of $\mathrm{Var}\,
   \mathbb E[P^{m,\mathrm{haw}\text{-}1}_{1500}\mid\mathfrak F^N]$ is 80–87% of it; whether an
   event moves a touch depends on the order of the events.
3. *H2 holds approximately:* $R^2$ of $K$ on $\Pi$ at 1500 s is $0.67$–$0.88$.
4. *There is no constant rate:* the whole-book imbalance $\varpi^\top N(t)$ does not revert,
   and the mid of haw-1 drifts towards the thinner side, at $10^{-5}$ ticks per share of
   imbalance per second, three to six standard errors from zero on windows from 500 s. The
   resulting $t^3$ term reaches the linear one near 4500–5500 s at $\eta = 0.1, 0.2$. A rate
   exists between the relaxation of the shape of haw-1, of order $L_x\bar S/\lambda^*_5 = 133$
   s, and that time; the rates above are measured there.

---

## 5. Uncertain sizes

Working material, as at the end of §4: the notes say what random sizes change in one closing
paragraph of `sec.discrepancy`.

CKS against haw-q, sizes in units of $\bar q$: in units the opening book is that of
`def.threeBooks`, the $n$-th order carries $\xi_n := q_n/\bar q$ units, $\mathbb E\xi_n =
1$. `lemma.oneBestPrice` and `corol.partingAtOneQuote` hold with the same proofs; in
`prop.partingProbability` the limit-order rows are unchanged, the price of a limit order not
depending on its size.

**The parting with sizes.** In units, haw-q moves the touch of the
side of the event *i.* for a market order exactly when $\xi_n \ge S^{\mathrm{haw}\text{-}q}$,
probability $\mathbb P(\xi_n \ge S^{\mathrm{haw}\text{-}q})$, to the first price at which
the size cumulated from the touch exceeds $\xi_n$, possibly several levels away; *ii.* for a
withdrawal exactly when it draws the touch and $\xi_n \ge S^{\mathrm{haw}\text{-}q}$,
probability $\mathbb P(\xi_n \ge S^{\mathrm{haw}\text{-}q})S^{\mathrm{haw}\text{-}q}/
S^{\mathrm{haw}\text{-}q}(\tau\mathbb N)$, by $g$ ticks. With unbounded support, as the
lognormal, these are positive at every touch, and the books are never quiet.

*Proof.* A market buy of $\xi_n$ units consumes the ask from the best price in price-time
priority until exhausted. A withdrawal cancels $\xi_n \wedge S(p_n)$ at its price
(`def.geometricPlacement` *iii.*), moving the touch exactly when it draws it and $\xi_n \ge
S$, to the next occupied price. $\xi_n$ is independent of $\mathfrak F^N$, the earlier draws
and the level drawn. $\square$

**The fluid scale with sizes.** In `eq.hawkesTouch` for haw-q a joining limit
order brings $\xi_n$, a market order or withdrawal at the touch removes $\xi_n \wedge S$.
With $\mathbb E\xi_n = 1$, $\mathrm{Var}\,\xi_n < \infty$ the three steps go through with
$\xi_n$ in the martingale of step 2, except two truncations: at the touch, acting only when
it holds $O(1)$ units, and of withdrawals behind the touch from levels of fewer than $\xi_n$
units, which change a side by an amount the argument does not control. To first order
`eq.fluidTouch`, $s^*$ and the two regimes are unchanged, the first move of haw-q coming when
its touch holds $O(1)$ units rather than none.

$\mathbb E\mathcal D^{\mathrm{haw}\text{-}q}_t = 0$ when the opening touches are equal, and
the split holds, by `prop.discrepancyMoments`, the split on the draws that keep the sides of
haw-q occupied.

**The decomposition with sizes.** With $\mathcal H$ read on haw-q and
$\hat\xi_n := \xi_n \wedge S^{\mathrm{haw}\text{-}q}$ for a market order or a withdrawal at
the touch, $\xi_n$ otherwise, $2\bar S\mathcal D^{\mathrm{haw}\text{-}q}_t/\tau$ is the
right-hand side of the decomposition read on haw-q in units, plus $\sum_{T_n\le t}
\varpi_{E_n}(1 - \hat\xi_n)\mathbf 1\{n\notin\mathcal H\}$.

*Proof.* As before, with the contribution of an event in units: $e^{\mathrm{haw}\text{-}q}_n/
\bar q = \varpi_{E_n}\hat\xi_n\mathbf 1\{n\notin\mathcal H\}$, and $\varpi -
\varpi\hat\xi\mathbf 1\{n\notin\mathcal H\} = \varpi\mathbf 1\{n\in\mathcal H\} +
\varpi(1-\hat\xi)\mathbf 1\{n\notin\mathcal H\}$. $\square$

The new term vanishes when every order carries one unit; with the first term it sums
$\varpi_{E_n}(1 - \hat\xi_n\mathbf 1\{n\notin\mathcal H\})$. Given $\mathfrak F^N$ and the
earlier draws $\xi_n$ is independent of $\{n \in \mathcal H\}$, mean one, and that event has
probability $\alpha_n$ on haw-q. Where $\hat\xi_n = \xi_n$ (every limit order, every event at
a touch of more than $\xi_n$ units) the increment $\varpi_{E_n}(1 - \xi_n\mathbf
1\{n\notin\mathcal H\} - \alpha_n)$ has conditional mean zero and

$$\mathrm{Var}(\xi_n\mathbf 1\{n\notin\mathcal H\}) = \alpha_n(1 - \alpha_n) + (1 -
\alpha_n)\mathrm{Var}\,\xi_n.$$

**What the sizes add.** Under H1, H2 read on haw-q, $\tilde S$ in units, and
setting aside the truncation at the touch, the proof of the first-regime closed form with
these increments adds $\mathrm{Var}\,\xi_n\sum_e(1-\alpha_e)\lambda^*_e/(2\tilde S)^2$ to
the placement rate, market orders entering with $\alpha_e = 0$
(`closed_form_rates(..., size_variance)`). It is neither the whole of what the sizes add nor
a bound on it. The truncation is not negligible: at each move of haw-q by a market order or
a withdrawal at its touch, $\hat\xi_n$ is the touch and not $\xi_n$, and
$\sum\varpi_{E_n}(\xi_n - \hat\xi_n)$ over these moves has a variance that grows with their
number. The sizes also make the depth
haw-q moves through random, through its outer sizes, and the whole-book imbalance random
given the path: up to the truncation of withdrawals it is $S^{b,1}_0 - S^{a,1}_0 +
\sum_{T_n\le t}\varpi_{E_n}\xi_n$ in units, of conditional variance $\mathrm{Var}\,\xi_n
N_{\mathfrak g}(t)$. The closed form carries none of the three. Whether an event moves a
touch depends on its size more than on the order of the events, and part of the variance
moves from the flow part to the placement part. A side of haw-q has variance rate
$(\varpi^b)^\top D \varpi^b + \mathrm{Var}\,\xi_n (\lambda^*_3 + \lambda^*_2 + \lambda^*_5)$
in units, $\bar q^2$ times it in shares.

### Evidence for §5

Fan B with `config.uncertain_size_mark_params()`: $\bar q = 100$, log-sd $0.8$,
$\mathrm{Var}\,\xi = e^{0.64} - 1 = 0.896$; $\tilde S$ from the moves.

| $\eta$ | paths kept | $\tilde S$ | flow: closed / measured (haw-1) | placement: closed / measured (haw-1) | total: closed / measured |
|---|---|---|---|---|---|
| 0.1 | 359/360 | 2.80 | 0.0809 / 0.0178 (36) (0.0498) | 0.1126 / 0.0591 (49) (0.0195) | 0.194 / 0.0769 (56) |
| 0.2 | 353/360 | 8.81 | 0.0067 / 0.0028 (12) (0.0061) | 0.0131 / 0.0273 (31) (0.0045) | 0.0198 / 0.0301 (29) |
| 0.3 | 341/360 | 19.2 | 0.0023 / 0.0010 (4) (0.0016) | 0.0032 / 0.0111 (15) (0.0015) | 0.0055 / 0.0121 (16) |
| 0.4 | 317/360 | 33.8 | 0.0022 / 0.0008 (3) (0.0011) | 0.0012 / 0.0057 (6) (0.0008) | 0.0034 / 0.0065 (6) |
| 0.5 | 303/360 | 40.5 | 0.0021 / 0.0015 (3) (0.0027) | 0.0009 / 0.0025 (3) (0.0002) | 0.0031 / 0.0041 (4) |

1. *The flow part falls*, to 0.36–0.73 of that of haw-1. Its linear part is unchanged for
   $\eta \ge 0.2$ (impacts $0.103, 0.063, 0.036$ against $0.112, 0.066, 0.039$); what falls
   is the nonlinear part ($0.42$ against $2.75$ ticks² at 0.2), which moves to the placement
   part.
2. *The size term is a lower bound.* The measured increase of the placement part over haw-1
   is two to six times $\mathrm{Var}\,\xi\sum_e(1-\alpha_e)\lambda^*_e/(2\tilde S)^2$ ($0.023$
   against $0.0098$ at 0.2), through the random depth, the random whole-book imbalance and
   the drift of source 4 of §4. H2 is worse: $R^2$ $0.62$–$0.65$.
3. *The assumption binds sooner.* The side variance rate is $\bar q^2[(\varpi^b)^\top
   D\varpi^b + \mathrm{Var}\,\xi(\lambda^*_3 + \lambda^*_2 + \lambda^*_5)] = 7.47\,\bar q^2$
   against $2.98$, a lifetime scale of 5357 s against 13 400 s. A side of haw-q emptied
   before 1500 s on 0.25% to 9.3% of the runs of fan A as $\eta$ goes from 0.1 to 1.0,
   against none of haw-1. The rates above are on the paths without an empty side, a
   selection of at most 16% that depends on the sizes; the nested split is then computed
   under a law in which the marks depend on the path, and *iv.* of
   `prop.discrepancyMoments` does not hold exactly for it.
4. *The truncation at the touch is not negligible.* At each move of haw-q through a market
   order or a withdrawal the message brings the touch, less than $\xi_n$, and the omitted
   $\sum\varpi_{E_n}(\xi_n - \hat\xi_n)\mathbf 1\{n\notin\mathcal H\}$ grows like the square
   root of the number of such moves; the closed form omits it.

---

## 6. What the notes predict

Inputs: `params = config.balanced_order_flow_params()`, `marks` (whose `depth_decay` is
$\eta$), `uniform_depth` $\bar S$, `levels` $L$, `opening` $r^x(0)$, `size_unit` $\bar q$,
$\mathrm{Var}\,\xi$.
$\lambda^*$ is `params.stationary_intensity()`, $D$ `params.count_covariance_rate()`,
$\varpi^b$, $\varpi^a$ `side_vector(BUY)`, `side_vector(SELL)`. Base case as in §3, $\bar S =
20$, $L = 10$, $\bar q = 100$, log-sd $0.8$.

| # | notes | prediction | code | base case | how to check |
| --- | --- | --- | --- | --- | --- |
| P1 | `corol.partingAtOneQuote`, `corol.quietBook`, `def.firstMoves` | at $\chi$ exactly one best price differs; $\chi = \psi^{\mathrm{CKS}} \wedge \psi^{\mathrm{haw}\text{-}1}$ unless the same move | `CoupledFlows.parting`, `first_price_moves` | always; exceptions $\le 2\%$ of paths | per path |
| P2 | `prop.partingProbability` | $\mathbb E\sum_{T_n\le\chi}p_n = 1$, type by type | — | — | compensator sum against frequency |
| P3 | `prop.cksTouchWalks` | $\psi^{\mathrm{CKS}}$ from the counts | `cks_first_move`, `cks_touch_walks` | equal to the folded book on every path | `first_price_moves(...).cks` |
| P4 | `prop.fluidTouch` | $r^x(s) = r^x_\infty + (r^x(0) - r^x_\infty)e^{-\lambda^*_5 s/L_x}$ | `fluid_touch` | at $r^x(0) = 1$: $r^x_\infty = 1.667, 3.333, 5, 10$ at $\eta = 0.5, 0.6, 0.7, 1$ | mean touch of haw-1 at $\bar S s$ over $\bar S$ |
| P5 | `corol.twoRegimes` | $\chi \approx \bar S s^*$, $s^* = s^*_b \wedge s^*_a$, in the first regime; and the share of paths on which haw-1 moves first, rising through one half near $\bar S_\times = s^*(\varpi^b)^\top D\varpi^b/k$ | `fluid_emptying_time` | $s^* = 1.2155, 1.7491, 3.1334, 5.2564$ at $\eta = 0.1, 0.2, 0.3, 0.35$; $\bar Ss^* = 24.3, 35.0, 62.7, 105.1$ s; from $r^x(0) = 0.5$, $s^*_x = 0.9285$ at $\eta = 0.2$; $\bar S_\times = 11.6, 16.7, 29.8$ at $\eta = 0.1, 0.2, 0.3$ | $\psi^{\mathrm{haw}\text{-}1}/\bar S$ at $\bar S = 20, \dots, 160$, from below; the share of haw-1-first paths at each $\bar S$ |
| P6 | heuristics after `corol.twoRegimes` | $\mathbb E\psi^{\mathrm{CKS}} \approx 0.31\,\bar S^2/(\varpi^b)^\top D\varpi^b$; haw-1 moves with the exhaustion of a side, at $L^2$ times the scale | `diffusive_scale` | scale $134.0$ s; $\mathbb E\psi^{\mathrm{CKS}} \approx 41$ s | mean of P3; $\psi^{\mathrm{haw}\text{-}1}$ against the exhaustion time |
| P7 | `prop.discrepancyMoments` | $\mathbb E\mathcal D_t = 0$ and the lower bound when the opening touches are equal; the split | `variance_split` | — | paths × mark seeds |
| P8 | working material: the three-term decomposition, the decomposition with sizes | the decomposition, per event | `distance_terms` | exact | per event |
| P9 | working material: the placement martingale | $\mathrm{Var}\,M^{\mathcal H}_t = \mathbb E\sum\alpha_n(1-\alpha_n)$, $\alpha_n$ on the spread of haw-1 | — | exact | independent paths, one mark seed each |
| P10 | heuristics after `prop.discrepancyMoments`; the second-regime rate | $\varpi^\top D\varpi/(2\bar S)^2$, all flow, on horizons short against the life of a side | `second_regime_rate` | $0.003635$ ticks²/s | $\eta \ge 0.7$ |
| P11 | heuristics after `prop.discrepancyMoments`, a first guess; the first-regime closed form | flow $(\varpi\circ c)^\top D(\varpi\circ c)$, placement $\sum_e\alpha_e(1-\alpha_e)\lambda^*_e/(2\tilde S)^2$, $\tilde S$ by regression | `closed_form_rates(params, uniform_depth, PlacementStatistics.of(pairs), 0.0)` | table of §4 | rates on $[500, 1500]$ s |
| P12 | heuristics after `prop.discrepancyMoments`; what the sizes add | placement plus $\mathrm{Var}\,\xi\sum_e(1-\alpha_e)\lambda^*_e/(2\tilde S)^2$, a lower bound | `closed_form_rates(…, e^{σ²} − 1)` | table of §5 | same |
| P13 | `eq.sideSize`, `remark.wholeBookImbalance` | sides $S^x_0(\tau\mathbb N) + (\varpi^x)^\top N(t)$, whole-book imbalance $S^{b,1}_0 - S^{a,1}_0 + \varpi^\top N(t)$, for haw-1 | `side_vector` | exact | per event |
| P14 | `eq.sideSize`; what the sizes add | lifetime $(L\bar S)^2/(\varpi^b)^\top D\varpi^b$, with sizes $(L\bar S)^2/[(\varpi^b)^\top D\varpi^b + \mathrm{Var}\,\xi(\lambda^*_3 + \lambda^*_2 + \lambda^*_5)]$ | `CoupledFlows.breach` | 13 400 s; 5357 s | fraction of runs with an empty side |

Estimators for P11–P12 (`PlacementStatistics.of`): $\alpha_e$ is the fraction of the events
of type $e$ with $e_n = 0$ on the Hawkes book, pooled over runs; $\tilde S$ is
$\mathrm{Cov}(K_T, \Pi_T)/\mathrm{Var}\,\Pi_T$ across runs to one horizon, in units,
infinite when nothing moves. Horizons: rates between 500 and 1500 s, after the shape of the
book has relaxed ($\approx 133$ s) and before the drift of source 4 of §4 matters
($\approx 4500$ s).

---

## 7. The module

`unito26.lob.coupling` exports:

- the path: `SizeUnit` (a `NewType` of `int`, the shares in one unit), `RecordedEvents`
  (`drawn`, `head`, `after`, `state_after`, `replay`), `Replay`;
- the pair: `CoupledFlows` (`on`, `frame`, `cks_depth`, `hawkes_depth`, `breach`,
  `first_price_discrepancy`, `first_price_discrepancy_time`, `parting`), `Parting`,
  `Mover` (`CKS`, `HAWKES`, `BOTH`);
- the books alone, for fans: `first_price_discrepancy`, `first_price_moves` with
  `FirstMoves`, `touch_walks`, `cks_mids`, `hawkes_mids`;
- the statistics: `variance_split`, `distance_terms`;
- the predictions: `side_vector`, `cks_touch_walks`, `cks_first_move`, `OpeningTouch` (a
  `NewType` of `float`, the opening touch over $\bar S$), `fluid_touch`,
  `fluid_emptying_time`, `diffusive_scale`, `second_regime_rate`, `PlacementStatistics`
  (`behind_probability`, `effective_depth`, `of`), `VarianceRates` (`flow_part`,
  `placement_part`, `total`), `closed_form_rates`.

The configs are `config.balanced_order_flow_params()`, `config.unit_mark_params()` (one
share, $\eta = 0.2$), `config.uncertain_size_mark_params()` (lognormal, mean 100, log-sd
0.8, $\eta = 0.2$) and `config.uncertain_size_unit()` (100).
