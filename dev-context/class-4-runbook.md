---
title: "Class 4 — price formation: the runbook"
subtitle: "Section 1.4 and section 1.5, slides and notebooks 07 and 08 in delivery order"
geometry: margin=2cm
fontsize: 11pt
colorlinks: true
---

# Before the class

**The class in five sentences.**

1. The update rule of section 1.1 is exact but needs the whole message stream; we want one
   number, read off the two best quotes, that tracks the mid-price.
2. That number is the *order flow imbalance* (OFI). On an idealised book the mid-price change
   over a window **is** the imbalance, times $\tau/(2\bar S)$, up to a residual of at most
   one tick. This is an identity about a window that has elapsed. It is accounting.
3. The order flow is a six-type Hawkes process with sizes. Under the idealised book each
   event contributes its signed size, so the imbalance is a functional of the flow alone.
4. The forecast of the flow over the next $h$ seconds is
   $\bar q\,\varpi^\top A\,\Phi(h)\,Z(t+)$: a linear function of the present state. The
   mid-price inherits it through the identity, residual included.
5. Whether the forecast says *continuation* or *reversal* is decided by the kernel $A$, and
   not by the imbalance. Two specifications with the same branching ratio and the same rate
   forecast opposite signs.

**The two questions.** Keep them apart all class, and say which one is on the table.

- *Does the imbalance account for the move that just happened?* Yes, by an identity
  (Proposition 1.4.3). Steps 1 to 20.
- *Does it forecast the next one?* That depends on the kernel (Proposition 1.4.16,
  Corollary 1.4.21). Steps 21 to 50.

**The two regimes.** The package ships two specifications of the flow, `resilient` and
`trending`. Same six types, same branching ratio $0.6$, same total rate $30.19$ events a
second. They differ in where the excitation goes.

- `resilient`: an event excites the types of the *opposite* pressure. What depletes a side
  begets the limit orders that refill it. After a market buy the flow is forecast to reverse.
- `trending`: an event excites the types of its *own* pressure. After a market buy the flow
  is forecast to continue.

**Timing, for 180 minutes.**

| clock | what | steps |
| --- | --- | --- |
| 0:00 -- 0:40 | slides, part A: the identity | 1 -- 14 |
| 0:40 -- 1:05 | notebook 07 | 15 -- 20 |
| 1:05 -- 1:20 | break | |
| 1:20 -- 1:40 | slides, part B: the model of the flow | 21 -- 26 |
| 1:40 -- 2:00 | notebook 08, sections 1 to 5 | 27 -- 31 |
| 2:00 -- 2:25 | slides, part C: the forecast | 32 -- 39 |
| 2:25 -- 2:45 | notebook 08, sections 6 to 12 | 40 -- 46 |
| 2:45 -- 2:55 | slides, section 1.5 | 47 -- 50 |

**If late, cut in this order.** Step 37 (the total response: say its one sentence over step
36). Step 9 (the position of the bid: set it as the exercise, in words). Step 34 (the residual
absorbing the flow: say it over step 33). In notebook 08: sections 3, 9 and 10.

**Practical.**

- Open notebooks 07 and 08 before the class. Both are stored executed. **Do not re-run
  notebook 08 in class**: sections 6, 7, 8 and 11 are Monte Carlo and take minutes. Scroll
  the stored output. Notebook 07 runs in seconds and can be run live.
- Prices in both notebooks are in ticks, so $\tau = 1$ everywhere on screen.
- `script.pdf` in `documentation/tex/slides/` has the fuller wording of every slide.

\newpage

# Part A — the identity (slides)

## 1. Slide: *Outline*

**Say.** Three classes of background lead here. Today's question: which features of the order
flow move the mid-price, and how the Hawkes apparatus captures them. Three steps: one number
read off the book; a model of the flow that produces it; a forecast of where the flow takes
the mid-price.

**Next.** Why the exact rule of class 1 is not enough.

