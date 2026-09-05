# From LOBSTER files to a market session

LOBSTER ships two files per ticker per trading day.
This file describes what is in them,
what the format permits that the data happens never to show,
and how the two become a `MarketSession`.

Companion to [`order-driven-markets-notation.md`](order-driven-markets-notation.md),
which fixes what the objects are,
and to [`grid-levels-and-lobster-levels.md`](grid-levels-and-lobster-levels.md),
which fixes how a level is counted.
It is written to be lifted into the LaTeX lecture notes,
so it is self-contained:
the sample files and LOBSTER's own ReadMe live under `data/`, which is not in the repository.

**Measurements.** Numbers below were taken on 2026-09-05 from the eight sample pairs of
2012-06-21 — AAPL, AMZN, GOOG, INTC, MSFT, SPY — 3,499,101 book states in all. They describe
one day of one sample and are quoted to make a point concrete, never as a property of the
format. Where the two differ, that difference is the point.

---

## 1. The two files

For each ticker and day, LOBSTER writes a **message** file and an **orderbook** file:

```
TICKER_YYYY-MM-DD_StartTime_EndTime_message_LEVEL.csv
TICKER_YYYY-MM-DD_StartTime_EndTime_orderbook_LEVEL.csv
```

`StartTime` and `EndTime` are the requested window in **milliseconds** after midnight;
`LEVEL` is the number of levels the book is reported to.
Neither file has a header.

The two are **aligned by position and by nothing else**.
Row $i$ of the orderbook file is the state of the book *after* the event on row $i$ of the
message file. The orderbook file carries no timestamp, no sequence number and no key:
the alignment is a property of how the files were written, and it cannot be checked from
their contents. That is the single most consequential fact about the format.

### The message file: six columns

| # | column | meaning |
| --- | --- | --- |
| 1 | `Time` | seconds after midnight, decimal, at least milliseconds and up to nanoseconds |
| 2 | `Type` | the event, below |
| 3 | `OrderID` | reference number assigned in the order flow |
| 4 | `Size` | shares |
| 5 | `Price` | dollars $\times$ 10000, so \$91.14 is `911400` |
| 6 | `Direction` | `-1` a sell limit order, `+1` a buy limit order |

| `Type` | event |
| --- | --- |
| 1 | submission of a new limit order |
| 2 | cancellation, partial |
| 3 | deletion, total |
| 4 | execution of a visible limit order |
| 5 | execution of a **hidden** limit order |
| 7 | trading halt indicator |

There is no type 6 in LOBSTER's sample ReadMe. `unito26.lob.lobster.LobsterEvent` defines
`CROSS_TRADE = 6`; that value is not sourced here and should be confirmed against LOBSTER's
full documentation before anything is asserted about it. None of the eight sample files
contains a type 6 or a type 7.

**There is no "aggressive order" event.** A trade appears as the execution of the *resting*
order it hit, so `Direction` on a type 4 or 5 names the **passive** side, and the
aggressor's direction is $-d$. The ReadMe says it directly: execution of a sell limit order
is a buyer-initiated trade. Trade signing, which is a literature elsewhere, is exact and
free here — and inverted by anyone who reads the column as the trade's direction.

### The orderbook file: $4 \times \text{LEVEL}$ columns

Ask price, ask size, bid price, bid size, repeated outward from the touch:

```
AskPrice1, AskSize1, BidPrice1, BidSize1, AskPrice2, AskSize2, BidPrice2, BidSize2, ...
```

Where a side holds fewer than `LEVEL` occupied prices, the remaining slots are **padded**:
price `+9999999999` on the ask, price `-9999999999` on the bid, size `0` in both cases.

The two sentinels have **opposite signs**. A filter written for one lets the other through,
and one padded row moves a mean spread by $10^8$ ticks. The plausible repair
`book[book.BidPrice1 > 0]` cleans the bid correctly and the ask not at all.

### Trading halts

A halt writes a type-7 message with `Size` and `OrderID` zero, `Direction` `-1`, and the
`Price` column carrying a **status code** rather than a price:

```
Halt:             36023 | 7 | 0 | 0 | -1 | -1
Quoting resumed:  36323 | 7 | 0 | 0 |  0 | -1
Trading resumed:  36723 | 7 | 0 | 0 |  1 | -1
```

