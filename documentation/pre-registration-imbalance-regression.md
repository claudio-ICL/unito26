# Pre-registration — regressing the mid-price change on the imbalances

Frozen before the first confirmatory run. It is a procedure, not an intention: every claim
below carries its estimand in symbols, the exact row set, the statistic, the inference, the
direction, the threshold, the multiplicity correction, and the minimum effect the seed block
can detect.

**Three disjoint seed blocks.** Exploration, which produced every number in the notebook's
context section and every figure in the development notes, used seeds **0–29**. The window
and the dispersions below were fixed on a **tuning block, seeds 2000–2019**, which had never
been read at the time. Confirmation uses **3000–3011**, which has been read by nothing.
Exploratory numbers are reported without p-values and without intervals framed as tests.

## The lab

Two regimes, at the same branching ratio and the same total rate, differing in whether
excitation follows the pressure partition. `chap.hawkes` §7 develops the distinction and
[`point-processes-and-hawkes.md`](point-processes-and-hawkes.md) §2 tabulates it.

| | resilient (`EXAMPLE_`) | trending (`TRENDING_`) |
| --- | --- | --- |
| `ρ`, `ν` | 0.6, 30.19 events/s | 0.6, 30.19 events/s |
| `β` | 4 s⁻¹ | 4 s⁻¹ |
| `λ_L/(λ_M + λ_W)` | 0.965 | 0.98 |
| `depth_decay` | 0.08 | 0.15 |
| signed endogenous fraction | −0.351 | +0.554 |

Warm-up `W = 1200 s`, sample `T = 3600 s`, reported depth 10.

The warm-up is not a round number and is not the old one. From an empty book the touch depth
reaches 95% of its plateau at about **900 s**, so 1200 s puts the whole sample on the
plateau. The previous value of 4800 s was set against a generator whose depth never
plateaued at all, and is not a conservative version of this one — it is a number derived from
a different object.

`β = 4` and not 60. At the old decay `ν/β = 0.50`: an event's excitation had fallen to 13.7%
before the next event arrived, so the study sampled a process whose self-excitation was
switched off between observations. At `β = 4`, `ν/β = 7.55`.

## The row set, fixed once

Rows are the messages of one session at reported depth 10, built with
`MarketSession.from_occupied_levels` and masked on the `Covered` flags. A row enters a claim
when **every** predictor in that claim is defined on it and the outcome is defined:

* `OFI_{t,w}` is NaN when any `e_n` in `(t−w, t]` is NaN — row 0, any empty-side row, and the
  row after one, since `e_n` reads two states;
* `I^1_t` is NaN where `QueueImbalance1Covered` is 0;
* the outcome is NaN where the forward difference spans a segment boundary.

Measured on the tuning block: the resilient regime retains **99.995%** of rows with a single
segment per seed; the trending regime retains **99.74%** across **480 segments** per seed.

**The two regimes therefore carry different survival gates, and the reason is structural.**
A trending book is one whose liquidity is stripped, so emptying is the phenomenon and not a
defect; a gate that refused it would refuse the regime. The resilient regime is gated at
99.9% and the trending one at 99.0%, both reported, and the trending regime additionally
carries a sensitivity check: every claim it enters is recomputed on the subset of rows more
than one second from any segment boundary, and a claim whose sign moves under that
restriction is withdrawn.

## The claims

Four. Holm within the family of four; family-wise 5%, one-sided where a direction is given.
`bins = 6`, `prior_weight = 20`, fitted on the first half of each session and scored on the
second, with the train side purged by `ceil(w * nu)` rows at the fold boundary, which is
`w` seconds of rows plus the next-event horizon.

`w` is **fixed on the tuning block and never re-examined**: `w* = 0.200 s` in the resilient
regime and `0.080 s` in the trending one, each the argmax of the mean incremental-skill curve
over the grid `{0.05, 0.08, 0.125, 0.2, 0.3, 0.45, 0.7, 1.1, 1.7, 2.6, 4.0}` s, scored on the
row set of the largest candidate. The horizon is fixed a priori: the next event for C1–C3,
and one second for C4.

Every interval is **seed-level**: the twelve sessions are the independent replicates, and a
within-path block bootstrap answers a different question — it conditions on one realisation
of the depth path. The block bootstrap is reported alongside for single-session statements
only, over contiguous blocks of *time*, with the block length from Politis–White and
sensitivity at 2× and 4×.

C1–C3 are claims about the **resilient** regime, which is the one that passes the tighter
survival gate. C4 is the claim about the contrast, and is the headline.

### C1 — the window adds information over the last event alone

*Estimand.* `Δ₁ = E[ S(e_n, OFI_{t,w} − e_n) − S(e_n) ]` over seeds, where `S` is the
three-class out-of-fold log-score skill of a binned model, the joint model shrunk toward the
`e_n`-only model so that `Δ₁ = 0` exactly when the window adds nothing.

*Statistic.* `incremental_log_score_skill`. *Alternative.* `Δ₁ > 0`, one-sided.

