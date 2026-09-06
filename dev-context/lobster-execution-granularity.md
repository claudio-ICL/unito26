# Execution granularity: our fold and a LOBSTER file disagree on what a row is

**Status: resolved.** We coarsen. The mechanism and the measurements are in
[`documentation/from-lobster-files-to-a-session.md`](../documentation/from-lobster-files-to-a-session.md)
§5, and the code is `unito26/lob/lobster_session.py`. This file records what was decided, what
it costs, and what was deliberately given up.

## The discrepancy

Our fold applies one message to the book and writes one row. LOBSTER records the execution of
each *resting order* separately, so one incoming order that consumes $k$ resting orders becomes
$k$ message rows and $k$ orderbook rows at one timestamp, with the intermediate book states
visible between them.

On the sample this affects a fifth to a half of market orders depending on the ticker, and 43%
of AMZN's executions and 86% of INTC's sit inside a multi-fill order. Four fifths of those are
*queue splits* — several resting orders at one price — which is the part an aggregate book
cannot reproduce, because the aggregate state does not know a level of 100 is five orders of
20. This is the aggregation-versus-identity break of the ladder, arriving as a property of the
data rather than as a design decision.

## What was decided

**Two types, one transformation.** `MarketSession` means one row per aggressive order and one
per every other message. A raw pair is a `LobsterMarketSession`, holding both frames
positionally indexed exactly as the files have them, and `coarsened` is the only way across.
The two indices make the confusion a validation error rather than a wrong answer; before this,
the file schema declared no index and accepted a clocked session frame in silence.

**A market order is a maximal contiguous block of visible executions sharing an instant and a
direction, together with any hidden executions strictly between two of them.** Three
alternatives were measured and rejected:

- *a `groupby` on the instant and direction* joins two orders that merely arrived together. It
  agrees with the rule above on AMZN, GOOG and AAPL and disagrees on INTC;
- *contiguous visible fills alone* splits the 19 AMZN sweeps that took hidden liquidity in the
  middle;
- *contiguous type-4 and type-5 together* merges 584 AMZN blocks of which only 19 are genuine
  interruptions, and — because a hidden print carries a price while moving no level — turns
  queue splits into apparent level walks: 430 of the resulting 727 "walks" preserve an order
  flow contribution that a real walk never preserves.

**The block keeps its last row** — the state after the whole order finished matching — and its
fills are summed onto it. A block of hidden prints alone is dropped, every such row repeating
the state before it, except at row 0 where there is nothing to repeat: AMZN's first message is a
hidden execution, so the opening row is kept unconditionally.

## What it costs

Measured by `coarsening_report`, which states what the theory promises beside what happened.

Preserved exactly: every statistic that is a function of one configuration, since the surviving
row *is* one of the file's rows; volume, traded value and VWAP, the fills being additive; and
the order flow contribution on every queue split. Not preserved: the same contribution on every
level walk (297 of AMZN's 1,511 multi-fill orders), any window reduction that contains one, and
every per-row average, `AverageDepth{w}` among them.

Given up deliberately: **the queue information.** The file knows a level of 100 was five orders
of 20 and the coarse session does not. Recovering it means refining our own book instead —
L4/L5 of the ladder, one event per resting order consumed — which is a batch of its own and
would match the file row for row.

## What is still not known

**The grouping's hole is unquantified.** Two genuinely distinct market orders arriving in the
same nanosecond on the same side merge into one, and the file carries no aggressor id to
separate them. `price_reversing_orders` finds none on any sample file, and that is weak
evidence: two orders each sweeping monotonically away from the mid are invisible to it. Only a
feed carrying an aggressor id, or a venue's own trade report, would settle it.
