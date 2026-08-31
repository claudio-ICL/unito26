# Notation for order-driven markets

Notation and the mechanics of order-driven markets.
Lecture notes, slides, notebooks and package code should all denote the same objects in the same
way, and have the same mechanics. 

**Sources.** The symbols are defined once, as macros, in
[`tex/include/notation.tex`](tex/include/notation.tex); the statements are developed in
[`tex/notes/orderdriven/sections/order_driven_markets.tex`](tex/notes/orderdriven/sections/order_driven_markets.tex).
This file restates them in one readable place and adds the Python identifier each symbol
maps to. **If this file and the `.tex` ever disagree, the `.tex` wins** — fix this file.

---

## 1. The limit order

A **limit order** is the fundamental action available to a participant in an order-driven
market. It is the 4-tuple

$$(t, q, p, d), \qquad q \ge 0, \quad p \ge 0, \quad d \in \{-1, +1\}.$$

| component | meaning |
| --- | --- |
| $t$ | time of submission (the timestamp) |
| $q$ | size, in number of shares |
| $p$ | limit price |
| $d$ | direction: $d = +1$ buy, $d = -1$ sell |

A participant who *posts* $(t,q,p,d)$ commits at time $t$ to buy ($d=+1$) or sell ($d=-1$)
the amount $q$ at price $p$, where $p$ is the **highest** price she will pay if $d=+1$ and
the **lowest** price she will accept if $d=-1$. The single expression $pd$ turns both cases
into one: an order is willing to trade at any $\pi$ with $\pi d \le p d$.

By regulation $p$ is an integer multiple of a fixed **tick size** $\tau > 0$. A participant
may also withdraw a commitment by **cancelling** a previously submitted order.

A **trading epoch** $E$ is the collection of all limit orders submitted within a time
interval. Orders cannot be submitted simultaneously, so an order is identified by its
timestamp: formally, $E$ is the graph of a function from a subset of the positive half-line
into $\{(q,p,d) : q \ge 0,\ p \ge 0,\ d = \pm 1\}$. Uniqueness of timestamps is exactly what
makes the priority relation of §2 a *total* order.

An order $(t,q,p,d) \in E$ is **active** (outstanding) at time $u$ if $t \le u$ and by time
$u$ it has been neither executed nor cancelled.

## 2. Matching and priority

When $(t,q,p,d)$ arrives, the matching algorithm searches the active orders with timestamp
$s < t$ and *opposite* direction $-d$. An active order $(s,\rho,\pi,-d)$ **matches** the
incoming order if

$$\pi d \le p d .$$

On a match, $\rho \wedge q$ shares are transacted **at the resting order's price $\pi$**. 
The two orders are replaced by

$$(s, \tilde\rho, \pi, -d), \qquad (t, \tilde q, p, d), \qquad
\tilde\rho = \rho - \rho \wedge q, \quad \tilde q = q - \rho \wedge q,$$

and at least one of $\tilde\rho, \tilde q$ is zero. If $\tilde\rho = 0$ the resting order
leaves its queue. If $\tilde q = 0$ the incoming order is fully executed and the search
stops; if $\tilde q > 0$ the search continues.

The search follows **price-time priority**: on the side $-d$,