## 2. Slide: *The exact update is too fine for the mid-price*

**Say.** The update rule of section 1.1 is exact, and it tracks every level of the book. To
run it we need the whole tape. We want something coarser: the two best quotes in, the
mid-price out.

**Show.** The table, row by row: left what the rule needs, right what we look for.

**Next.** We simplify the book until the mid-price is an explicit function of the flow.

## 3. Slide: *The idealised book*

**Say.** Four requirements, for a fixed depth $\bar S$. One: nothing happens behind the best
quotes. Two: no order reaches past the quote it acts on. Three: every queue behind a best
quote holds exactly $\bar S$, and the best quotes hold at most $\bar S$. Four: when the best
bid is full, the next limit buy arrives one tick above it; the same on the ask, one tick below.

**Say also.** This is a model. No traded book looks like this. It is the setting in which the
relation we are after is exact.

**Next.** The picture.

## 4. Slide: *Behind each touch, every queue holds $\bar S$*

**Show.** Blue is the bid, orange the ask. Only the two queues at the best quotes change size.
Everything behind them is full.

**Say.** If the best bid empties, the queue behind it becomes the best bid, and it is full:
the bid moves down one tick. If the best bid is full and a limit buy arrives, it opens a new
queue one tick up: the bid moves up one tick. So the mid-price moves by half a tick at a time,
and only when a best queue empties or a new one opens.

**Next.** The statistic.

## 5. Slide: *The order flow imbalance*

**Say.** For each event $n$, a contribution $e_n$, built from the best quotes before and after
the event. Four terms: two for the bid, two for the ask. The imbalance over a window is the
sum of the contributions of the events in the window.

**Say slowly.** The convention that is got wrong: $S^{b,1}_{T_n}$ is the size at the best bid
*after* the $n$-th event; $S^{b,1}_{T_{n-1}}$ is the size just before it.

**Next.** The formula is easier as three pictures.

## 6. Slide: *What each event contributes*

**Show.** Left: the best bid does not move; the event contributes the change in size.
Middle: the bid improves; the event contributes the whole new queue. Right: the bid is
cleared; the event contributes minus the whole old queue.

**Say.** Dashed is before the event, filled is after. The ask is the same with the signs
reversed. Positive means pressure upwards: more on the bid, or less on the ask.

**Next.** What the sum of these does to the mid-price.

## 7. Slide: *The mid-price change tracks the imbalance*

**Show.** Top: the change of the mid-price over the last second. Bottom: the imbalance over
the same second. One simulated session of the idealised book; the same figure is in notebook
07, section 3.

**Say.** They rise and fall together. One counts ticks, the other counts shares. The dashed
lines are drawn so that $2\bar S$ shares stand as tall as one tick. The next slide says
exactly how the two are related.

## 8. Slide: *The mid-price moves with the flow*

**Say.** Proposition 1.4.3. Under the idealised book, the mid-price change over a window
equals the imbalance over that window times $\tau/(2\bar S)$, plus a residual. The residual is
at most one tick in size.

**Say.** Read the slope: $2\bar S$ shares of imbalance move the mid-price by one tick. A deep
book moves less.

**Show.** The residual, second line. It depends only on the sizes at the two best quotes at
the two ends of the window. It does not depend on how long the window is.

**Say.** This is an identity about a window that has elapsed. It says nothing yet about the
future.

**Next.** Why it is true.

## 9. Slide: *The position of the bid, in shares*  (cut second if late)

**Say.** This is Exercise 1.4.4, and it proves the proposition. Measure where the bid is in
shares: the size at the best bid, plus $\bar S$ for every tick the bid has moved up. Every
bid-side event moves this position by exactly its own signed size.

**Show.** The staircase. Each time it crosses a dashed line, a multiple of $\bar S$, the bid
moves one tick.

**Say.** Do the same on the ask, subtract, and the identity is the result.