*Detectable.* Tuning-block dispersion `sd = 5.6·10⁻⁴`; at 12 seeds the 80%-power one-sided
minimum is `4.0·10⁻⁴`. Tuning-block mean `+2.7·10⁻³`.

*Why this and not `b₂`.* `b₂ = 0` is a one-degree-of-freedom **linear** restriction that
forces the window's contribution onto an equally weighted boxcar, and the outcome is an atom
with a heavy-tailed remainder that a magnitude slope reads badly. `b₂` and the lag-bucket `F`
are reported as diagnostics beside this, never as the headline.

### C2 — `OFI` adds information over `I^1`

*Estimand.* `Δ₂ = E[ S(I^1, OFI) − S(I^1) ]`, same estimator, same folds.

*Alternative.* `Δ₂ > 0`, one-sided. *Detectable.* `sd = 8.1·10⁻⁴`, minimum `5.8·10⁻⁴` at 12
seeds. Tuning-block mean `+1.7·10⁻³`.

### C3 — `I^1` adds more over `OFI` than `OFI` adds over `I^1`

*Estimand.* `Δ₃ = E[ S(OFI, I^1) − S(OFI) ] − Δ₂`, the two incremental skills differenced
**within seed**, which is what makes them comparable: they share the row set, the folds and
the bin count.

*Alternative.* `Δ₃ > 0`, one-sided. *Detectable.* `sd = 1.5·10⁻³`, minimum `1.1·10⁻³` at 12
seeds. Tuning-block mean `+1.6·10⁻²`.

*What it may and may not be read as.* It says the book-reading statistic carries information
the flow statistic cannot. It does **not** say how large that advantage would be in a traded
market, and the direction of the bias is known: this laboratory has no adverse-selection
channel, so `I^1` here carries mechanical information only and is measured at its weakest.
A confirmation of C3 is therefore a lower bound on the imbalance's advantage, not an estimate
of it.

### C4 — the predictive sign is opposite between the regimes

The headline. Contemporaneously `OFI` is the mechanical update of the mid in both regimes,
and that is accounting. What it predicts is not, and the two regimes disagree.

*Estimand.* `Δ₄ = E_trending[ Cov(sign OFI_{t,w}, ΔP^m_{t→t+1s}) ]
− E_resilient[ Cov(sign OFI_{t,w}, ΔP^m_{t→t+1s}) ]`, each expectation over its own twelve
seeds at its own `w*`.

*Statistic.* `signed_covariance`, which is the lattice-aware form: the raw `E[sign(x) ΔP]`
inherits the per-seed price drift, and the model has no anchor for the level.

*Alternative.* `Δ₄ > 0`, one-sided, **and** the two regime means of opposite sign
individually, each one-sided at the same family level. The compound alternative is
deliberate: a contrast can be large because one regime is extreme, and the claim is about the
*sign flip*, which requires both.

*Detectable.* Pooled tuning-block dispersion `sd = 1.4·10⁻²`; at 12 seeds a regime the
80%-power one-sided minimum is `1.0·10⁻²`. Tuning-block contrast `+0.113`, which is 10.9× it,
with all 20 tuning seeds negative in the resilient regime and all 20 positive in the trending
one.

*What it may be read as.* That the sign belongs to the **kernel** and not to `OFI`. No
statement anywhere in this study about `OFI` predicting continuation or reversal is
admissible without naming the regime.

## What is not confirmatory

Everything else in the notebook: the `ρ` and `β` ladders, the bucket ladder, the ceiling
table, the mechanical regression's shape, the `R²` diagnostics, the tail statistics, the
mutual information and transfer entropy tables, the forward-VWAP experiment, and every number
in the context section. Reported as measurements with seed bands, without p-values.

The `ρ` and `β` ladders were confirmatory claims in the previous revision of this file. They
are not run here, and a claim that is not run is not pre-registered: they move to
[`point-processes-and-hawkes.md`](point-processes-and-hawkes.md) as measurements.

The information measures are descriptive for a reason rather than by omission. Their
plug-in bias is `(m_x−1)(m_y−1)/2n_eff`, and `n_eff` is not the row count: the relaxation
time spans about nineteen events, so the realistic bias is of the same order as the effects
being measured. Their null is a circular shift and never a permutation.

## What would falsify the regime rather than a claim

Reported and acted on before any claim is read:

* resilient regime: any seed with more than 0.1% of rows masked away from the session
  opening; trending regime: more than 1.0%, with the sensitivity check above;
* any regime whose realised `λ_L/(λ_M + λ_W)` differs from its declared value by more than 1%;
* any regime with `min μ < 0`, which the constructor refuses outright;
* a touch depth whose profile across the six tenths of a session has a slope significantly
  different from zero across the block. The gate is a **trend** test and not a band: on a
  book of a few hundred shares the ten-minute means fluctuate by tens of per cent without
  drifting, and a band written for a thicker book fails on fluctuation alone. At the
  operating point the slope is `+0.8%` per tenth with `t = 0.98`, `p = 0.34`.
