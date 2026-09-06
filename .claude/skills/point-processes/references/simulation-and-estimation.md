# Simulation and estimation

The algorithms of `chap.hawkes` §6, and the statistical traps that the lattice-valued
outcome sets. Load the chapter for the derivations; this file is what an implementation
needs at hand.

## The conditional survival function

Everything rests on it:

$$\mathbb P(T_{n+1} - T_n > s \mid \mathcal F_{T_n})
 = \exp\Big(-\int_{T_n}^{T_n+s}\bar\lambda(u)\,du\Big),$$

with $\bar\lambda$ evaluated on the event that no arrival occurs in the interval, which
makes the right-hand side $\mathcal F_{T_n}$-measurable and therefore invertible.

## Dassios–Zhao, exact

With a common $\beta$, $\bar\lambda(t) = \bar\mu + D e^{-\beta(t-T_n)}$ between events,
$D := \bar\lambda(T_n^+) - \bar\mu \ge 0$ by $A \ge 0$. So the survival function factorises
and the wait is a minimum of two independent draws. For $U_1, U_2 \sim \mathrm{Unif}(0,1)$:

$$\tau_1 = -\frac{\ln U_1}{\bar\mu},
\qquad
\tau_2 = -\frac1\beta\ln\Big(1 + \frac{\beta\ln U_2}{D}\Big),
\qquad T_{n+1} - T_n = \tau_1 \wedge \tau_2,$$

with $\tau_2 := +\infty$ exactly when $-\ln U_2 \ge D/\beta$. **That is not an edge case to
patch.** The excited part carries the finite total mass $D/\beta$ and expires without firing
with probability $e^{-D/\beta}$; clipping instead of returning infinity biases the immigrant
share.

Then draw the type on the **pre-jump** intensities,
$\mathbb P(E_{n+1} = e) = \lambda_e(T_{n+1}-)/\bar\lambda(T_{n+1}-)$. This step is where the
full matrix $A$ re-enters — the wait saw only its column sums — and the scheme is not
defined without it.

$O(1)$ per event, exact, no rejection, no discretisation, no time grid.

## Ogata thinning, the control

Kept because it applies to any kernel and because an independent route is what makes
agreement meaningful. Its majorant is free: with $A \ge 0$ the total intensity is
non-increasing between events, so the value at the last event dominates it. Draw
$U \sim \mathrm{Exp}(\bar\lambda(t))$, accept with probability
$\bar\lambda(t+U)/\bar\lambda(t)$, else advance and repeat.

## Goodness of fit

Meyer's theorem, with **three** hypotheses: no two components jump simultaneously; each
compensator is continuous; each diverges. Rescaling each component's clock by its own
compensator gives **mutually independent** unit-rate Poisson processes.

Hypothesis (i) is what buys the joint independence — the univariate statement needs no
orthogonality — and it is exactly what fails on recorded data, where one aggressive order
is reported as several fills sharing a timestamp.

**A KS test of each margin against $\mathrm{Exp}(1)$ tests the margins and nothing else.**
It leaves both independences of the theorem untested: serial within a component, and joint
across components. Say so rather than claiming the model is validated.

## The lattice, and what it breaks

$\Delta P^m$ lives on a half-tick lattice with a large atom at zero. Four consequences that
have each been got wrong at least once here.

**Never quantile-bin the outcome.** Every interior quantile equals zero, `np.unique`
collapses the edges to one, and the two surviving bins are $\{\Delta P < 0\}$ and
$\{\Delta P \ge 0\}$ — which merges flat with up. Bin the **predictor**; take the outcome as
the three sign classes. Return the realised bin count, since ties can collapse the
predictor's bins too and comparisons are valid only at a fixed realised count.

**Miller–Madow for a mutual information is a subtraction:**

$$\hat I_{MM} = \hat I - \frac{\hat m_{xy} - \hat m_x - \hat m_y + 1}{2N},$$

occupied cells, nats. The entropy correction $+(\hat m - 1)/2N$ applied to an MI *doubles*
the bias. And it removes only the $O(1/N)$ term at the nominal row count: on serially
dependent rows the bias scales as $1/n_{\text{eff}}$, so a residual survives that is of the
same order as the effects measured.

**An i.i.d. permutation null is anti-conservative here.** On these rows it understates the
null mean by about four and the null spread by about five. Use a **circular-shift** null:
rotate one series by a uniform offset of at least twice the Politis–White block length,
recompute, 999 draws. It preserves each series' autocorrelation and destroys only the
cross-dependence.

**Hill's tail index is undefined on a discrete outcome.** At a 1% tail threshold most tail
observations tie the threshold exactly and contribute $\log 1 = 0$; the estimate reports the
lattice spacing, and diverges when the tail is a single lattice value. Report Hill on the
**regressors**; carry the outcome's tail with the participation ratio, $P(\Delta P = 0)$,
the realised support and the top-0.1% share of $\sum(\Delta P)^2$.

## Two identities worth knowing

**In-sample and unshrunk**, the binned three-class log-score skill is
$\hat I(\mathrm{bin}(x); \mathrm{class}(y))/\hat H(\mathrm{class}(y))$. It is *not* equal to
the out-of-fold shrunk skill the study reports, which is typically two to four times
smaller. Report both and say which is which; mutual information is not free.

**Transfer entropy conditions on the target's past only**,
$T_{X\to Y} = I(x_t;\,y_{t\to t+h}\mid y_{t-h\to t})$. Adding the source's own past gives a
different quantity that vanishes when $x$ is nearly a function of its own past — which a
window sum is. The reverse direction needs a forward increment of $x$, not the same function
with arguments swapped. **Never report the difference of the two directions**: a common
unobserved driver — here the Hawkes state, which drives flow and price jointly — makes it
non-zero under no predictive relation at all.

## Sample size

At $\nu = 30.19$/s a 3600 s session gives about 108,700 rows and
$\hat H(\mathrm{class}) \approx 0.30$ nats. Plug-in MI bias is
$(m_x-1)(m_y-1)/2n_{\text{eff}}$: about $4.6\times10^{-5}$ at $n_{\text{eff}} = N$, but the
relaxation $1/(\beta(1-\rho)) = 0.625$ s spans roughly nineteen events, so the realistic
figure is nearer $9\times10^{-4}$ — the same order as the signal. Keep bins at 6, print the
bias beside every estimate, and keep the confirmatory claim on the out-of-fold incremental
log-score skill.

For non-overlapping buckets, $T/b$ rows: **two** at half-hour buckets on a 3600 s session,
where an intercept-and-slope fit returns $R^2 = 1$ by arithmetic. The grid rule $T/b \ge 50$
binds, so $b \le 72$ s on one session; anything coarser needs pooling, and pooled rows are
demeaned **within seed** because the price level has no anchor.