$$(s,\rho,\pi,-d) < (s',\rho',\pi',-d)
\iff (d\pi < d\pi') \vee \big((\pi = \pi') \wedge (s < s')\big).$$

Better price first — where "better" is *lower* for the ask side when a buy order comes in,
*higher* for the bid side when a sell order comes in, which $d\pi < d\pi'$ expresses in one
line — and, at equal price, earlier submission first. Because timestamps within an epoch are
unique, this relation is a total order on each side (Lemma `lemma.orderingOfOrders`), which
is what licenses speaking of "the queue" at all.

## 3. Queues and the book configuration

The **ask** and **bid order queues** at time $t$ are the sets of active orders on each side:

$$A_t := \{(s,q,p,-1) \in E : \text{active at } t\}, \qquad
B_t := \{(s,q,p,+1) \in E : \text{active at } t\}.$$

A **limit order book** is a grid of equally spaced prices, spacing $\tau$, increasing left to
right, with the outstanding orders queuing at each node. Buy offers sit on the left (the
**bid side**), sell offers on the right (the **ask side**), and the two never overlap: a buy
order at or above a resting sell order would have been matched on arrival rather than
rested. This is a consequence of the matching rule, not an extra assumption — and it is the
invariant to assert in code.

The configuration at time $t$ is fully described by:

| symbol | definition |
| --- | --- |
| $P^a_t$ | **best ask price** — lowest price with sell offers active at $t$ |
| $P^b_t$ | **best bid price** — highest price with buy offers active at $t$ |
| $P^{a,i}_t = P^a_t + (i-1)\tau$ | price of the $i$-th ask level, $i = 1, 2, \dots$ |
| $P^{b,i}_t = P^b_t - (i-1)\tau$ | price of the $i$-th bid level, $i = 1, 2, \dots$ |
| $V^{a,i}_t = \sum_{\{(s,q,P^{a,i}_t,-1) \in A_t \,:\, s \le t\}} q$ | **volume** at the $i$-th ask level |
| $V^{b,i}_t = \sum_{\{(s,q,P^{b,i}_t,+1) \in B_t \,:\, s \le t\}} q$ | **volume** at the $i$-th bid level |

so the state is $\big(P^a_t,\ P^b_t,\ \{(V^{a,i}_t, V^{b,i}_t) : i = 1,2,\dots\}\big)$.

Two conventions that matter for code:

- **"Volume" means the sum of the sizes queuing at one price level**, measured in shares. The
  literature also calls it the *size* of the queue. It is not a traded volume.
- Levels are **1-indexed** and indexed *relative to the best price on their own side*, so
  level $i$ names a different absolute price as the best price moves. Intermediate levels may
  be empty ($V^{a,i}_t = 0$ for some $i$ with $V^{a,j}_t > 0$, $j > i$); by convention
  $V^{a,j}_t = V^{b,j}_t = 0$ for $j \le 0$ — not stated in the notes, but required to make
  the shifted index in §5 well defined.
- **This is the *grid* indexing, and it is not the one a market-data file uses.** LOBSTER
  and its kind index by *occupied* level, skipping the empty positions this section admits.
  The two coincide only on a book with no holes, and every quantity indexed by level —
  $I^n$ above all — means something different under each.
  [`grid-levels-and-lobster-levels.md`](grid-levels-and-lobster-levels.md) is the reference
  for the difference and for the code that keeps the two apart.

## 4. Derived quantities

| quantity | symbol | definition |
| --- | --- | --- |
| spread | $\phi_t$ | $\lvert P^a_t - P^b_t \rvert$ |
| mid-price | $P^m_t$ | $(P^a_t + P^b_t)/2$ |
| $n$-level volume (queue) imbalance | $I^n_t$ | $\dfrac{\sum_{i \le n} V^{b,i}_t - \sum_{i \le n} V^{a,i}_t}{\sum_{i \le n} V^{b,i}_t + \sum_{i \le n} V^{a,i}_t}$ |

$I^n_t \in [-1, +1]$, **bid minus ask over the total** — bid-heavy is positive. It is widely
accepted as a reliable signal for the next mid-price move (Cartea, Donnelly and Jaimungal,
2018): close to $+1$ the mid-price will likely rise, close to $-1$ it will likely fall.
Getting this sign backwards silently inverts every signal built on it.

## 5. The update rule

**Proposition (`prop.lobUpdate`).** Let a sell limit order $(t,q,p,-1)$ arrive at time $t$
into the book $\big(P^a_{t-}, P^b_{t-}, \{(V^{a,i}_{t-}, V^{b,i}_{t-})\}\big)$. Put

$$N_v := \inf\Big\{n \ge 0 : q < \sum_{i=1}^{n} V^{b,i}_{t-}\Big\}, \qquad
N_p := \inf\{n \ge 1 : P^{b,n}_{t-} < p\}, \qquad
N := \max\big(0,\ N_v \wedge N_p - 1\big),$$

$$q^{i} := \max\Big(0,\ q - \sum_{k=1}^{i \wedge N_v \wedge (N_p-1)} V^{b,k}_{t-}\Big)
        = \max\Big(0,\ q - \sum_{1 \le k \le i} V^{b,k}_{t-}\mathbf{1}_{\{P^{b,k}_{t-} \ge p\}}\Big),$$

$q^i$ being the quantity still to be executed once the first $i$ levels have been consumed.
$N_v$ is where the size runs out, $N_p$ is where the price constraint bites, and $N$ is the
number of bid levels fully consumed.

Both infima can be over an empty set, with $\inf\emptyset = +\infty$: $N_v = +\infty$ when $q$
exceeds the price-eligible bid volume, and $N_p = +\infty$ for a market order ($p = 0$), since
prices are non-negative so $P^{b,n}_{t-} < 0$ never occurs. **The formulae below assume the
incoming order does not exhaust the price-eligible side.** If it does, that side empties and
$P^b_t$ is undefined — for a market order $N = +\infty$, and for a price-limited order the
formula names an empty price: a sell of 500 at $p = 9.98$ on the book of §8 consumes the whole
bid side (450) and yields $P^b_t = P^{b,4}_{t-} = 9.97$, where nothing rests. Code must branch
on the exhausted-side case, and must not compute $N_v$ by a loop that assumes termination.
Then

$$
\begin{aligned}
P^b_t &= P^{b,1+N}_{t-}, \\
V^{b,k}_t &= V^{b,k+N}_{t-} - \big(q^{k+N-1} - q^{k+N}\big), && k = 1,2,\dots \\
P^a_t &= P^a_{t-} - \max\big(0,\ P^a_{t-} - p\big)\,\mathbf{1}_{\{q^{\infty} > 0\}}, \\
V^{a,k}_t &= V^{a,\,k + \delta P^a_t/\tau}_{t-} + q^{\infty}\,\mathbf{1}_{\{p \,=\, P^a_t + (k-1)\tau\}}, && k = 1,2,\dots
\end{aligned}
$$

where $\delta P^a_t = P^a_t - P^a_{t-} \le 0$ is the jump of the best ask. For a buy limit
order $(t,q,p,+1)$ the rules are the same with the two sides interchanged and the
inequalities reversed.

Reading the four lines: the bid side is shifted up by $N$ consumed levels and the new best
bid may be partially eaten (by $q^{N} - q^{N+1}$); the ask side is untouched unless something is left over
($q^\infty > 0$), in which case the residual rests at $p$, improving the best ask when
$p < P^a_{t-}$ and shifting every ask index by $-\delta P^a_t/\tau$ levels.

## 6. Decomposition: every limit order is a market order plus a resting order

**Proposition (`prop.decompositionOfLimitOrder`).** Given the book at $t-$, processing the
sell limit order $(t,q,p,-1)$ is equivalent to processing the ordered pair

$$\big[(t, q_M, 0, -1),\ (t, q - q_M, p, -1)\big], \qquad
q_M := \min\Big(q,\ \sum_{i \ge 1} V^{b,i}_{t-}\mathbf{1}_{\{P^{b,i}_{t-} \ge p\}}\Big),$$

the first having priority over the second. Symmetrically, the buy limit order $(t,q,p,+1)$
is equivalent to

$$\big[(t, q_M, \infty, +1),\ (t, q - q_M, p, +1)\big], \qquad
q_M := \min\Big(q,\ \sum_{i \ge 1} V^{a,i}_{t-}\mathbf{1}_{\{P^{a,i}_{t-} \le p\}}\Big).$$

The first component is the **market order**: $p = 0$ for a sell and $p = \infty$ for a buy
are the price specifications that guarantee immediate execution, so none of $q_M$ is queued.
The second component is exactly the part that rests. Note $q - q_M = q^{\infty}$ in the
notation of §5.

This decomposition is the single most useful structural fact for implementation: a matching
engine needs **one** code path — consume, then rest the remainder — not a separate one for
"marketable" and "passive" orders.

A sell market order $(t,q_M,0,-1)$ **walks the book** if $q_M > V^{b,1}_{t-}$, which implies
$N \ge 1$ in §5; likewise for a buy market order against $V^{a,1}_{t-}$. The converse fails:
an order that exactly clears the best level ($q_M = V^{b,1}_{t-}$) gives $N = 1$, because the
best price moves, yet the trade prints at a single price and nothing is walked.

**Trades are market orders with $q_M > 0$.** Over a window $[0,T]$, the seller-initiated
trades are $\{(t,q_M,0,-1) : q_M > 0\}$ and the buyer-initiated trades are
$\{(t,q_M,\infty,+1) : q_M > 0\}$. Where a venue lets participants submit genuine market
orders, we keep this convention: the executed fraction of an incoming order *is* the market
order, whatever the venue calls it.

## 7. Execution PnL

Let $V$ be the **signed** size we wish to execute ($V > 0$ buy, $V < 0$ sell), $K$ the cash
account, $H$ the inventory, $X = $ wealth.

Executing via a **market order** at time $t$ pays the half-spread:

$$\Delta K^{\text{market order}}_t = -P^m_t V \underbrace{-\frac{P^a_t - P^b_t}{2}\lvert V\rvert}_{\text{we pay the spread}} .$$

Executing via a **limit order** earns it, but the cash change is booked at execution time $t$
using the *stale* prices from the submission time, relabelled $t-1$:

$$\Delta K^{\text{limit order}}_t = -P^m_{t-1} V \underbrace{+ \frac{P^a_{t-1} - P^b_{t-1}}{2}\lvert V\rvert}_{\text{we earn the spread}} .$$

Adding the PnL on the position held and the mark-to-market of the position acquired:

$$\Delta X^{\text{market order}}_t
= \underbrace{H_{t-1}\,\Delta P^m_t}_{\text{held position}}
+ \underbrace{\Delta K^{\text{market order}}_t}_{}
+ \underbrace{P^m_t V}_{\text{mark-to-market}}
= H_{t-1}\,\Delta P^m_t - \frac{\phi_t}{2}\lvert V\rvert,$$

$$\Delta X^{\text{limit order}}_t
= H_{t-1}\,\Delta P^m_t + \Delta K^{\text{limit order}}_t + P^m_t V
= H_{t-1}\,\Delta P^m_t + V\,\Delta P^m_t + \frac{\phi_{t-1}}{2}\lvert V\rvert .$$

The extra term $V \Delta P^m_t$ is **adverse selection**: our limit order is hit precisely
when the mid has moved against us, by participants who are faster or better informed. We do
not control *when* we are filled. Choosing between market and limit orders is therefore the
question of whether the spread we earn compensates the adverse move we suffer while waiting.

## 8. Worked example

Tick $\tau = 0.01$. Book at $t-$:

| side | level $i$ | price | volume |
| --- | --- | --- | --- |
| ask | 2 | 10.03 | 180 |
| ask | 1 | **10.02** $= P^a_{t-}$ | 120 |
| bid | 1 | **10.00** $= P^b_{t-}$ | 100 |
| bid | 2 | 9.99 | 200 |
| bid | 3 | 9.98 | 150 |

so $\phi_{t-} = 0.02$, $P^m_{t-} = 10.01$, $I^1_{t-} = (100-120)/220 = -0.0909$.

**Case A — fully executed, no remainder.** Sell limit order $(t, 250, 9.99, -1)$.

Decomposition: $q_M = \min(250,\ 100 + 200) = 250$, remainder $q - q_M = 0$. It consumes 100
at 10.00 and 150 at 9.99.

Update rule: $\sum_1 = 100$, $\sum_2 = 300 > 250$ so $N_v = 2$; $P^{b,3}_{t-} = 9.98 < 9.99$
so $N_p = 3$; $N = 1$. Then $q^0 = 250$, $q^1 = 150$, $q^i = 0$ for $i \ge 2$, so
$q^\infty = 0$ and the ask side is untouched.

$$P^b_t = P^{b,2}_{t-} = 9.99, \quad
V^{b,1}_t = 200 - (150 - 0) = 50, \quad
V^{b,2}_t = 150 - 0 = 150, \quad
P^a_t = 10.02 .$$

Resulting state: bid $9.99 \times 50$, $9.98 \times 150$; ask $10.02 \times 120$,
$10.03 \times 180$. Hence $\phi_t = 0.03$, $P^m_t = 10.005$,
$I^1_t = (50-120)/170 = -0.4118$. Both routes agree.

**Case B — walks the book and leaves a remainder.** Same book, sell limit order
$(t, 400, 9.99, -1)$.

Decomposition: $q_M = \min(400,\ 300) = 300$, remainder $(t, 100, 9.99, -1)$ rests on the ask
side at 9.99 — inside the old spread.

Update rule: $N_v = 3$ (since $400 < 450$), $N_p = 3$, $N = 2$; $q^0 = 400$, $q^1 = 300$,
$q^i = 100$ for $i \ge 2$, so $q^\infty = 100 = q - q_M$.

$$P^b_t = P^{b,3}_{t-} = 9.98, \quad V^{b,1}_t = 150, \quad
P^a_t = 10.02 - \max(0,\ 10.02 - 9.99) = 9.99, \quad \delta P^a_t = -0.03 .$$

Ask indices shift by $-\delta P^a_t/\tau = 3$: $V^{a,1}_t = 100$ at 9.99 (the remainder,
using $V^{a,j}_{t-} = 0$ for $j \le 0$), $V^{a,2}_t = V^{a,3}_t = 0$ at 10.00 and 10.01, and
$V^{a,4}_t = 120$ at 10.02. Hence $\phi_t = 0.01$, $P^m_t = 9.985$,
$I^1_t = (150-100)/250 = +0.2$.

Case B exercises everything that usually breaks: walking the book, a residual resting inside
the spread, index shifting, and empty levels between the best price and the deeper ones. Use
it as the canonical test fixture.

## 9. Symbol table

Every symbol below is defined in `tex/include/notation.tex`, blocks
`%% LIMIT ORDER BOOKS %%` and `%% EXECUTION AND PnL %%`. The last column is the canonical
Python identifier — use it, and nothing else, in `unito26/` and in the notebooks.

| symbol | LaTeX macro | meaning | Python |
| --- | --- | --- | --- |
| $P$ | `\price` | generic price | `price` |
| $V$ | `\volume` | generic volume / signed order size in §7 | `volume` |
| $\tau$ | `\tickSizeOfLOB` | tick size of the book | `tick_size` |
| $P^m$ | `\midPrice` (alias `\midprice`) | mid-price | `mid_price` |
| $P^{\mu}$ | `\microPrice` | micro-price: the imbalance-weighted mid, $P^m + \tfrac{\phi}{2} I^1$ | `micro_price` |
| $P^b$ | `\bestBidPrice` | best bid price | `best_bid_price` |
| $P^a$ | `\bestAskPrice` | best ask price | `best_ask_price` |
| $P^{b,i}$ | `\nthBestBidPrice[i]` | price of the $i$-th bid level | `bid_price(i)` |
| $P^{a,i}$ | `\nthBestAskPrice[i]` | price of the $i$-th ask level | `ask_price(i)` |
| $V^b$ | `\bestBidVolume` | volume at the best bid | `best_bid_volume` |
| $V^a$ | `\bestAskVolume` | volume at the best ask | `best_ask_volume` |
| $V^{b,i}$ | `\nthBestBidVolume[i]` | volume at the $i$-th bid level | `bid_volume(i)` |
| $V^{a,i}$ | `\nthBestAskVolume[i]` | volume at the $i$-th ask level | `ask_volume(i)` |
| $V^b_t(p)$ | `\bidVolumePriceP` | bid volume at absolute price $p$ | `bid_volume_at(p)` |
| $V^a_t(p)$ | `\askVolumePriceP` | ask volume at absolute price $p$ | `ask_volume_at(p)` |
| $\phi$ | `\LOBspread` | spread | `spread` |
| $I$, $I^n$ | `\volumeImbalance` (alias `\queueImb`) | volume / queue imbalance | `queue_imbalance(n)` |
| $\mathrm{OFI}$ | `\OFI` (alias `\orderFlowImbalance`) | order flow imbalance | `order_flow_imbalance` |
| $A$ | `\askOrderQueue` | set of active sell orders | `ask_orders` |
| $B$ | `\bidOrderQueue` | set of active buy orders | `bid_orders` |
| $Q^b_t$, $Q^a_t$ | `\bidQueue`, `\askQueue` | bid / ask queue size process | `bid_queue`, `ask_queue` |
| $Q$ | `\queue` | generic queue size process | `queue` |
| $A$, $D$ | `\arrivals`, `\departures` | generic arrival / departure counting processes | `arrivals`, `departures` |
| $A^b_t$, $A^a_t$ | `\bidArrivals`, `\askArrivals` | arrivals to the bid / ask queue | `bid_arrivals`, `ask_arrivals` |
| $D^b_t$, $D^a_t$ | `\bidDepartures`, `\askDepartures` | departures from the bid / ask queue | `bid_departures`, `ask_departures` |
| $T^{b,A}_j$, $T^{a,A}_j$ | `\bidArrivalTimes`, `\askArrivalTimes` | arrival times | `bid_arrival_times`, `ask_arrival_times` |
| $T^{b,D}_j$, $T^{a,D}_j$ | `\bidDepartureTimes`, `\askDepartureTimes` | departure times | `bid_departure_times`, `ask_departure_times` |
| $Q$ | `\quantityToLiquidate` | quantity to liquidate | `quantity_to_liquidate` |
| $Q_0$ | `\metaorderSize` | metaorder size | `metaorder_size` |
| $\mathtt{imp}$ | `\impactProfile` | market impact profile (not characterised in the notes) | `impact_profile` |
| $q_M$ | `\marketOrderSize` | market-order component of a limit order | `market_order_size` |
| $K$ | `\cashAccount` | cash account | `cash` |
| $H$ | `\inventory` | inventory (signed position) | `inventory` |
| $X$ | `\wealth` | wealth / portfolio value | `wealth` |

Names carried by the implementation rather than by the notes, recorded here so they are
not reinvented: `occupied_levels(direction, reported_depth)` for the LOBSTER indexing,
`grid_span` for the number of grid positions a given set of reported levels covers,
`empty_grid_positions` and `gap_count` for the holes between them, `side_statistics` for
all of those read in one pass, `queue_imbalance_profile(imbalance_levels)` for $I^n$ at
several $n$ from one walk of each side, `column_sliced_imbalance` for the expression that
is *not* $I^n$, and the types `GridDepth` / `ReportedDepth` that keep the two counts from
being swapped. See
[`grid-levels-and-lobster-levels.md`](grid-levels-and-lobster-levels.md).

Three further gap statistics say *where* the holes are, not only how many:
`first_gap_distance` and `largest_gap_distance` for the distance in ticks from the touch to
the nearest and to the longest run of empty positions, and `first_gap_size` for the length
of the nearest one. **A distance is measured to the empty position**, so a gap opening at
grid position $i$ lies $i - 1$ ticks from the touch; the largest-gap tie-break is toward the
touch. Where a side has no gap there is no position to name, and zero would name the touch,
which always carries volume: a book answers `None`, a frame NaN. `first_gap_size` answers
zero, as `largest_gap` does, because a length of zero is a true answer.

The order tuple itself has no macros: $t$ is time, $q$ size, $p$ price, $d$ direction, and
$(s, \rho, \pi, -d)$ is the resting counterpart of $(t, q, p, d)$. In code, keep the tuple
order `(t, q, p, d)`.

**Collisions to watch.** The `.tex` reuses letters across blocks: $A$ is both the ask order
queue (`\askOrderQueue`) and the generic arrival process (`\arrivals`); $Q$ is both a queue
size (`\queue`) and the quantity to liquidate (`\quantityToLiquidate`); $V$ is both a level
volume and the signed order size in the PnL equations of §7. Context disambiguates them in
prose, but Python names must not — hence the distinct identifiers above.