## 10. Slide: *The residual is the flow that went into the queues*

**Show.** Each dot is a window of the same session. The line has slope $\tau/(2\bar S)$. The
grey band is one tick either side. Every dot is inside the band. The dots sit in rows because
the mid-price moves by half ticks.

**Say.** The orange dots are windows over which neither quote moved. The mid-price change is
zero, the imbalance is not: shares joined or left the queues without moving a price. There the
residual cancels the flow term exactly.

**Say.** The band has the same width for every window length. The flow term grows with the
window. That is why the identity is useful over long windows and says little over very short
ones.

**Next.** So far the events were given. Now a model that generates them.

## 11. Slide: *An order is four components; the Hawkes process supplies two*

**Say.** An order is time, direction, size, price. The time is an arrival time of a Hawkes
process. The direction is the type of that arrival. The size is drawn independently. The price
is drawn last, against the book the event finds.

**Say.** The structure of the model is in the first two rows.

## 12. Slide: *The order flow is a marked Hawkes process*

**Show.** The table: six types. Market, limit, withdrawal; on each side.

**Say.** The row $\varpi$ is the *pressure*: $+1$ if the event pushes the mid-price up, $-1$ if
down. A market buy consumes the ask: $+1$. A limit buy adds to the bid: $+1$. A withdrawal
from the bid removes support: $-1$.

**Say.** Definition 1.4.6: the times and types are a six-dimensional exponential-kernel Hawkes
process, exactly as last class, with $(\mu, A, \beta)$. Sizes are i.i.d. with mean $\bar q$,
independent of the times and types.

## 13. Slide: *A limit price is a geometric offset from the opposite best quote*

**Say.** How the price is drawn. A limit buy is priced from the best ask, at one tick plus a
geometric number of ticks. Offset zero improves the best bid, or joins it if the spread is one
tick. Large offsets land behind the best bid.

**Say.** An order behind the best quote moves neither quote and contributes nothing to the
imbalance. The idealised book rules those out. A generated book has them.

## 14. Slide: *The contribution is the signed size*

**Say.** Proposition 1.4.9. Under the idealised book the contribution of an event is its
pressure times its size: $e_n = \varpi_{E_n} q_n$. So the imbalance is the sum of signed
sizes over the window.

**Say.** This is what part two of the assumption buys: each event changes one queue, by its
own size. The imbalance no longer needs the book. It is a functional of the flow.

**Next.** To notebook 07. We build the idealised book and check every statement so far.

\newpage

# Notebook 07 — the order flow imbalance

## 15. Section 1: *The idealised book*

**Show.** The figure of the opening book: best bid 3 at 1000, best ask 2 at 1020,
$\bar S = 5$, every level behind full.

**Say.** The spread is wide on purpose: a limit order at a full best quote needs a free tick
inside it.

**Show.** The print after the simulation: 1,728 messages in 60 seconds, all of size one; the
four parts of the assumption held for every message. The counts by type: limit orders the
commonest, market orders the rarest.

**Say.** The flow is the `resilient` specification. Every order has size one because parts two
and three need it: an order of two shares could reach past a queue that holds one.

## 16. Section 2: *What each event contributes*

**Show.** The table of ten scripted events. Read three rows aloud.

- Row 2, limit buy: the bid is full, 5 at 1000, so the order opens 1 at 1001. Case
  *improved*, $e_n = +1$.
- Row 3, withdrawal from the bid: the 1 at 1001 leaves, the bid is back to 5 at 1000. Case
  *cleared*, $e_n = -1$: the one share of the old queue, not the five of the new one.
- Row 8, market buy: clears the ask. $e_n = +1$.

**Say.** On every row the contribution is one share with the sign of the pressure. That is
Proposition 1.4.9, on ten events.

**If asked** about the `NaN` on row 1: the first row has no predecessor in the session.

**Show.** The ten small books under the table, one per event.

## 17. Section 3: *The order flow imbalance over a window*