The orderbook rows facing a type 7 duplicate the preceding state.
So on these rows `Price` is not a price, `Direction` names no side, and `Size` is not a
quantity. A schema cannot express "this column means something else on these rows"; the only
honest response is to keep the raw message schema loose and to tighten it on the subset that
is actually orders. Two schemas, two pipelines.

---

## 2. Levels are occupied levels

`LEVEL` counts **occupied** prices, not positions on the tick grid: level $k$ is the $k$-th
price carrying size, however far from the touch it sits. The notes' $I^n$ counts grid
positions instead. The two coincide only on a book with no holes, and the difference is
invisible in the output — both stay in $[-1,1]$, both move with the market.

[`grid-levels-and-lobster-levels.md`](grid-levels-and-lobster-levels.md) is the reference for
this, for the coverage condition it forces, and for why a padded side in a *file* is weaker
information than an empty side in a book we hold. It is not restated here.

---

## 3. What the format permits, and what one day of data happens to show

The four constraints below are the ones a reader writes first. Each is wrong, and they fail
in two different ways, which is the distinction worth keeping.

| constraint | on the sample | why it is wrong |
| --- | --- | --- |
| `OrderID > 0` | **rejects real rows immediately** | hidden executions carry no order id — 2,445 rows on AMZN, exactly its type-5 count — and so does every halt row |
| `Price >= 0` | **passes all eight files** | no sample contains a halt. On a halt sequence it rejects the first message and accepts the other two |
| `Price % 100 == 0` | **passes every type 4, rejects some type 5** | hidden prints are sub-penny: 63 rows on AMZN, 50 on GOOG, 372 on AAPL, 2,140 on INTC, all type 5 |
| `spread > 0` | **passes all 3,499,101 rows** | the sample never crosses or locks; nothing in the format promises that |

The first fails on day one and teaches only that the specification is worth reading. The
other three are the interesting ones: they pass every test written against this data, and
they encode an assumption the data merely happens to satisfy. A schema derived from a
sample inherits the sample's blind spots, and a test suite built from the same sample cannot
see them.

The rule that follows is the one to carry: **write the schema against the format, not
against the data you have**. Where the format is loose, say so and record why, because a
missing constraint is invisible to a reader who meets the schema cold and reasonable to
tighten.

### Padding is real, and it is asymmetric

At depth 10 none of the samples pads at all. At depth 50 all three do:

| file | shallowest padded level | rows padded at level 50 |
| --- | --- | --- |
| AAPL | ask 41 | 108 |
| MSFT | ask 33, bid 41 | 871 ask, 367 bid |
| SPY | bid 50 | 44 bid |

AAPL's 108 padded rows all fall between $t = 34200.004$ and $t = 34200.641$ — the first
two-thirds of a second of the session, before the book has filled to fifty levels. Padding
here is an opening artefact, so a window that does not start at 09:30 contains none, and an
assertion about padding written over such a window is vacuous rather than passing.

SPY is the file whose *bid* side truncates. It is worth keeping in view precisely because
the ask is the side one tests first.

---

## 4. The clock

Timestamps are decimal seconds after midnight. The ReadMe promises at least milliseconds and
up to nanoseconds; AMZN's file carries nine decimals on 242,707 of its 269,748 rows, eight on
24,328, and **twelve on two** — `36754.716797047004` and `43002.632812672004`, finer than the
documentation admits.

### Ties are ordinary

Times are non-decreasing and never decrease. They are also **not unique**: AMZN has 8,483
tied steps, 3.1% of the file, and one timestamp repeated 31 times. Section 5 says where the
ties come from.

Two consequences. A rolling window must decide what a tie means, and the choice here is
causal: the window $(t-w,\,t]$ is closed on the right at the current row, so two rows sharing
a timestamp get different windows and row $i$ does not see row $i+1$. And an index schema
must **not** declare the timestamp unique. That is the constraint a reader adds next, and it
rejects 3.1% of the file.

### Nothing may group on the float

Equality on a float is exact-bit equality, and it works here:

| | |
| --- | --- |
| float64 spacing at seconds after midnight | $7.276 \times 10^{-12}$ s, about 137 ticks per nanosecond |
| distinct timestamps as text | 261,265 |
| distinct after parsing to float64 | 261,265 |
| adjacent rows distinct in text but equal as float64 | 0 |

It works *because the clock is seconds after midnight*, which keeps the exponent small.
The same nanosecond resolution measured from the Unix epoch, $1.34 \times 10^9$ s, has a
float64 spacing of 238 nanoseconds, and every group of the next section collapses into its
neighbours. The safety is a property of the encoding, not of the format, and the file already
carries digits finer than float64 can separate at a larger origin.

