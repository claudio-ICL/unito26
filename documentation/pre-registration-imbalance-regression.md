# Pre-registration — regressing the mid-price change on the imbalances

Frozen before the first confirmatory run. It is a procedure, not an intention: every claim
below carries its estimand in symbols, the exact row set, the statistic, the inference, the
direction, the threshold, the multiplicity correction, and the minimum effect the seed block
can detect.

The context section of the notebook is a page of numbers mined from this same generator, so
the **confirmatory seed block is disjoint from the exploratory one**: exploration used seeds
0–29, confirmation uses **1000–1011**. Exploratory numbers are reported without p-values and
without intervals framed as tests.

## The lab

`ρ = 0.6`, `β = 60 s⁻¹`, `ν = 30.19` events/s, `λ_L/(λ_M + λ_W) = 1`, `depth_decay = 0.15`.
Warm-up `W = 4800 s`, sample `T = 3600 s`, reported depth 10.

The warm-up is not a round number. From an empty book the touch depth reaches 95% of its
plateau at about 3 900 s, so 4 800 s puts the whole sample on the plateau; it is also far
above the intensity relaxation `20/(β(1−ρ)) = 0.83 s`, which is the constraint that binds at
the other end of the `β` ladder and is asserted rung by rung.

## The row set, fixed once

Rows are the messages of one session at reported depth 10, built with
`MarketSession.from_occupied_levels` and masked on the `Covered` flags. A row enters a claim
when **every** predictor in that claim is defined on it and the outcome is defined:

* `OFI_{t,w}` is NaN when any `e_n` in `(t−w, t]` is NaN — which is row 0, any empty-side
  row, and the row after one, since `e_n` reads two states;
* `I^1_t` is NaN where `QueueImbalance1Covered` is 0;
* the outcome is NaN where the forward difference spans a segment boundary.

Measured on the confirmatory block, **99.997%** of rows survive and every seed has a single
segment. Survival is reported as a gate: a rung below 99.9% away from the session opening has
left the regime, and is reported as out of regime rather than silently conditioned on.

## The claims

Five, all at `w = 30 ms` and the next-event horizon unless stated. Holm within the family of
five; family-wise 5%, two-sided except where a direction is given.

Every interval is **seed-level**: the twelve sessions are the independent replicates, and a
within-path block bootstrap answers a different question — it conditions on one realisation
of the depth path. The block bootstrap is reported alongside for single-session statements
only, over contiguous blocks of *time*, with the block length from Politis–White on the
scored series and sensitivity at 2× and 4×.

### C1 — the window adds information over the last event alone

*Estimand.* `Δ₁ = E[ S(e_n, OFI_{t,w} − e_n) − S(e_n) ]` over seeds, where `S` is the
three-class out-of-fold log-score skill of a binned model, the joint model shrunk toward the
`e_n`-only model so that `Δ₁ = 0` exactly when the window adds nothing.

*Statistic.* `incremental_log_score_skill` at `bins = 6`, `prior_weight = 20`, fitted on the
first half of each session and scored on the second.

*Alternative.* `Δ₁ > 0`, one-sided. *Threshold.* Holm-adjusted 5%.

*Detectable.* Pilot dispersion `sd = 1.2·10⁻³`; at 12 seeds the 80%-power one-sided minimum
is `9.6·10⁻⁴`.

*Why this and not `b₂`.* `b₂ = 0` is a one-degree-of-freedom **linear** restriction that
forces the window's contribution onto an equally weighted boxcar, and the outcome is an atom
of 0.96 with a heavy-tailed remainder that a magnitude slope reads badly. `b₂` and the
lag-bucket `F` are reported as diagnostics beside this, never as the headline.

### C2 — `OFI` adds information over `I^1`

*Estimand.* `Δ₂ = E[ S(I^1, OFI) − S(I^1) ]`, same estimator, same folds.

*Alternative.* `Δ₂ > 0`, one-sided. *Detectable.* `sd = 1.6·10⁻³`, minimum `1.3·10⁻³` at 12
seeds.

### C3 — `I^1` adds more over `OFI` than `OFI` adds over `I^1`

*Estimand.* `Δ₃ = E[ S(OFI, I^1) − S(OFI) ] − Δ₂`, the two incremental skills differenced
**within seed**, which is what makes them comparable: they share the row set, the folds and
the bin count.

*Alternative.* `Δ₃ > 0`, one-sided — the book-reading statistic carries information the flow
statistic cannot, which is entry 7 of the theory reference and the reason the flow-only
oracle is not a ceiling.

*Detectable.* `sd = 3.2·10⁻³`, minimum `2.7·10⁻³` at 12 seeds.

### C4 — the incremental skill of `OFI` over `I^1` rises with `ρ`

*Estimand.* the slope of `Δ₂` on `ρ` across the ladder `ρ ∈ {0, 0.2, 0.4, 0.6, 0.8}`, with
`λ*` held identical on every rung by `μ = (I − Γ)λ*` and `μ ≥ 0` checked rung by rung.

*Alternative.* slope `> 0`, one-sided. The **incremental** statistic and not the level: the
levels carry `1/Var(depth)`, and the depth is not controlled across rungs.

*Detectable.* Twelve seeds a rung; the rung-to-rung dispersion is re-estimated on the
exploratory block before the confirmatory run and the claim is refused if the realised
dispersion exceeds what twelve seeds were sized for.

### C5 — the optimal window scales as `1/β` and not as `1/(β(1−ρ))`

*Estimand.* the two exponents of `log w*` regressed jointly on `log(1/β)` and
`log(1/(1−ρ))`, predicted `(1, 0)`.

*Statistic.* an **equivalence test** against a margin of `±0.25` on each exponent, not a
test that the slope differs from zero — the prediction is a point, so the burden runs the
other way.

*Primary evidence.* the **collapse** of the whole criterion curve when plotted against
`log w − log(1/β)`, which uses every grid point rather than one argmax. `ŵ*` is a noisy
statistic on a quadratically flat surface, and the argmax regression is reported second.

*Grid.* `w` bounded below by an event-sampled window occupancy of 2 and above by
`T/w ≥ 50`; `β` extended only while `w* ≈ 1.6/β` stays interior to the grid.

*Tuning.* on a block of seeds disjoint from both the exploratory and the confirmatory blocks.
Within a path, where folds are used at all, the purge and embargo are `w_max + h` — the
**sum**, since a row at `t` reads `(t − w, t + h]` — and every candidate is scored on the row
set of the largest candidate.

## What is not confirmatory

Everything else in the notebook: the `c` ladder, the `β` ladder's levels, the ceiling table,
the mechanical regression's shape, the `R²` diagnostics, the tail statistics, and every
number in the context section. Reported as measurements with seed bands, without p-values.

## What would falsify the regime rather than a claim

Reported and acted on before any claim is read:

* any seed with more than 0.1% of rows masked away from the session opening;
* any rung whose realised `λ_L/(λ_M + λ_W)` differs from 1 by more than 1%;
* any rung with `min μ < 0`, which the constructor refuses outright;
* a touch depth whose last sixth differs from its first by more than a factor of two,
  averaged over the block.