**Show.** The three prints saying `True`: three ways to compute the imbalance agree.

**Show.** The figure with two panels. Top the mid-price change over one second, bottom the
imbalance over the same second.

**Say.** They move together. Section 4 says exactly how.

## 18. Section 4: *The mid-price moves with the flow*

**Show.** The print: 1,999 random windows, from 1.4 milliseconds to 57 seconds long. Slope
$0.1$, which is $\tau/(2\bar S)$ with $\bar S = 5$. Identity in integers: largest error
$0.0$. Largest residual: $0.8$ ticks.

**Say.** No tolerance. The identity holds exactly on every window. The residual never reaches
a tick.

**Show.** The scatter: every window inside the band.

**Show.** The staircase, *The position of the bid, in shares*: the best bid falls from 999 to
995, and it steps exactly when the position crosses a dashed line.

## 19. Section 5: *The residual is the flow that went into the queues*

**Show.** The print: 224 windows over which neither quote moves. On 169 of them the imbalance
is not zero. On all of them the mid-price change is zero.

**Show.** The table by window length. The flow term's spread grows from $0.30$ to $1.95$
ticks. The residual's stays at about $0.28$.

**Say.** Over short windows the two are the same size and the identity says little. Over long
windows the flow term dominates.

## 20. Section 6: *The contribution is the signed size*

**Show.** The print: $e_n$ equals pressure times size on all 1,727 rows.

**Show.** The last table, on a book that is *not* idealised. The third order is a market buy
of 200 against a best ask holding 120. It registers 120.

**Say.** On a general book an order that reaches past the best quote registers only what the
best quote held. The imbalance then reads the book, and not the flow alone. Part two of the
assumption is what rules that out.

**Then.** Break.

\newpage

# Part B — the model of the flow (slides)

**Open with.** Before the break: an identity about the past. Now the forward question. Given
everything observed up to now, where does the flow go next?

## 21. Slide: *Direction symmetry*

**Say.** $\Sigma$ swaps buy and sell: market buy with market sell, limit buy with limit sell,
and so on. It turns the pressure into its opposite.

**Say.** Definition 1.4.12. The specification is *direction-symmetric* if swapping buy and
sell leaves it unchanged: $\Sigma A \Sigma = A$ and $\Sigma\mu = \mu$.

**Say, in plain words.** The market has no built-in direction. Whatever it does to buys, it
does to sells. Every forecast of today rests on this.

**Why we assume it.** Without it the model has a drift built into its parameters, and a
forecast would mostly report that drift. With it, anything the model forecasts about direction
comes from what just happened.

## 22. Slide: *Contracted with $\varpi$, the baseline drops out*

**Say.** Proposition 1.4.13. Take any matrix $M$ that the swap leaves alone, and any vector
$v$ that the swap leaves alone. Then $\varpi^\top M v = 0$.

**Say.** The proof is one line: the swap changes the sign of $\varpi$ and nothing else, so the
number equals minus itself.

**Say.** Consequences: $\varpi^\top\mu = 0$, and $\varpi^\top\lambda^* = 0$. On average, as
much pressure up as down. And every matrix the forecast is built from qualifies.

## 23. Slide: *The kernel carries the mechanism of replenishment*

**Show.** Two pictures of the branching matrix, in four blocks. Columns: the type that
excites. Rows: the type that is excited. The blocks separate pressure $+1$ from pressure
$-1$.

**Say.** Left, the `resilient` regime: the mass is off the diagonal blocks. An event of
pressure $+1$ excites events of pressure $-1$. A market buy empties the ask, and what follows
is limit sells that refill it.

**Say.** Right, the `trending` regime: the mass is on the diagonal blocks. An event excites
events that push the same way.

**Say.** Same six types, same branching ratio, same total rate. Only the placement of the mass
differs.

## 24. Slide: *Choose the structure and the rate; the baseline follows*

