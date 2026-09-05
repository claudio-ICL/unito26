"""Limit order books: folding a stream of orders into a book.

The strand is built as a ladder of increasing complexity, and the modules follow it:

``messages``
    the order tuple ``(t, q, p, d)``, event types, and tick/currency conversion.
``orderbook``
    both representations of the book -- the aggregate ``{price: size}`` one and the
    order-level, identity-carrying one, in a single file.
``delta_log``
    a session recorded as the level changes rather than as the states, and the book
    rebuilt from them.
``session``
    the ``MarketSession`` -- a LOBSTER-shaped frame plus the statistics read off it --
    and the three ways of building one: two folds through a book, and a delta log
    replayed.  Every row of one is an aggressive order or another single message.
``statistics``
    which statistics a session records: the one declaration its column names, their
    order, its coverage flags and the fold's write positions are all read off.
``frames``
    the serialization protocol the parameter classes implement, and LOBSTER's vocabulary.
``config``
    example parametrizations, frozen as records.
``binary_gaps``
    an integer as a set of bit positions: the vocabulary the bitmap books are written in.
``hawkes``
    multivariate Hawkes order flow: the timing and type of events.
``simulate``
    marks -- turning an event type into an actual order, given the book.
``lobster``
    the LOBSTER sample files: the named pair, the tick-size to price-unit conversion,
    the schema-declared loaders and the windowed aligned read.
``lobster_session``
    a LOBSTER pair held as the files hold it, positionally indexed, and the coarsening
    that turns it into a ``MarketSession`` -- the feed writes a row per resting order
    consumed, and a session has a row per order that consumed them.
``worked_examples``
    the catalogue of book transitions, one per branch of the update rule, shared by
    the tests, the notebook and the documentation.
``benchmark``
    timing and memory for the variants; the numbers belong in a notebook, not a test.
``visualization``
    a book drawn as text for the documentation, and a book or a session drawn as plotly
    for the notebooks.

The organising idea is in ``documentation/order-flow-to-order-book.md``: the aggregate
state is closed under the arrival of an order, so it reproduces the whole public book,
and it stops being sufficient the moment a question concerns a *named* order.
"""
