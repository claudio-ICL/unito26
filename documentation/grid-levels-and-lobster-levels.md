# Two ways to count a level

A level index means one thing in the notes and a different thing in a LOBSTER file.
The two agree on a book with no holes, which is most of the time on a large-tick
instrument and almost never on a small-tick one.
Where they disagree, code that confuses them does not fail — it computes a different
quantity and reports it under the same name.

This file is the reference for that difference, and for the machinery in
`unito26.lob.orderbook` and `unito26.lob.replay` that exists to handle it.

---

## 1. $I^n$ is a grid quantity

Section 4 of [`order-driven-markets-notation.md`](order-driven-markets-notation.md)
defines the $n$-level volume imbalance as

$$I^n_t = \frac{\sum_{i \le n} V^{b,i}_t - \sum_{i \le n} V^{a,i}_t}
               {\sum_{i \le n} V^{b,i}_t + \sum_{i \le n} V^{a,i}_t},$$

and section 3 defines $V^{b,i}_t$ as the volume resting at the **grid price**
$P^{b,i}_t = P^b_t - (i-1)\tau$ — a position on the price ladder, occupied or not, with
$V^{b,i}_t = 0$ where nothing rests.

So $n$ counts **grid positions**, spanning $n-1$ ticks from each touch.
It is not a count of queues.
The `.tex` in `documentation/tex/notes/orderdriven/` is the authority; `queue_imbalance(n)`
follows it, and its argument is typed `GridDepth` for that reason.

**This is not the literature's convention.** Feed-derived empirical work almost always
counts the first $n$ *queues*, because that is what a file hands you. A student
reproducing a paper's number on the same data needs to know which is which. We keep the
grid definition: a price distance is comparable across instruments and stays meaningful
as the book thins, where "the fifth occupied level" may be one tick away or fifty.

## 2. A LOBSTER file counts occupied levels

From `data/lobster/LOBSTER_SampleFiles_ReadMe.txt`:

> The term level refers to occupied price levels. This implies that the difference between
> two levels in the LOBSTER output is not necessarily the minimum ticks size.

So `BidPrice2` is the second price *carrying volume*, however far below the touch it sits.
Column $k$ and grid level $k$ are the same price only while the book has no holes.

Two conventions in `unito26.lob.orderbook`, deliberately named apart:

| | means | method | type |
| --- | --- | --- | --- |
| grid | position on the ladder, §3 | `levels(direction, depth)` | `GridDepth` |
| reported | price carrying volume, LOBSTER | `occupied_levels(direction, reported_depth)` | `ReportedDepth` |

## 3. Gaps are the whole difficulty

An empty queue inside the window shifts every column past it. Nothing errors: summing
`BidSize1..BidSizeN` produces a well-formed number in $[-1,1]$ that moves plausibly with
the market and is a different statistic.

Gaps are ordinary rather than pathological. Case B of the notes' own worked example leaves
two of them, and `AggregateBook.empty_grid_positions` exists to find them.

## 4. Select by price, never by column

The grid window on the bid side is $[P^b - (n-1)\tau,\; P^b]$, so

$$\text{bid total}(n) = \sum_k \mathtt{BidSize}_k \cdot
  \mathbf{1}\{\mathtt{BidPrice}_k \ge \mathtt{BidPrice}_1 - (n-1)\tau\},$$

and the ask mirror uses $\mathtt{AskPrice}_k \le \mathtt{AskPrice}_1 + (n-1)\tau$.
This is what `MarketSession.stats_from_frame` does. A column slice is the confusion this
file exists to prevent; `MarketSession.column_sliced_imbalance` is that expression, kept
under a name that says what it computes so that the two can be drawn on one pair of axes
rather than mistaken for each other.

Two further traps in the same computation. `sum` skips NaN by default, so a missing level
is silently treated as absent rather than unknown; the sums are masked explicitly instead.
And bid prices *descend* with level, so a single gap formula for both sides makes every
bid gap negative — the bid takes $-\mathrm{diff}$.

<!-- begin generated: indexing example -->