**Say.** How a specification is built. We choose the branching matrix and the stationary rates
we want, and read the baseline off: $\mu = (I - \Gamma)\lambda^*$. It must come out positive.
Where it would be negative the target cannot be reached at that branching ratio.

## 25. Slide: *The intensity contrast*

**Say.** Definition 1.4.14. $\lambda^\uparrow$ sums the intensities of the three types that
push up, $\lambda^\downarrow$ of the three that push down. The contrast is the difference:
$\Delta\lambda = \varpi^\top\lambda$.

**Say.** It says which way the flow is leaning right now. Under direction symmetry the
baseline term vanishes, and the contrast is $\varpi^\top A Z(t)$: a function of the state.

**Remind.** $Z$ is the state of last class: for each type, the count of past events, each
discounted by $e^{-\beta\,\cdot\,\text{age}}$.

## 26. Slide: *Signed excitation*

**Say.** Proposition 1.4.15. For each type, one number: $\theta_e =
(\varpi^\top A)_e/\varpi_e$. It takes the same value on the two members of a pair.

**Say, in plain words.** One event of type $e$ raises the intensity of the types that push
its own way, relative to those that push the other way, by $\theta_e$.

**Say.** $\theta > 0$: the type begets its own pressure. $\theta < 0$: it begets the opposite.
The sign is a property of the kernel. The same six types carry either sign.

**Next.** To notebook 08, sections 1 to 5.

\newpage

# Notebook 08, sections 1 to 5 — reading the model

## 27. Section 1: *Six types, and two regimes*

**Show.** The second table. Branching ratio $0.600$ in both. Total rate $30.188$ in both.
Signed endogenous fraction: $-0.351$ for `resilient`, $+0.554$ for `trending`.

**Say.** The last line is the difference. On balance the offspring of an event push against it
in the resilient regime and with it in the trending one.

## 28. Section 2: *Direction symmetry*

**Show.** The first table: both regimes are symmetric, and $\varpi^\top\mu$ and
$\varpi^\top\lambda^*$ are zero to rounding.

**Show.** The broken example: one entry of the kernel halved. $\varpi^\top\mu$ is still $0$,
and $\varpi^\top\lambda^* = -0.90$.

**Say.** So the hypothesis is on the kernel as well as on the baseline. A balanced baseline is
not enough.

**Show.** The two heat maps. They are the slide of step 23 with the real numbers: $73.5\%$ of
the mass across the partition in the resilient regime, $1.7\%$ in the trending one.

## 29. Section 3: *Choosing a specification*  (skip if late)

**Show.** The two refusals: past a certain branching ratio the constructor names the
components of the baseline that went negative.

## 30. Section 4: *The intensity contrast along a path*

**Show.** The figure: the contrast over two seconds. It jumps at events and decays between
them.

**Say.** Open circles: the contrast just before an event. Filled: just after, with that event
included. A forecast made at an event uses the filled value, $Z(T+)$: the event just observed
is information.

## 31. Section 5: *Signed excitation, pair by pair*

**Show.** The table of $\theta$.

| pair | `resilient` | `trending` |
| --- | --- | --- |
| market | $-1.900$ | $+2.656$ |
| limit | $0.000$ | $+1.770$ |
| withdrawal | $-3.108$ | $+2.656$ |

**Say.** Resilient: a market order and a withdrawal beget the opposite pressure; a limit order
begets neither. Trending: every type begets its own pressure.

**Then.** Back to the slides for the forecast.

\newpage

# Part C — the forecast (slides)

## 32. Slide: *The short-horizon forecast*

**Say first.** This is the frame the chapter exists for.

**Say.** Proposition 1.4.16. Stand at time $t$. The expected signed size of the flow over the
next $h$ seconds is $\bar q\,\varpi^\top A\,\Phi(h)\,Z(t+)$.

**Read the right side, factor by factor.**

