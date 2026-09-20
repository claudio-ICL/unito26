# Level 3 (Market-by-Order) vs. Level 2 (Market-by-Price): why MBO is faster, and why HFT firms reconstruct the book from it

## Two data streams, two different jobs

Exchanges like CME and Nasdaq generally sell (at least) two flavors of real-time data:

- **Market-by-Order (MBO) / "Level 3"** — a message for every individual order event: new order, modify, cancel, execute, replace, each tagged with a unique order ID and its priority/rank in the queue. Nasdaq's TotalView-ITCH protocol sends a distinct message type for each order-book event (add, execute, cancel, replace); the exchange sends only the event that changed the book, not the book's state, leaving each participant to maintain and update their own copy. CME's MBO feed (now "MBOFD" — Market By Order Full Depth) works the same way: it disseminates individual orders and quotes at every price level, while preserving anonymity of the participant behind each order.

- **Market-by-Price (MBP) / "Level 2" / the published order book** — the exchange itself does the aggregation: it buckets resting quantity by price level and periodically (or incrementally) tells you "at price X there are now Y contracts total," without individual order identity. This is what most people mean by "the order book" or "depth of book" feed.

Both are usually derived from the same underlying matching-engine event stream — the exchange isn't running two independent processes, it's publishing two different **views** of one truth.

## Why MBO/L3 is faster

This isn't really about the wire being faster — it's about **where the aggregation work happens** and what that does to latency and information content.

**1. Fewer processing stages between the matching engine and the wire.**
An MBO message is close to a direct, ledger-style record of what the matching engine just did to a specific order — insert, delete, modify. An MBP/aggregated update, by contrast, requires the exchange's own book-building logic to first net the individual order event against the existing price-level total, decide whether the level's displayed quantity changed, and then emit a level-based delta (or periodic snapshot). That aggregation step is extra compute sitting in the publication path — it doesn't exist for MBO, which is one reason CME's own literature markets the incremental MBO feed as the low-latency product and treats MBP as the "high level" derived view: the handler's design separates a high-level Market-By-Price API from a low-level API that carries both Market-by-Order and Market-By-Price information, with the MBO path built to shave the feed down to microsecond delivery.

**2. MBO changes are emitted the instant an order-level event happens; MBP changes only when a price level's *aggregate* view changes.**
If ten orders sit at the best bid and one of them is added, modified, or partially filled, the MBO stream fires immediately with that specific event. The MBP feed may not need to publish anything until the aggregate at that price level actually moves (or it may publish a "quantity changed" update with a lag introduced by however the venue batches its book-recalculation). For strategies that care about queue position, order flow toxicity, or the very first sign of aggression at a price, MBO surfaces the information one processing stage earlier.

