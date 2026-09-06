---
name: point-processes
description: The theory and notation of point processes and Hawkes processes as this course defines them, and the invariants the unito26 simulator rests on. Load before writing or reviewing any code or prose that touches counting processes, intensities, compensators, the random time change, Hawkes self-excitation, branching ratios, cluster or branching representations, exact or thinning simulation of point processes, the synthetic order-flow generator, or the predictive power of order-flow and queue imbalance — in the unito26 package, in notebooks, in the lecture notes, or in exam snippets.
---

# Point processes and Hawkes flow in `unito26`

The theory is developed in the notes, `documentation/tex/notes/hawkes/`, chapter
`chap.hawkes`, and restated for working use — with the module and test that carry each
section — in **`documentation/point-processes-and-hawkes.md`**. Read that file before
designing types or functions; the notes are the authority, this skill is the code-facing
half.

Symbols are the notes' symbols. Never invent a parallel name for something the notes
already name, and never rename a concept on the way into Python.

## The naming map

| notes | macro | Python |
| --- | --- | --- |
| $d_E$ | `\numEventTypes` | `dimension` |
| $\mu$ | `\baseIntensity` | `baseline` |
| $\kappa_{e,e'}$ | `\hawkesKernel\subscriptee` | the kernel; exponential here |
| $A$ | `\excitation` | `excitation` |
| $\beta$ | `\decay` | `decay` |
| $\Gamma = A/\beta$ | `\branchingMatrix` | `branching_matrix` |
| $\rho$ | `\branchingRatio` | `branching_ratio` |
| $S(t)$ | `\decayedCounts` | `decayed_counts` |
| $\lambda^*$ | `\stationaryIntensity` | `stationary_intensity()` |
| $\nu = \mathbf 1^\top\lambda^*$ | `\totalRate` | `stationary_intensity().sum()` |
| $\bar\lambda$ | `\totalIntensity` | `total_intensity` |
| $\Lambda$ | `\compensator` | `compensators_at_events` |
| $p$ | `\pressure` | `EventType.pressure` |
| $\Delta\lambda = p^\top\lambda$ | `\intensityContrast` | the flow-only oracle |

**$\Lambda$ is the compensator and nothing else.** The total intensity is $\bar\lambda$.
**$\kappa$ is the kernel.** The pressure contrast is $\Delta\lambda$, never $\kappa$.

## Invariants any implementation must respect

- **$A_{e,e'}$ is the influence of $e'$ on $e$** — row excited, column exciting. This makes
  $\lambda = \mu + AS$ and $\lambda^* = (I-\Gamma)^{-1}\mu$ plain products on column
  vectors, and makes the **column** sums of $\Gamma$ the readable quantity. Because
  $\rho(\Gamma) = \rho(\Gamma^\top)$, a transposed kernel passes every stability check and
  produces a stationary path of the right rate. It is a bug that still runs, and the
  convention is the only defence.
- **$A \ge 0$ and a scalar $\beta$ do different jobs.** The common $\beta$ is what makes
  $\bar\lambda$ decay as a single exponential *between events*; $A \ge 0$ is what makes the
  excess over $\bar\mu$ non-negative. The exact scheme needs both, for different reasons,
  and $\bar\lambda$ is **not** an autonomous one-dimensional process — its jump size depends
  on the type, so the full state is carried and the type draw is part of the algorithm.
- **$\rho < 1$ is checked in `__post_init__`.** Nothing downstream re-checks it.
- **$S$ is left-continuous**, $S_e(t) = \sum_{T^e_j < t}e^{-\beta(t-T^e_j)}$, with a strict
  inequality, because Definition `def.compensator` requires a predictable intensity. Name
  the pre-jump and post-jump values separately; confusing them shifts every intensity by one
  event and produces a plausible path.
- **The compensator is implemented independently of the simulator on purpose.** An
  accumulated compensator agrees with the path by construction; an independent one turns
  Meyer's theorem into a test.
- **Predictability is a property of the intensity, not of a regressor.** $\mathrm{OFI}$ is
  adapted and not predictable, and that is correct.

## Four statements that are usually got wrong

1. **$\rho$ is not the endogenous fraction**, and $1/(1-\rho)$ is not the mean cluster size.
   They coincide *in particular when* $\Gamma$ has constant column sums, and *in particular
   when* $\mu$ is a right Perron vector — neither is generic. Write "in particular when",
   never "only when". Here: $\rho = 0.6$ against $0.682$ and $3.149$.
2. **$\mathbf 1^\top(I-\Gamma)^{-1}e_j$ counts the ancestor.** It is a cluster size, not a
   descendant count. The $\mu$-weighted average is $\bar C = \nu/\bar\mu$, and
   $\bar\mu\,\bar C = \nu$ is the certificate that every event lies in exactly one cluster.
3. **Column sums of $\Gamma$ count offspring; column sums of $A$ are jumps in intensity.**
   They differ by $\beta$. Never quote them as one number.
4. **$N - \Lambda$ is a square-integrable martingale at every $\rho$**, on any finite
   horizon. Subcriticality buys a stationary version, second moments of the *state* bounded
   uniformly in $T$, and ergodicity — not the martingale. And $M$ is never $L^2$-bounded on
   $[0,\infty)$, since $\mathbb E[M_e(T)^2] = \mathbb E[\Lambda_e(T)] \to \infty$.

## The two regimes, and the sign

The package ships two flow parametrizations at the same $\rho$ and the same $\nu$. Pressure
partitions the six event types; `EXAMPLE_ORDER_FLOW_PARAMS` excites **across** the partition
(what depletes a side calls forth what refills it) and `TRENDING_ORDER_FLOW_PARAMS` excites
**within** it. Signed endogenous fraction $-0.351$ against $+0.554$.

**Contemporaneously $\mathrm{OFI}$ is the mechanical update of the mid in both** ($+0.41$,
$+0.36$). Forward, the example predicts **reversal** and the trending one **continuation**.
The sign belongs to the kernel, not to $\mathrm{OFI}$: never write that $\mathrm{OFI}$
predicts continuation without naming the regime.

The laboratory has **no adverse selection** — the replenishment mechanism is its reverse, and
the two cannot both be strong in one kernel. So $I^n$ here carries mechanical information
only. Read every OFI-versus-$I^n$ comparison asymmetrically: OFI winning is not evidence it
dominates in general; $I^n$ winning would be the stronger finding.

## How we write it here

Per `CLAUDE.md`: the clear, idiomatic version first; cleverness and optimisation after,
explained and reconciled against it. Reusable, tested code in `unito26/`; lectures and
exercises in `notebooks/`; tests in `tests/`.

The algorithms, the estimation invariants and the statistical traps are in
`references/simulation-and-estimation.md`.