- $Z(t+)$: the state now, including the event at $t$ if there is one.
- $\Phi(h) = \int_0^h e^{Ks}ds$: how that state is expected to evolve over the horizon. It is
  the forward mean of last class.
- $A$: turns state into intensity.
- $\varpi^\top$: keeps the direction, up minus down.
- $\bar q$: the mean size.

**Say.** The forward mean of last class has three terms; two are baseline terms. Direction
symmetry removes both. What remains is linear in the state.

**Say.** Under the idealised book the left side is the imbalance over $(t, t+h]$. So this is
a forecast of the imbalance.

## 33. Slide: *The forecast of the mid-price*

**Say.** Corollary 1.4.17. Take the identity of step 8 over the window $(t, t+h]$ and take
expectations. The expected mid-price change is the forecast of the flow times
$\tau/(2\bar S)$, plus the expected residual.

**Say.** The residual stays in the formula. Two reasons, on the next two slides.

## 34. Slide: *The residual absorbs the flow until a quote moves*  (cut third if late)

**Show.** Dashed: the flow term. Blue: the expected mid-price change. Orange: the expected
residual.

**Say.** At short horizons the flow arrives but no quote has moved yet. The shares sit in the
queues. The mid-price lags the flow, and the residual is minus the flow term. First reason:
the residual is not independent of the flow.

## 35. Slide: *The residual bounds what the forecast can say*

**Say.** Second reason. With $\rho < 1$ the flow term tends to a finite limit as the horizon
grows: one event has finitely many descendants. The residual is bounded by one tick at every
horizon.

**Say.** So a longer horizon does not buy a bigger forecast. The forecast says something about
the mid-price only when the state is loaded enough for the limit to reach a tick.

**Say.** That is why the empirical question of section 1.5 is about the *sign* of the
forecast, and not about its size.

## 36. Slide: *The contrast is the drift of the imbalance*

**Say.** Corollary 1.4.19. For a small horizon, $\Phi(h)$ is about $h$ times the identity. So
the forecast of the imbalance is $\bar q\,\Delta\lambda(t+)\,h$: the intensity contrast is the
drift of the imbalance.

**If step 37 is cut, add.** At the other end, as $h$ grows, the forecast settles at the whole
expected progeny of the present state, and it settles faster than the relaxation time.

## 37. Slide: *The forecast finishes before the relaxation time*  (cut first if late)

**Say.** Remark 1.4.20. As $h \to \infty$, $A\Phi(h)$ tends to $\Gamma(I-\Gamma)^{-1}$: the
direct offspring and all their descendants.

**Say.** Last class the slowest mode decayed at rate $\beta(1-\rho)$. That mode is symmetric
between buys and sells, so $\varpi$ does not see it. The forecast decays at the next rate,
which is faster.

## 38. Slide: *The sign belongs to the kernel*

**Show.** Two curves of $\theta_a(h)$ against the horizon: one positive, *continuation*; one
negative, *reversal*.

**Say.** Corollary 1.4.21. $\theta(h)$ is the signed excitation carried over a horizon $h$.
One extra event of type $a$ against one fewer of its mirror moves the forecast by
$2\bar q\,\theta_a(h)$.

**Say slowly.** The sign of $\theta_a(h)$ decides whether an excess of buys is forecast to
continue or to reverse. That sign belongs to the kernel. Two specifications with the same
branching ratio and the same rates carry opposite signs, and the identity of step 8 holds in
both.

**Say.** So we never say "the order flow imbalance predicts continuation" without naming the
specification.

## 39. Slide: *Three statistics of the same past flow*

**Show.** The table. Three ways to summarise the recent flow, and how each weights a past
event: by age, by size, by type.

- the signed count over a window: flat in age, no sizes;
- the decayed signed count $\varpi^\top Z$: exponential in age, no sizes;
- the imbalance: flat in age, with sizes.

**Say.** The forecast uses none of the three. It weights by age through the kernel, and by
type through $\theta(h)$.