**3. No "artificial" batching/conflation in the raw MBO feed.**
Exchanges often conflate or snapshot their aggregated book feeds more aggressively for bandwidth reasons (e.g., CME's conflated UDP/TCP groups, or the "top 10" limited-depth MBOLD product, are explicitly overlay/snapshot-based: unlike standard incremental book processing, this limited-depth product completely restates the book with each new snapshot refresh message rather than sending granular incremental deltas). Full-depth MBO, by contrast, is built to be a pure incremental log, sequenced and timestamped at nanosecond granularity, so the client can process events as they occur rather than waiting for a periodic restatement.

**4. Encoding and framing.**
Modern MBO feeds (CME SBE, Nasdaq ITCH + MoldUDP64) use fixed-length binary encoding designed for branchless, allocation-free parsing: fixed-length fields, native byte order, and proper alignment let the client access message fields directly in the network buffer without a complex sequential decoding process. This matters equally for MBP feeds using the same encoding, so it's not the deciding factor on its own — but it compounds with points 1–3 to push total MBO tick-to-trade latency into the tens-of-microseconds range that vendors advertise (e.g., a 90th-percentile latency to the application of 42 microseconds over a cross-connect, or 590 microseconds over the public internet, for a normalized CME feed).

## Technical differences, side by side

| | MBO / Level 3 | MBP / Level 2 (aggregated book) |
|---|---|---|
| Granularity | Individual order (unique order ID, its own priority/rank) | Price level (total resting size at each price) |
| What's disseminated | Every add/modify/cancel/execute/replace event | Net change in size at a price level (or periodic snapshot) |
| Queue position | Recoverable — you can rank your own resting order against every other order ahead of it | Not recoverable — you only know the aggregate, not who's in front of you or in what order |
| State ownership | Client must maintain the book itself, applying each event in sequence order | Exchange has already done the state-keeping; client mostly just applies level deltas |
| Bandwidth / message volume | Much higher message rate (one message per order event) | Lower — many order-level events can collapse into "no visible change at this price level" |
| Anonymity | Order IDs are exchange-internal handles, not participant identities, but order-level detail (size, timing, priority) is exposed | Only the aggregate is exposed — most granular signal is hidden |
| Latency to publish | Lower — closer to a raw log of matching-engine events | Higher — an extra aggregation/book-building step sits between the match and the message |

## Why HFT firms reconstruct the book from MBO rather than just consuming the exchange's published MBP

**1. Speed, restated as strategy-relevance.**
Because MBO delivers each event one processing stage earlier and doesn't wait for level-aggregation, a firm that reconstructs its own book from MBO sees changes to the top of book — and to depth beyond it — strictly before, or at least no later than, the exchange's own published MBP update reflects the same change. In latency-sensitive strategies, being "first" to react to a book change is often the entire edge, so consuming the derived (and inherently lagged) product is a non-starter.

**2. Information the aggregated feed literally cannot contain — queue position.**
This is arguably the bigger reason, independent of latency. MBO carries the order reference number and priority for every resting order, which lets a firm know exactly where its own order sits in the queue at a price level, and how that queue is being built and drained order-by-order. CME is explicit that this is a first-class feature of the MBO product: systems must sort first by price and then by the order-priority tag to reconstruct the true book order, since priority is not guaranteed to be sequential across price levels, and priority assignment follows a defined sequencing rule based on the order the exchange gateway actually received the messages in, applied regardless of the matching algorithm. An MBP feed simply discards this — you get the total at a price, never the internal composition or order of the queue. Anything that depends on fill probability (how many shares/contracts are ahead of you before your resting order gets touched) requires MBO.

**3. Depth and granularity beyond what MBP publishes.**
Aggregated books are frequently truncated — e.g., top-N levels, or "limited depth" variants like CME's MBOLD, which explicitly caps at the top 10 bid and ask orders for bandwidth and anonymity reasons. A firm reconstructing from full-depth MBO retains visibility arbitrarily deep into the book, including levels the standard published aggregate feed may never surface.

**4. Own-order tracking and internal consistency.**
A firm needs to reconcile its own resting orders against the book state at the order-ID level to manage risk, detect partial fills, and time cancel/replace decisions correctly. That bookkeeping is native to MBO (it's built around order IDs) and awkward or impossible to do precisely from an aggregated feed.

**5. Why the exchange's own MBP feed still gets used — as a checksum, not a primary input.**
Reconstructing a full order book from a raw incremental order-event stream is genuinely hard to get exactly right at scale: sequence gaps, out-of-order UDP packets, dropped messages, snapshot resynchronization after a disconnect, and correctly handling every edge case in the update-action semantics (implied orders, order-priority ties, replace-vs-cancel/new semantics) all introduce room for a subtle reconstruction bug. Reconstruction efforts openly describe this as the hard part of the exercise — beyond simply parsing the binary protocol, the reconstruction also has to retrieve and track the state of every prior order that a new message refers back to. Because the exchange's own aggregated MBP feed is authoritative and built directly from the matching engine's true state (not from a client-side replay of potentially lossy multicast), it functions as a **ground truth checksum**: a firm periodically diffs its internally reconstructed, order-level book (collapsed to price levels) against the exchange's published aggregate. Any mismatch is a strong signal of a bug, a dropped/out-of-order packet, or a missed resync — something you want to catch before it silently corrupts trading decisions, not something you want to depend on for the decisions themselves, since it's both slower and coarser than what you built yourself.

## A pedagogical framing

This is a nice fit for the "judgment over code" thesis. The naive move is "just subscribe to the order book feed, it's simpler." The judgment move is recognizing that (a) the aggregated feed is a derived, lagged, lossy-by-design product, (b) the raw event stream contains information (queue priority, own-order tracking, full depth) that aggregation destroys by construction, and (c) building your own reconstruction introduces a new class of correctness risk that has to be actively guarded against — which is precisely why the "smart" architecture uses the slower, official feed as a validator rather than a shortcut. That's a good contrast pair for an exam snippet: one version naively parses only the MBP feed and calls it done; the plausible-but-wrong version reconstructs from MBO but has no reconciliation step against the exchange's published book, silently drifting after a dropped packet.

## Sources

- [MDP 3.0 - Market By Order Limited Depth Book Processing — CME Group Client Systems Wiki](https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/MDP+3.0+-+Market+By+Order+Limited+Depth+Book+Processing)
- [MDP 3.0 - Market by Order - Book Management — CME Group Client Systems Wiki](https://cmegroupclientsite.atlassian.net/wiki/display/EPICSANDBOX/MDP+3.0+-+Market+by+Order+-+Book+Management)
- [White Paper: CME MDP 3.0 — B2BITS](https://www.b2bits.com/product_support/e-library/white-paper-cme-mdp-30)
- [CME MDP Premium Market Data Handler SDK — OnixS](https://www.onixs.biz/cme-mdp-premium-market-data-handler.html)
- [Java Market Data Handler for CME MDP 3.0 — epam](http://epam.github.io/java-cme-mdp3-handler/)
- [CME Globex MDP 3.0 — Databento](https://databento.com/datasets/GLBX.MDP3)
- [What Is Nasdaq TotalView? Key Features and Benefits — Nasdaq](https://www.nasdaq.com/articles/data/nasdaq-totalview)
- [The Short-Term Predictability of Returns in Order Book Markets: a Deep Learning Perspective (arXiv, LOBSTER/ITCH description)](https://arxiv.org/pdf/2211.13777)
- [ITCH — Nasdaq Order Book Reconstructor (martinobdl)](https://github.com/martinobdl/ITCH)