Tick $\tau = 1$.  Asks occupied at 101, 102, 103, 104, 105; bids at 99 and 90 and nowhere between.

A file of reported depth 2 holds:

| AskPrice1 | AskSize1 | BidPrice1 | BidSize1 | AskPrice2 | AskSize2 | BidPrice2 | BidSize2 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 101 | 10 | 99 | 40 | 102 | 20 | 90 | 60 |

| side | reported levels | grid span |
| --- | --- | --- |
| ask | 101, 102 | 2 |
| bid | 99, 90 | 10 |

The bid side spans 10 grid positions on 2 reported levels; the ask side spans 2.  So:

| quantity | value |
| --- | --- |
| $I^2$, selecting by price | +0.142857 |
| $I^2$, slicing by column | +0.538462 |
| $I^2$ recoverable from the file | True |
| $I^3$ recoverable from the file | False |

The column-sliced answer pairs the touch at 99 with a level 9 ticks away and reports it as a top-of-book signal.  And $I^3$ fails on the **ask** side, which ran out at 102, while the bid had 10 positions of room to spare.

<!-- end generated: indexing example -->

## 5. The repair has a limit

Write the **grid span** of a side as $\lvert P_1 - P_L\rvert/\tau + 1$, where
$L = \min(D, \text{occupied levels})$ — using $D$ directly is undefined on a padded side.
`AggregateBook.grid_span` computes it.

$I^n$ is recoverable from a frame when, **for each side independently**, either
$n \le \text{grid span}$ or that side is fully reported; coverage is the conjunction over
the two sides. One short side does not excuse the other.

The condition is **sufficient, not necessary**. Bids occupied at 100, 99 and 95 with
$D = 2$ give a span of 2, so the rule calls $I^3$ uncovered — yet the masked sum is right,
because the unreported level at 95 falls *below* the window. It first genuinely fails at
$n = 6$. It is nonetheless the tightest rule **decidable from a frame**: at
$n = \text{span} + 1$ the frame is equally consistent with a level just below the window
and with a gap there, so no frame-only rule can do better.

Reported depth is a *purchase option* — LOBSTER sells 1, 5, 10, 30 or 50 levels and puts
it in the filename. What the market decides is how much **grid** depth a given reported
depth buys, and that moves row by row as the book breathes.

## 6. On a real file, even "fully reported" is weaker than it looks

A padded side in a file does not mean "the book ends here". It means "no further levels in
the visible price range" — and, as `unito26/lob/lobster.py` records, even the last visible
level degrades over the session as the range is exhausted.

So the second branch of §5 is exact for a frame we generated and only an upper bound for
one we loaded. `MarketSession.from_file` carries that provenance and drops the branch.
The honest account has three states, not two:

- **covered** — the window is inside the reported span;
- **not covered** — it is not, and the frame cannot answer;
- **covered only within the visible range** — the frame answers, for the liquidity the
  file can see.

The third cannot be detected from the data, which is why it is named here rather than
modelled in a column.

And for the same reason, neither route computes "the true $I^n$" on real data: hidden
liquidity (LOBSTER type 5) means both give the *visible* imbalance. A reconstructed book
is not ground truth.

## 7. The padding sentinels

> The extra bid and/or ask prices are set to -9999999999 and 9999999999, respectively.
> The Corresponding volumes are set to 0.

They have **opposite signs**, so a filter written for one lets the other through. The price
mask of §4 rejects both automatically, which is why the imbalance survives padded rows —
but nothing else does. `AskPrice1 - BidPrice1` on a row padded at level 1 gives
$\approx 2\times10^{10}$, and a largest-gap gives $\approx 10^8$ ticks.
`unito26.lob.frames` names them `ASK_PADDING` and `BID_PADDING`; `describe_orderbook`
drops unquoted rows before it measures anything.

Note also that a LOBSTER orderbook file carries **no timestamp column** — it is
$N \times (4 \times \text{levels})$, its rows aligned with the message file. So
`MarketSession.lobster_book` carries exactly $4D$ columns and keeps time on the index.
