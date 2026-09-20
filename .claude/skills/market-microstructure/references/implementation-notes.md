# Implementation notes for order-book code

Companion to `documentation/order-driven-markets-notation.md`. That file fixes *what* the
objects are; this one records how we represent them in Python, and what to test.

## Representing the book

Three representations, each right for a different job. Say which one a piece of code is
using, and do not mix them silently.

**1. Order-level book (the faithful one).** Mirrors §3 of the reference: a mapping from price
(in ticks) to a FIFO queue of resting orders.

```python
from collections import deque

bid_levels: dict[int, deque[Order]]   # price in ticks -> orders, oldest first
ask_levels: dict[int, deque[Order]]
```

`deque` gives O(1) `popleft` on the fill side and `append` on the post side, which is exactly
price-time priority. Best prices are `max(bid_levels)` / `min(ask_levels)` — O(number of
occupied levels), fine for teaching, and the honest first version. If it ever becomes the
bottleneck, the replacement is a heap or a sorted container, introduced *after* the dict
version is understood.

This is the only representation that can answer "where am I in the queue?", so it is the one
for queue-position and adverse-selection work.

**2. Level-aggregated snapshot.** Just the state of §3:
`(best_ask_price, best_bid_price, ask_sizes, bid_sizes)`, sizes as fixed-length arrays
over the first $n$ levels. This is what the update rule of §5 acts on, what most public data
feeds give you, and what feeds signals ($\phi$, $P^m$, $I^n$). Cheap, but it forgets who is
in front of whom.

**3. Event stream.** The trading epoch itself: a table of `(t, q, p, d)` submissions,
cancellations and executions, from which either of the other two is reconstructed by replay.
Store as a DataFrame or an arrow table; `pyarrow` is already in the stack.

numpy/pandas earn their place on (2) and (3) — many snapshots, columnar signals, replay over
a session. They do *not* earn it inside (1), where per-order mutation in a numpy array is
slower and far less readable than plain Python objects.

## Engine skeleton

Driven by the decomposition (Prop. `prop.decompositionOfLimitOrder`), so there is one path:

```
submit(t, q, p, d):
    # 1. market-order part: consume the opposite side while it matches
    while q > 0 and opposite side non-empty and pi*d <= p*d for the best opposite price:
        fill min(q, resting.q) at the RESTING price pi
        decrement both; drop the resting order when it hits zero
        drop the level when its queue empties
    # 2. resting part: whatever is left joins the back of its own level's queue.
    #    A genuine market order (p = 0 / inf) never rests -- reject or discard its remainder.
    if q > 0 and p not in (0, inf):
        levels_on_side_d[p].append(Order(t, q, p, d))
```

The guard in step 2 matters: §6 models a genuine market order with the sentinel price
$p = 0$ (sell) or $p = \infty$ (buy), so without it an oversized market order rests a sell
order **at price 0**, which then matches every subsequent buy — silent corruption of the book
from that point on.

`market_order_size` is the total filled in step 1; it is the quantity that defines a *trade*.
Return the fills — `(price, size)` pairs plus the aggressor's direction — rather than
printing or discarding them: trades, PnL and impact are all built from that list.

Cancellation removes an order from its level's queue and removes the level if it empties —
which can move the best price on that side. It changes nothing else.

## Testing

`tests/` mirrors the package layout; run `python -m pytest tests/`.

**Canonical fixture.** §8 of the reference, Case B: $\tau = 0.01$; bid $10.00 \times 100$,
$9.99 \times 200$, $9.98 \times 150$; ask $10.02 \times 120$, $10.03 \times 180$; incoming
sell $(t, 400, 9.99, -1)$. Expected: $q_M = 300$ filled as $100$ at $10.00$ and $200$ at
$9.99$; the remaining $100$ rests at $9.99$ on the ask side; afterwards $P^b_t = 9.98$,
$P^a_t = 9.99$, $\phi_t = 0.01$, $P^m_t = 9.985$, $I^1_t = +0.2$. It exercises walking the
book, a residual resting inside the old spread, index shifting and empty levels in one go.
Case A (the same book, sell $(t, 250, 9.99, -1)$) is the no-remainder counterpart.

**Property tests** worth having from the start:

- the book never crosses after any sequence of submissions and cancellations;
- shares are conserved: total volume filled equals the drop in resting size on the consumed side,
  and every fill price is a resting price that satisfied $\pi d \le p d$;
- `queue_imbalance(n)` lies in $[-1, 1]$ and is $+1$ / $-1$ exactly when one side is empty
  (with both sides empty it is $0/0$ — assert the precondition rather than the bound);
- the level-aggregated view derived from the order-level book agrees, level by level, with
  the update rule of §5 applied to the previous snapshot — the two routes of §8 agreeing is
  the general statement of this test;
- prices coming out are integer multiples of `tick_size`.

**Sanity on real data**, when a LOB dataset is in play: spreads are positive, and for a
large-tick instrument mostly one or two ticks; timestamps are non-decreasing; reconstructed best prices match the feed's own
best prices on every message.