**Say.** So the imbalance needs no parameters, and it estimates the forecast only up to two
gaps: the weighting, and the sizes. The first gap closes when $\theta$ is the same for all
types. The second never closes: the state does not know the sizes.

**Next.** To notebook 08, section 6.

\newpage

# Notebook 08, sections 6 to 12 — the forecast against simulation

**Reminder.** Do not re-run. Scroll the stored output.

## 40. Section 6: *The short-horizon forecast against Monte Carlo*

**Say what is tested.** The formula of step 32, against 20,000 simulated paths from one fixed
state, in each regime.

**Say which state, and why.** The state is $m + e_{\text{MB}}$: the mean state, plus one
market buy that has just arrived. The forecast depends on the state only through its
deviation from the mean state: the mean state itself forecasts zero, because it is symmetric
between buys and sells. So from $m + e_{\text{MB}}$ the forecast is the response of the flow
to one market buy, and it equals $\bar q\,\theta_{\text{MB}}(h)$.

**Say how.** Each path continues from that state for three seconds. The expected flow over
$(t, t+h]$ depends on $h$ and on the state at $t$ only, so the simulation puts $t$ at zero.

**Show.** The first table, the row $h = 1$ s. Resilient: formula $-48.0$ shares, Monte Carlo
$-51.9$, standard error $3.8$. Trending: formula $+97.6$, Monte Carlo $+98.1$, standard error
$5.9$.

**Show.** The two figures: the formula runs through the error bars at every horizon.

**Say.** After a market buy: the resilient regime forecasts selling pressure, the trending
regime buying pressure. Same event, opposite forecasts.

**Show.** The last print of the section: read *before* the market buy, the forecast would be
zero. The Monte Carlo is 8 to 22 standard errors from zero. Which state is read matters.

## 41. Section 7: *The forecast of the mid-price, on an idealised book*

**Say.** The same paths, now folded into an idealised book with $\bar S = 3$. Each path
records the mid-price.

**Show.** The print: the identity holds on every path and at every horizon; the largest
residual is $0.333$ ticks.

**Show.** The figure with three curves, *the three terms*. Dashed: flow term. The mid-price
change follows it. The residual is small after the first tenth of a second.

**Show.** The table with the column *no quote moved*: $98.5\%$ of paths at 10 milliseconds,
$54\%$ at a tenth of a second, none after a second. While no quote has moved the residual is
exactly minus the flow term.

**Show.** The second figure, $\bar S = 12$: *the price inherits the flow late*. On a thicker
book the mid-price lags the flow for longer. This is the slide of step 34, measured.

## 42. Section 8: *The residual bounds the forecast*

**Show.** The print. From one extra market buy, the flow term settles at $-0.113$ ticks
(resilient) and $+0.266$ ticks (trending). Well inside one tick.

**Say.** It takes a burst to reach a tick: nine market buys in the resilient regime, four in
the trending one.

**Show.** The figure: the dotted curves, one market buy, stay inside the grey band. The solid
curves, the burst, reach its edge, and the simulated mid-price follows.

## 43. Section 9: *The contrast is the drift of the imbalance*  (skip if late)

**Show.** Left panel: the forecast and its tangent at $h = 0$. The slope of the tangent is the
contrast, $-1.90$ and $+2.66$: the $\theta_{\text{MB}}$ of step 31.

## 44. Section 10: *The total response*  (skip if late)

**Show.** The last table of the section: the forecast decays at rates $2.79$ and $4.00$ per
second (resilient) and $1.68$ (trending). The relaxation rate is $1.6$. Every pair finishes
faster.

## 45. Section 11: *The sign belongs to the kernel*

**Show.** The figure of $\theta(h)$: three curves per regime. Resilient at or below zero,
trending above zero, at every horizon.

**Show.** The table *difference*: an extra market buy against an extra market sell. At
$h = 1$ s: $-96$ shares in the resilient regime, $+195$ in the trending one.

