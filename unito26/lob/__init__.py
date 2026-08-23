"""Limit order books: folding a stream of orders into a book.

The strand is built as a ladder of increasing complexity, and the modules follow it:

``messages``
    the order tuple ``(t, q, p, d)``, event types, and tick/currency conversion.
``orderbook``
    both representations of the book -- the aggregate ``{price: volume}`` one and the
    order-level, identity-carrying one -- deliberately in a single file.
``replay``
    the fold that drives a book with a stream of messages, plus the snapshot taps that
    turn a live book into a time series.
``hawkes``
    multivariate Hawkes order flow: the timing and type of events.
``simulate``
    marks -- turning an event type into an actual order, given the book.
``lobster``
    a read-only loader and descriptive statistics for the LOBSTER sample files.

The organising idea is in ``documentation/order-flow-to-order-book.md``: the aggregate
book is a sufficient statistic for the *public* book, and it stops being sufficient the
moment a question concerns a *named* order.
"""
