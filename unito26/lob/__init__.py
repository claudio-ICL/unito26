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
``worked_examples``
    the catalogue of book transitions, one per branch of the update rule, shared by
    the tests, the notebook and the documentation.
``benchmark``
    timing and memory for the variants; the numbers belong in a notebook, not a test.
``visualization``
    a book drawn as text for the documentation and as plotly for the notebook.

The organising idea is in ``documentation/order-flow-to-order-book.md``: the aggregate
state is closed under the arrival of an order, so it reproduces the whole public book,
and it stops being sufficient the moment a question concerns a *named* order.
"""