**Say.** The same excess of buys over sells: reversal in one specification, continuation in
the other.

**Say also.** At a general state the two need not disagree. The notebook exhibits a state from
which both forecast upward flow. Along an ordinary path they agree in sign at 9 of 41 events.

## 46. Section 12: *Three statistics of the same past flow*

**Show.** The five numbers at one instant of the path.

| statistic | value |
| --- | --- |
| signed count over 1 s | $-3$ events |
| decayed count $\varpi^\top Z(t+)$ | $-1.25$ events |
| imbalance over 1 s | $-170$ shares |
| forecast over 1 s, `resilient` | $+174$ shares |
| forecast over 1 s, `trending` | $-183$ shares |

**Say.** The three statistics agree in sign: recent flow was selling. The two forecasts
disagree with each other. The resilient regime forecasts buying, against the three statistics;
the trending regime forecasts selling, with them.

**Show.** The last print: redraw the sizes of the same events, and the imbalance moves from
$-1250$ to $+60$ while the state and the forecast do not move at all.

**Say.** Only the imbalance sees the sizes. No function of the state recovers them.

**Show.** *What to take away*, the last cell. Read its four paragraphs as the summary of the
notebook.

\newpage

# Section 1.5 — what the generated setting cannot settle (slides)

## 47. Slide: *Outline*

**Say.** Everything today was on flow that we generate. A result on generated flow is a result
about the generator. Four things are absent by construction.

## 48. Slide: *The intensities do not read the book*

**Say.** In our model the arrival rates do not look at the queues. In a traded market they do.
A resting limit order is filled when someone wants to trade against it, which is more often
when that trade is right. Those who posted it defend themselves by withdrawing first.

**Say.** So in a traded book a thin queue is thin for a reason, and depletion begets
depletion. That is the opposite of replenishment. The queue imbalance at the best quotes,
$I^1$, carries that information in a traded book. Here it cannot.

## 49. Slide: *What the generated setting also lacks*

**Show.** The table, four rows: sizes that depend on the flow; a second timescale; intraday
patterns; an anchor for the price level.

## 50. Slide: *Read the comparison asymmetrically*

**Say.** On generated flow, whatever the queue imbalance forecasts is mechanical. So a result
that favours it is the stronger finding, and a result that favours the order flow imbalance
is not evidence that it wins in a traded market.

**Close with.** What recorded data settles: which sign $\theta$ carries in a traded market,
and at which window and which horizon the sign can be read from the imbalance. That is the
assignment of the chapter, in section 1.5 of the notes: build the session from a LOBSTER pair,
compute the two statistics, regress, and read the sign across windows and horizons.

\newpage

# If asked

**Is the imbalance the signed traded volume?** No. Limit orders and withdrawals at the best
quotes count as much as trades. And on a general book only what happens at the best quotes
counts.

**Is the idealised book realistic?** No. It is the setting in which the relation is an
identity. On recorded data the relation is a regression, with a slope that falls as the depth
rises; that is the empirical finding of Cont, Kukanov and Stoikov.

**Why read the state after the event, $Z(t+)$?** Because the event at $t$ has been observed.
$Z$ is left-continuous: $Z(t)$ does not include it, $Z(t+) = Z(t) + e_E$ does. Notebook 08,
section 6, shows the Monte Carlo telling the two apart.

**Why does the forecast stop growing with the horizon?** At $\rho < 1$ an event has a finite
expected number of descendants, $\Gamma(I-\Gamma)^{-1}$ in all.

**Which regime is the real market?** The model does not say. Both are admissible at the same
branching ratio and the same rate. It is the question of the assignment.

**Why the mean state $m$ in the experiment?** Any state would do. From $m$ the forecast is
zero, so adding one market buy to it isolates the response to that one order.

**Why an exponential kernel?** It makes $(N, Z)$ Markov, as last class: the whole past enters
through six numbers.
