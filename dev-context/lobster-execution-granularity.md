# Execution granularity: our fold and a LOBSTER file disagree on what a row is

**Status: open.** The facts are settled and written up in
[`documentation/from-lobster-files-to-a-session.md`](../documentation/from-lobster-files-to-a-session.md)
§5, which carries the mechanism and the measurements. This file records only what we have to
decide, and why we have not decided it.

## The discrepancy

Our fold applies one message to the book and writes one row. LOBSTER records the execution of
each *resting order* separately, so one incoming order that consumes $k$ resting orders
becomes $k$ message rows and $k$ orderbook rows at one timestamp, with the intermediate book
states visible between them.

On the sample this affects a fifth to a half of trades depending on the ticker, and 43% of
AMZN's executions and 86% of INTC's sit inside a multi-row trade. Four fifths of those are
*queue splits* — several resting orders at one price — which is the part an aggregate book
cannot reproduce, because the aggregate state does not know a level of 100 is five orders of
20. This is the aggregation-versus-identity break of the ladder, arriving as a property of
the data rather than as a design decision.

## Why it matters here

Volume, traded value, VWAP and windowed OFI are all invariant to the splitting. Per-row
averages are not, and `AverageDepth{w}` is one: it divides by the number of rows in the
window, and a LOBSTER session has more rows per unit of trading than a simulated one.

The sharper consequence is that a session we fold and a session we load are **not row-wise
comparable**, although their frames have the same columns, the same dtypes and the same index
name. The unit of observation differs and no schema can say so. Any reconciliation between
the simulator and the data has to be stated at the level of a window or a trade, never a row.

## Two ways out, neither taken

**Coarsen LOBSTER.** Group maximal runs of type-4 rows sharing a timestamp and a direction
into one trade. Cheap, and it recovers our granularity exactly for the quantities listed
above. It discards the queue information, which is the thing the data has and the simulator
does not, so it is a loss taken deliberately.

**Refine ours.** An order-level book emitting one event per resting order consumed matches
LOBSTER row for row. That is L4-L5 of the ladder, and this is one more argument for building
it: the file is written in the granularity the identity-carrying book produces naturally.

The first is a preprocessing step and could land with the loaders; the second is a batch of
its own. They are not exclusive — the grouping is worth having regardless, as the only way to
ask the data for a trade size.

**The grouping heuristic has a known hole.** Two genuinely distinct market orders arriving in
the same nanosecond, on the same side, merge into one trade. The file carries no aggressor
id, so nothing distinguishes them. Rare, unquantified, and it should be measured rather than
assumed away.

**And the key must be the integer.** Grouping on the parsed float works on these files only
because the clock is seconds after midnight; §4 of the reference has the numbers. Any
grouping code keys on `TimeNanoseconds`.

## Checks to write once the loaders exist

- the distribution of §5, recomputed through a loaded session and keyed on
  `TimeNanoseconds`, rather than by `awk` over the raw file;
- grouping executions into trades leaves `Volume` and `TradedValue` unchanged, and windowed
  OFI unchanged;
- it does *not* leave `AverageDepth{w}` unchanged — asserting the difference, so the
  sensitivity is recorded rather than discovered later;
- the integer key and the float key induce the same groups on all eight sample files. This is
  the check that fails first on a feed whose clock has a different origin, which is the point
  of writing it;
- how often two distinct trades share a timestamp and a side, to put a number on the hole
  above.
