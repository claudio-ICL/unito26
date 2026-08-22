---
name: market-microstructure
description: The notation and mechanics of order-driven markets as this course defines them. Load before writing or reviewing any code that touches limit order books, order books, matching engines, order flow, bid/ask prices, tick sizes, price-time priority, queues and queue/volume imbalance, market orders, walking the book, execution PnL, market impact, or LOB/ITCH-style message data — in the unito26 package, in notebooks, or in exam snippets.
---

# Market microstructure and order books in `unito26`

The apparatus is developed in the notes,
`documentation/tex/notes/orderdriven/sections/order_driven_markets.tex`, and restated for
working use — with the mechanics and a worked example — in
**`documentation/order-driven-markets-notation.md`**. Read that file before designing types
or functions; the notes are the authority, this skill is the code-facing half.

Symbols are the notes' symbols. Never invent a parallel name for something the notes already
name, and never rename a concept on the way into Python.

## The naming map

An order is the 4-tuple `(t, q, p, d)`, **in that order**: time, size, price, direction.
`d` is `+1` (buy) or `-1` (sell) — an `int`, never a string, never a bool. The resting
counterpart in a match is $(s, \rho, \pi, -d)$.

| notes | Python |
| --- | --- |
| $\tau$ | `tick_size` |
| $P^a_t$, $P^b_t$ | `best_ask_price`, `best_bid_price` |
| $P^{a,i}_t$, $P^{b,i}_t$ | `ask_price(i)`, `bid_price(i)` |
| $V^{a,i}_t$, $V^{b,i}_t$ | `ask_volume(i)`, `bid_volume(i)` |
| $\phi_t$, $P^m_t$, $P^\mu_t$ | `spread`, `mid_price`, `micro_price` |
| $I^n_t$ | `queue_imbalance(n)` |
| $q_M$ | `market_order_size` |
| $A_t$, $B_t$ | `ask_orders`, `bid_orders` |
| $K$, $H$, $X$ | `cash`, `inventory`, `wealth` |

The full table, including the arrival/departure and impact families, is §9 of the reference.

Levels are **1-indexed** in the maths and relative to the best price *on their own side*. If
an implementation re-bases to 0, say so at the boundary and convert once — do not let both
conventions circulate.

## Invariants any implementation must respect

- **Prices are integer tick counts internally.** Convert to currency only at the boundary
  (input parsing, display, PnL). Floats on a tick grid produce prices that are not multiples
  of $\tau$ and levels that fail to compare equal.
- **The book never crosses.** Whenever both sides are non-empty, `best_bid_price <
  best_ask_price`. This follows from the matching rule, so a crossed book is a bug, not a
  market state — assert it.
- **Price-time priority.** Better price first ($d\pi < d\pi'$ handles both sides in one
  expression), and FIFO by timestamp within a level.
- **A fill trades at the resting order's price**, $\pi$, never at the incoming order's $p$.
- **Sizes are non-negative.** In the order-level representation a price whose queue empties
  is removed from the dict; the level *index* of §3 is unaffected and may still read zero
  (Case B of §8 has two such levels). By convention $V^{\cdot,j} = 0$ for $j \le 0$ — ours,
  not the notes', but required to make the shifted index in §5 well defined.
- **An exhausted side is a separate branch.** The update rule of §5 assumes the incoming
  order does not consume the whole price-eligible side; when it does, $N_v$ (and, for a market
  order, $N_p$) is $+\infty$ and the best price on that side is undefined. Never compute
  $N_v$ with a loop that assumes it terminates.
- **One code path, not two.** Every incoming limit order is processed as
  market-part-then-rest: consume the opposite side up to $q_M$, then rest $q - q_M$. There is
  no separate "marketable order" branch. This is Prop. `prop.decompositionOfLimitOrder` and
  it is the single most useful structural fact for the engine.
- **Imbalance is bid minus ask over the total**, so bid-heavy is positive and
  $I^n \in [-1,1]$. Inverting this sign silently inverts every signal built on it.
- **PnL signs.** A market order pays $\phi_t/2 \cdot |V|$; a limit order earns
  $\phi_{t-1}/2 \cdot |V|$ but carries the adverse-selection term $V \Delta P^m_t$, because
  the cash change is booked at the submission-time prices $P^m_{t-1}, \phi_{t-1}$. See §7 of
  the reference.

## How we write it here

Per `CLAUDE.md`: the **clear, idiomatic version first**, understood on its own terms;
cleverness and optimisation come after, explained and reconciled against it. A vectorised or
array-backed book is a second implementation shown to beat a first, never the first thing a
student meets.

Reusable, tested code goes in `unito26/` (and into `unito26/__init__.py` as it is actually
built); lectures and exercises go in `notebooks/`; tests in `tests/`, run with
`python -m pytest tests/`.

Data-structure choices, an engine skeleton, and the test conventions — including the
canonical fixture — are in `references/implementation-notes.md`.