So the *key* is an exact integer, built from the text by splitting on the decimal point and
never by scaling the parsed float: `int64` nanoseconds, which reproduces the same 261,265
distinct values and the same run boundaries, over a range $3.42 \times 10^{13}$ to
$5.76 \times 10^{13}$ against an `int64` ceiling of $9.22 \times 10^{18}$. The two
twelve-decimal rows lose their picoseconds.

The float and the integer are two fields with two jobs — the float is the coordinate the
window arithmetic runs on, the integer is the only thing anything may group or join on — and
both are declared before the file is read.

---

## 5. One order, several rows

LOBSTER records the **executions of resting orders**, not trades. An incoming order that
consumes $k$ resting orders produces $k$ message rows and $k$ orderbook rows, all sharing one
timestamp. This is stated in LOBSTER's own demo: 1,000 shares meeting one resting order of
1,000 print one execution; meeting five of 200 they print five.

Take the book of the worked example, best bid 100 at 1000, and suppose — as the aggregate
book cannot — that the 100 is five resting orders of 20 from five participants. A sell of 55
at 1000 arrives. Folding it into an aggregate book gives one state change, the bid size
falling 100 to 45. LOBSTER gives three rows: 20 against the earliest order, 20 against the
second, 15 against the third, with the intermediate states 80 and 60 visible in the orderbook
file. Those two intermediate configurations exist *inside* the matching of a single incoming
order.

It is common:

| ticker (depth 10) | type-4 rows | trades | multi-row trades | rows inside them | largest |
| --- | --- | --- | --- | --- | --- |
| AMZN | 8,974 | 6,591 | 1,511 (22.9%) | 3,894 (43.4%) | 28 |
| GOOG | 7,765 | 5,931 | 1,190 (20.1%) | 3,024 (38.9%) | 35 |
| AAPL | 23,658 | 18,016 | 3,883 (21.6%) | 9,525 (40.3%) | 43 |
| INTC | 28,924 | 8,006 | 3,888 (48.6%) | 24,806 (85.8%) | 105 |

grouping maximal runs of type-4 rows that share a timestamp and a direction. On INTC, 85.8%
of all executions sit inside a multi-row trade.

**Two causes, and only one of them needs identity.** A multi-row trade is either a *level
walk* — the aggressor consumes several prices, which an aggregate book could report one level
at a time if it chose — or a *queue split*, several resting orders at one price, which no
sequence of aggregate states determines, because the aggregate book does not know the level
is five orders. Splitting the same groups by whether all their prices agree: **80% AMZN, 79%
GOOG, 82% AAPL, 99% INTC** are queue splits. One AMZN buy at \$225.00 consumes 25 resting
orders — 500, 100, 30, 200, 1, ... — as 25 rows.

So the granularity gap is overwhelmingly the part an aggregate book cannot reach in
principle. It is the aggregation-versus-identity break of the strand, arriving as a property
of a file rather than as a design choice.

**Within a split the timestamp is exactly equal.** Consecutive type-4 rows sharing a price
and a direction give 1,988 pairs at a gap of exactly zero and 2,694 at a non-zero gap whose
minimum is 1.5 microseconds — six orders of magnitude above the float64 resolution of section
4. There is no ambiguous middle, so grouping on equality neither merges distinct trades nor
splits one.

### What it changes, quantity by quantity

- **volume, traded value, VWAP** — nothing. 20 + 20 + 15 at one price is 55 at that price;
- **order flow imbalance over a window** — nothing. $e_n$ differences consecutive touches,
  and three consecutive decrements sum to the single decrement;
- **any per-row average** — everything. A mean over rows weights a five-way split five times,
  and LOBSTER has more rows per unit of trading than a fold does;
- **mean trade size** — everything, and this is the trap LOBSTER's demo names outright. Mean
  *execution* size is not mean *trade* size, and nothing in the file marks the difference;
- **comparing a simulated session against a loaded one row by row** — impossible. The two
  frames have the same columns, the same dtypes and the same index name, and a different unit
  of observation. A schema pins the fields and cannot pin what a row *is*.

That last one is the limit of the discipline the rest of this file argues for, and it is
worth stating plainly: schemas are necessary and they are not sufficient.

How the discrepancy should be reconciled is an open question, recorded in
[`../dev-context/lobster-execution-granularity.md`](../dev-context/lobster-execution-granularity.md).
