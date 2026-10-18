"""Drawing a book, a session and a point process: as text for the documentation, as plotly
elsewhere.

The text ladder goes into markdown and into the lecture notes, where it must survive
version control and be readable in a diff.  The plotly figures are for a notebook, where
a level can be hovered and read.

Two conventions hold for every series of a book or a session here.  The lines are **steps**
(``line_shape="hv"``): the book holds each state until the next message, so a sloped
segment would draw a state the book never had.  And a padded level is plotted as NaN
with ``connectgaps=False``, so the line breaks where the side had no such level; drawn
literally, the sentinel price would take the axis to 10^10.

The book figures go through ``levels_map`` and know nothing about how a book stores its
levels; the session figures read the LOBSTER frame and its statistics; the point-process
figures take event times and types, and samples to set against a formula; the figures of
the CKS and the Hawkes flows read :mod:`unito26.lob.coupling`.
"""

from __future__ import annotations

from unito26.lob.messages import BUY, SELL, MessageType, is_market_price
from unito26.lob.orderbook import AggregateBook

__all__ = [
    "use_template",
    "ascii_ladder",
    "describe_message",
    "book_figure",
    "snapshots_figure",
    "example_figure",
    "depth_figure",
    "level_evolution_figure",
    "touch_figure",
    "gap_figure",
    "imbalance_figure",
    "coverage_figure",
    "band_width_figure",
    "intensity_figure",
    "state_figure",
    "matrix_figure",
    "raster_figure",
    "counting_figure",
    "monte_carlo_figure",
    "exponential_qq_figure",
    "mids_figure",
    "touch_walks_figure",
    "first_times_figure",
    "discrepancy_fan_figure",
    "variance_split_figure",
    "distance_terms_figure",
]

#: The first four slots of the categorical palette, in order.  A side keeps its colour
#: in every figure, so the mapping is learned once; the panels are told apart by their
#: axes rather than by their palette.
BID_COLOUR = "#2a78d6"
ASK_COLOUR = "#eb6834"
MID_COLOUR = "#1baf7a"
MICRO_COLOUR = "#eda100"
#: Categories without a side -- the event types of a point process -- take these by slot.
PALETTE = (BID_COLOUR, ASK_COLOUR, MID_COLOUR, MICRO_COLOUR, "#7e57c2", "#5b7f8a")

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"


def use_template(name: str = "unito26") -> None:
    """Register the course plotly template and make it the default."""
    import plotly.graph_objects as go
    import plotly.io as pio

    axis = dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    pio.templates[name] = go.layout.Template(
        layout=dict(
            paper_bgcolor=SURFACE,
            plot_bgcolor=SURFACE,
            font=dict(color=INK, size=12),
            xaxis=axis,
            yaxis=axis,
        )
    )
    pio.templates.default = name


def describe_message(message) -> str:
    """One line naming what a message asks the book to do, in the notation's terms."""
    side = "buy" if message.direction == BUY else "sell"
    if message.kind is MessageType.WITHDRAW:
        return f"withdraw {message.size} from the {side} side at {message.price}"
    if is_market_price(message.price):
        return f"market {side} {message.size}"
    return f"{side} {message.size} @ {message.price}"


def ascii_ladder(book: AggregateBook, bar: int = 28) -> str:
    """The book as a price ladder in text, asks above bids, best prices in the middle.

    Every occupied price appears, and only occupied prices: an empty grid position
    inside the book is shown as a gap in the price column, which is what makes the two
    empty levels of the walking case visible at a glance.
    """
    bids = book.levels_map(BUY)
    asks = book.levels_map(SELL)
    if not bids and not asks:
        return "    (empty book)"

    largest = max([*bids.values(), *asks.values()])
    rows = []
    for price in sorted(asks, reverse=True):
        size = asks[price]
        rows.append(
            f"  {price:>6}  {'#' * max(1, round(bar * size / largest)):<{bar}} {size:>5}  ask"
        )
    if bids and asks:
        spread = min(asks) - max(bids)
        rows.append(f"  {'':>6}  {'-' * bar}  spread {spread}")
    for price in sorted(bids, reverse=True):
        size = bids[price]
        rows.append(
            f"  {price:>6}  {'#' * max(1, round(bar * size / largest)):<{bar}} {size:>5}  bid"
        )
    return "\n".join(rows)


def _bars(book: AggregateBook, depth: int):
    """Two plotly bar traces, bids and asks, as (price, size) at the grid positions."""
    import plotly.graph_objects as go

    traces = []
    for direction, name, colour in ((BUY, "bid", BID_COLOUR), (SELL, "ask", ASK_COLOUR)):
        levels = [(p, v) for p, v in book.levels(direction, depth) if v]
        if not levels:
            continue
        prices, sizes = zip(*levels)
        cumulative = []
        total = 0
        for size in sizes:
            total += size
            cumulative.append(total)
        traces.append(
            go.Bar(
                x=sizes,
                y=prices,
                name=name,
                orientation="h",
                marker_color=colour,
                customdata=cumulative,
                hovertemplate=(
                    "%{y} &times; %{x}<br>cumulative %{customdata}<extra>" + name + "</extra>"
                ),
            )
        )
    return traces


def book_figure(book: AggregateBook, depth: int = 10, title: str = "") -> "object":
    """The ladder as horizontal bars, price on the vertical axis where it belongs."""
    import plotly.graph_objects as go

    figure = go.Figure(_bars(book, depth))
    figure.update_layout(
        title=title,
        xaxis_title="size",
        yaxis_title="price (ticks)",
        barmode="overlay",
        template="simple_white",
        height=420,
    )
    return figure


def snapshots_figure(books: dict, depth: int = 10, title: str = "") -> "object":
    """Several books on one pair of axes, with a dropdown choosing which is drawn.

    ``books`` maps a label to an :class:`~unito26.lob.orderbook.AggregateBook`.  One at a
    time rather than side by side: the books are compared at the same size axis, and a
    panel each would give them a width each as well.

    Each button's mask spans every trace in the figure, in trace order, and the initial
    ``visible`` must agree with ``active``.  A side contributes no trace where it is
    empty, so the masks are built from the counts rather than from a stride.
    """
    import plotly.graph_objects as go

    figure = go.Figure()
    counts = []
    for slot, (label, book) in enumerate(books.items()):
        traces = _bars(book, depth)
        counts.append(len(traces))
        for trace in traces:
            trace.visible = slot == 0
            trace.showlegend = slot == 0
            figure.add_trace(trace)

    total = sum(counts)
    starts = [sum(counts[:slot]) for slot in range(len(counts))]
    buttons = [
        dict(
            label=label, method="update",
            args=[
                {"visible": [starts[slot] <= i < starts[slot] + counts[slot]
                             for i in range(total)],
                 "showlegend": [starts[slot] <= i < starts[slot] + counts[slot]
                                for i in range(total)]},
                {"title": f"{title} — {label}" if title else label},
            ],
        )
        for slot, label in enumerate(books)
    ]
    figure.update_layout(
        title=f"{title} — {next(iter(books))}" if title else next(iter(books)),
        updatemenus=[dict(buttons=buttons, active=0, x=1.0, xanchor="right", y=1.16,
                          yanchor="top", showactive=True)],
        xaxis_title="size",
        yaxis_title="price (ticks)",
        barmode="overlay",
        template="simple_white",
        height=460,
        margin=dict(t=110),
    )
    return figure


def example_figure(example, depth: int = 8) -> "object":
    """One worked example: the book before and after, side by side.

    They are drawn together because the example is about the difference between them,
    which a single state does not show.
    """
    from plotly.subplots import make_subplots

    from unito26.lob.worked_examples import to_sides

    figure = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        subplot_titles=("before", "after"),
    )
    for column, state in ((1, example.before), (2, example.after)):
        book = AggregateBook.from_levels(*to_sides(state))
        for trace in _bars(book, depth):
            trace.showlegend = column == 1
            figure.add_trace(trace, row=1, col=column)
    figure.update_layout(
        title=f"{example.name} — {describe_message(example.message)}",
        template="simple_white",
        barmode="overlay",
        height=440,
    )
    figure.update_xaxes(title_text="size")
    figure.update_yaxes(title_text="price (ticks)", row=1, col=1)
    return figure


def depth_figure(book: AggregateBook, depth: int = 20) -> "object":
    """Cumulative size against price: what an order of a given size would cost.

    The same data as the ladder, read the other way: this is the curve a metaorder walks
    down, so its slope measures the book's resilience to size.
    """
    import plotly.graph_objects as go

    figure = go.Figure()
    for direction, name, colour in ((BUY, "bid", BID_COLOUR), (SELL, "ask", ASK_COLOUR)):
        prices, cumulative, total = [], [], 0
        for price, size in book.levels(direction, depth):
            total += size
            prices.append(price)
            cumulative.append(total)
        figure.add_trace(
            go.Scatter(
                x=prices,
                y=cumulative,
                name=name,
                mode="lines+markers",
                line_shape="hv",
                marker_color=colour,
                hovertemplate="through %{x}: %{y} shares<extra>" + name + "</extra>",
            )
        )
    figure.update_layout(
        title="cumulative depth",
        xaxis_title="price (ticks)",
        yaxis_title="cumulative size",
        template="simple_white",
        height=420,
    )
    return figure


# ---- the session ---------------------------------------------------------------------


def _steps(x, y, name: str, colour: str, **kwargs):
    """One step line.  ``connectgaps=False`` so a NaN run reads as absence, not as a
    straight line drawn through it."""
    import plotly.graph_objects as go

    line = dict(color=colour, width=2) | kwargs.pop("line", {})
    return go.Scatter(
        x=x, y=y, name=name, mode="lines", line_shape="hv",
        line=line, connectgaps=False, **kwargs,
    )


def _level_series(session, side: str, kind: str, level: int, window: slice):
    """One reported level's price (in ticks) or size, with padded rows as NaN."""
    import numpy as np

    from unito26.lob.frames import ASK_PADDING, BID_PADDING

    book = session.lobster_book.iloc[window]
    padding = ASK_PADDING if side == "Ask" else BID_PADDING
    price = book[f"{side}Price{level}"].to_numpy(dtype=float)
    values = book[f"{side}{kind}{level}"].to_numpy(dtype=float)
    scale = session.price_unit if kind == "Price" else 1
    return np.where(price == padding, np.nan, values / scale)


def level_evolution_figure(session, window: slice):
    """Queues and prices at one reported level, with a dropdown choosing the level.

    Two panels sharing a time axis: size above, price below, each carrying both sides.
    Splitting by quantity rather than by side puts the two sides on the same axis, so a
    queue draining above and a price stepping below are visibly the same event.  In the
    price panel the two lines cannot cross, and the distance between them is the
    ``n``-level spread.

    ``n`` selects a *reported* level -- the ``n``-th price carrying size -- because
    that is what the frame holds.  On a book with holes that is not the grid level of
    the same number.
    """
    from plotly.subplots import make_subplots

    depth = session.reported_depth
    times = session.lobster_book.index[window]
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("Size at the level", "Price of the level"),
    )
    for level in range(1, depth + 1):
        for row, kind in ((1, "Size"), (2, "Price")):
            for side, colour in (("Bid", BID_COLOUR), ("Ask", ASK_COLOUR)):
                figure.add_trace(
                    _steps(
                        times, _level_series(session, side, kind, level, window),
                        side.lower(), colour, visible=(level == 1),
                        legendgroup=side, showlegend=(row == 1 and level == 1),
                    ),
                    row=row, col=1,
                )

    # Each button's mask spans every trace in the figure, in trace order, and switches
    # both panels together.  The initial `visible` above must agree with `active`.
    per_level = 4
    buttons = [
        dict(
            label=f"level {level}", method="update",
            args=[
                {"visible": [i // per_level == level - 1 for i in range(per_level * depth)]},
                {"title": f"Reported level {level}"},
            ],
        )
        for level in range(1, depth + 1)
    ]
    figure.update_layout(
        title="Reported level 1",
        updatemenus=[dict(buttons=buttons, active=0, x=1.0, xanchor="right", y=1.14,
                          yanchor="top", showactive=True)],
        template="simple_white", hovermode="x unified",
        height=620, margin=dict(t=110, r=20),
        legend=dict(orientation="h", y=1.06, x=0),
    )
    figure.update_yaxes(title_text="shares", row=1, col=1)
    figure.update_yaxes(title_text="ticks", row=2, col=1)
    figure.update_xaxes(title_text="session time (s)", row=2, col=1)
    return figure


def touch_figure(session, window: slice):
    """Mid-price and micro-price between the two touches.

    ``P^mu = P^m + (phi/2) I^1`` places the micro-price inside the spread and toward the
    thin side, so the vertical distance from the mid to the micro is the imbalance read
    in ticks.
    """
    import plotly.graph_objects as go

    stats = session.stats.iloc[window]
    times = stats.index
    ask = stats["MidPrice"] + stats["Spread"] / 2
    bid = stats["MidPrice"] - stats["Spread"] / 2
    figure = go.Figure([
        _steps(times, ask, "best ask", ASK_COLOUR, line=dict(color=ASK_COLOUR, width=1, dash="dot")),
        _steps(times, bid, "best bid", BID_COLOUR, line=dict(color=BID_COLOUR, width=1, dash="dot")),
        _steps(times, stats["MidPrice"], "mid-price", MID_COLOUR),
        _steps(times, stats["MicroPrice"], "micro-price", MICRO_COLOUR),
    ])
    figure.update_layout(
        title="The micro-price inside the spread", template="simple_white",
        hovermode="x unified", height=420,
        xaxis_title="session time (s)", yaxis_title="ticks",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return figure


#: Which gap a trace is about.  A side keeps its colour in every panel, so the dash is
#: what is left to carry "nearest the touch" against "largest".
NEAREST_DASH = "solid"
LARGEST_DASH = "dot"


def gap_figure(session, window: slice):
    """The spread, how large the holes behind it are, and how far away they sit.

    The spread is a gap at the touch; the panels below describe the gaps behind it.  A
    book can hold a one-tick spread and still be full of holes two levels back, which is
    what separates the two indexings.

    One panel per kind of quantity -- levels, then ticks -- because the two are not on
    the same scale and a shared axis would flatten one of them.  Within a panel the side
    is the colour and the gap is the dash.

    The distance lines **break wherever a side is contiguous**.  There is no gap then, so
    there is no distance to plot, and a step line drawn through it would assert one.
    """
    from plotly.subplots import make_subplots

    stats = session.stats.iloc[window]
    times = stats.index
    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
        subplot_titles=(
            "Spread",
            "Gap size, in levels",
            "Distance from the touch to the gap, in ticks",
        ),
    )
    figure.add_trace(_steps(times, stats["Spread"], "spread", MID_COLOUR), row=1, col=1)
    for side, colour in (("Bid", BID_COLOUR), ("Ask", ASK_COLOUR)):
        for column, label, dash in (
            (f"{side}LargestGap", "largest", LARGEST_DASH),
            (f"{side}FirstGapSize", "nearest", NEAREST_DASH),
        ):
            figure.add_trace(
                _steps(
                    times, stats[column], f"{side.lower()}, {label}", colour,
                    line=dict(color=colour, width=2, dash=dash),
                ),
                row=2, col=1,
            )
        for column, label, dash in (
            (f"{side}FirstGapDistance", "nearest", NEAREST_DASH),
            (f"{side}LargestGapDistance", "largest", LARGEST_DASH),
        ):
            figure.add_trace(
                _steps(
                    times, stats[column], f"{side.lower()}, {label}", colour,
                    line=dict(color=colour, width=2, dash=dash), showlegend=False,
                ),
                row=3, col=1,
            )
    figure.update_layout(
        title="Spread and sparsity", template="simple_white", hovermode="x unified",
        height=760, legend=dict(orientation="h", y=1.05, x=0),
    )
    figure.update_yaxes(title_text="ticks", row=1, col=1)
    figure.update_yaxes(title_text="levels", row=2, col=1)
    figure.update_yaxes(title_text="ticks", row=3, col=1)
    figure.update_xaxes(title_text="session time (s)", row=3, col=1)
    return figure


def imbalance_figure(session, n, window: slice):
    """``I^n`` on the price grid, against the same expression evaluated by column.

    Both series stay in ``[-1, 1]`` and both move with the market.  They coincide while
    the reported levels are contiguous and separate as soon as they are not; the second
    is :meth:`~unito26.lob.session.MarketSession.column_sliced_imbalance`, which says what
    it computes.
    """
    import plotly.graph_objects as go

    stats = session.stats.iloc[window]
    times = stats.index
    by_column = session.column_sliced_imbalance(n).iloc[window]
    figure = go.Figure([
        _steps(times, stats[f"QueueImbalance{n}"], f"I^{n} on the grid", BID_COLOUR),
        _steps(times, by_column, f"first {n} size columns", ASK_COLOUR),
    ])
    figure.update_layout(
        title=f"Queue imbalance at n = {n}", template="simple_white",
        hovermode="x unified", height=420,
        xaxis_title="session time (s)", yaxis_title="imbalance",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return figure


def coverage_figure(sessions_by_depth: dict):
    """How much of a session a frame of a given reported depth cannot answer.

    One line per reported depth, over the grid depths the sessions carry.  This is the
    figure that turns "how deep a file do I need" into a number for a given market.
    """
    import plotly.graph_objects as go

    figure = go.Figure()
    for slot, (depth, session) in enumerate(sorted(sessions_by_depth.items())):
        levels = list(session.statistics.imbalance_levels)
        uncovered = [
            float(1.0 - session.stats[f"QueueImbalance{n}Covered"].mean()) for n in levels
        ]
        figure.add_trace(
            go.Scatter(
                x=levels, y=uncovered, name=f"reported depth {depth}", mode="lines+markers",
                line=dict(color=(BID_COLOUR, ASK_COLOUR, MID_COLOUR, MICRO_COLOUR)[slot % 4],
                          width=2),
                marker=dict(size=8),
            )
        )
    figure.update_layout(
        title="Fraction of the session where I^n is not recoverable from the frame",
        template="simple_white", height=420,
        xaxis_title="grid depth n", yaxis_title="fraction uncovered",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return figure


def band_width_figure(timings, title: str):
    """Seconds against the width of the band, one line per occupancy structure.

    A chart rather than a table because the x axis is continuous and the point is a
    *crossing*: two lines whose order reverses, which a table of numbers makes the reader
    find for themselves.  The band is drawn on a log axis, since it is varied by
    multiplying.

    ``timings`` is a frame indexed by band width in ticks, one column per structure.
    """
    import plotly.graph_objects as go

    colours = (BID_COLOUR, ASK_COLOUR, MID_COLOUR, MICRO_COLOUR)
    figure = go.Figure([
        go.Scatter(
            x=timings.index, y=timings[column], name=column, mode="lines+markers",
            line=dict(color=colours[slot % 4], width=2), marker=dict(size=8),
        )
        for slot, column in enumerate(timings.columns)
    ])
    figure.update_layout(
        title=title, template="simple_white", hovermode="x unified", height=420,
        legend=dict(orientation="h", y=1.06, x=0),
    )
    figure.update_xaxes(title_text="band width (ticks)", type="log")
    figure.update_yaxes(title_text="seconds", rangemode="tozero")
    return figure


# ---- point processes -----------------------------------------------------------------


def _state_at_jumps(params, times, types, clock):
    """The state ``Z`` of a path started from empty, read on ``clock`` and at every event
    on it twice, just before the event and just after, so that a line through the readings
    jumps at its events and not across the step of the clock that holds them.

    Returns the times of the readings, the readings, and the times and types of the events
    on the clock.
    """
    import numpy as np

    from unito26.lob.hawkes import Clock, decayed_counts_at

    times = np.asarray(times, dtype=float)
    types = np.asarray(types, dtype=int)
    clock = np.asarray(clock, dtype=float)
    shown = (times >= clock[0]) & (times <= clock[-1])
    events, kinds = times[shown], types[shown]
    empty = np.zeros(params.dimension)

    def state(at):
        return decayed_counts_at(params.decay, times, types, empty, Clock(at))

    grid = np.sort(np.concatenate([clock, events]))
    after = state(events) + np.eye(params.dimension)[kinds]
    x = np.concatenate([grid, events])
    states = np.concatenate([state(grid), after])
    order = np.lexsort((np.r_[np.zeros(grid.size), np.ones(events.size)], x))
    return x[order], states[order], events, kinds


def _event_ticks(events, kinds, slot: int, label: str):
    """The events of one type as ticks, on the line of an event strip that is the type's."""
    import numpy as np
    import plotly.graph_objects as go

    mine = events[kinds == slot]
    return go.Scatter(
        x=mine, y=np.full(mine.size, slot), mode="markers", showlegend=False,
        marker=dict(symbol="line-ns-open", size=10, color=PALETTE[slot % len(PALETTE)]),
        legendgroup=label, hovertemplate="%{x:.3f} s<extra>" + label + "</extra>",
    )


def _event_strip_axes(figure, labels, row: int) -> None:
    figure.update_yaxes(
        tickvals=list(range(len(labels))), ticktext=list(labels),
        range=[-0.6, len(labels) - 0.4], row=row, col=1,
    )
    figure.update_xaxes(title_text="time (s)", row=row, col=1)


def intensity_figure(params, times, types, clock, labels, title: str = ""):
    """The intensity of every type along one path, with the events beneath it.

    ``params`` is the specification the path ``(times, types)`` was drawn from, and the path
    starts from empty.  The intensity is read on ``clock``, and at every event on it twice,
    just before the event and just after, so that each jump is drawn at its event and not
    across the step of the clock that holds it.  The events are ticks in a strip below, one
    row per type.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    x, states, events, kinds = _state_at_jumps(params, times, types, clock)
    y = params.baseline + states @ params.excitation.T

    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.03
    )
    for slot, label in enumerate(labels):
        colour = PALETTE[slot % len(PALETTE)]
        figure.add_trace(
            go.Scatter(
                x=x, y=y[:, slot], name=label, mode="lines",
                line=dict(color=colour, width=1.5), legendgroup=label,
            ),
            row=1, col=1,
        )
        figure.add_trace(_event_ticks(events, kinds, slot, label), row=2, col=1)
    figure.update_yaxes(title_text="intensity (1/s)", rangemode="tozero", row=1, col=1)
    _event_strip_axes(figure, labels, 2)
    figure.update_layout(title=title, height=460, legend=dict(orientation="h", y=1.08, x=0))
    return figure


def state_figure(params, times, types, clock, labels, title: str = ""):
    """The intensity and the state of every type along one path, with the events beneath.

    Three rows on one time axis.  The first is the intensity ``lambda = mu + A Z``; the
    second is the state ``Z``, with a dotted line at its stationary mean ``lambda* / beta``
    for each type; the third is the events, as ticks.  ``params`` is the specification the
    path ``(times, types)`` was drawn from, and the path starts from empty.  Both lines are
    read on ``clock`` and on either side of every event, as in :func:`intensity_figure`.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    x, states, events, kinds = _state_at_jumps(params, times, types, clock)
    intensities = params.baseline + states @ params.excitation.T
    mean = params.stationary_mean()

    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=True, row_heights=[0.42, 0.42, 0.16],
        vertical_spacing=0.03,
    )
    for slot, label in enumerate(labels):
        colour = PALETTE[slot % len(PALETTE)]
        for row, y in ((1, intensities), (2, states)):
            figure.add_trace(
                go.Scatter(
                    x=x, y=y[:, slot], name=label, mode="lines",
                    line=dict(color=colour, width=1.5), legendgroup=label,
                    showlegend=row == 1,
                ),
                row=row, col=1,
            )
        figure.add_trace(
            go.Scatter(
                x=[x[0], x[-1]], y=[mean[slot]] * 2, mode="lines", showlegend=False,
                line=dict(color=colour, width=1, dash="dot"), legendgroup=label,
                hovertemplate="stationary mean %{y:.3f}<extra>" + label + "</extra>",
            ),
            row=2, col=1,
        )
        figure.add_trace(_event_ticks(events, kinds, slot, label), row=3, col=1)
    figure.update_yaxes(title_text="intensity (1/s)", rangemode="tozero", row=1, col=1)
    figure.update_yaxes(title_text="state Z", rangemode="tozero", row=2, col=1)
    _event_strip_axes(figure, labels, 3)
    figure.update_layout(title=title, height=620, legend=dict(orientation="h", y=1.06, x=0))
    return figure


def matrix_figure(matrices: dict, labels, title: str = ""):
    """Several square matrices as heatmaps side by side, on one colour scale.

    ``matrices`` maps a panel name to a matrix indexed by type, row excited and column
    exciting, and ``labels`` names the types.  The entries are printed in the cells, and the
    rows run downwards, so that a panel reads as the matrix is written.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    names = list(matrices)
    arrays = [np.asarray(matrices[name], dtype=float) for name in names]
    top = max(array.max() for array in arrays)
    figure = make_subplots(rows=1, cols=len(names), subplot_titles=names)
    for column, array in enumerate(arrays, start=1):
        figure.add_trace(
            go.Heatmap(
                z=array, x=list(labels), y=list(labels), zmin=0, zmax=top,
                colorscale="Blues", showscale=column == len(names),
                texttemplate="%{z:.3g}",
                hovertemplate="%{x} excites %{y}: %{z:.4g}<extra></extra>",
            ),
            row=1, col=column,
        )
    figure.update_yaxes(autorange="reversed")
    figure.update_xaxes(title_text="exciting type")
    figure.update_yaxes(title_text="excited type", row=1, col=1)
    figure.update_layout(title=title, height=360)
    return figure


def raster_figure(paths: dict, labels, title: str = ""):
    """Event times of several paths, one row per path and one colour per type.

    ``paths`` maps a row name to the ``(times, types)`` of its path.  The rows share the
    time axis, so how sparse and how clustered the events are is compared by eye.
    """
    import numpy as np
    import plotly.graph_objects as go

    figure = go.Figure()
    offsets = np.linspace(-0.15, 0.15, len(labels)) if len(labels) > 1 else [0.0]
    names = list(paths)
    for row, name in enumerate(names):
        times, types = (np.asarray(array) for array in paths[name])
        for slot, label in enumerate(labels):
            mine = times[types == slot]
            figure.add_trace(
                go.Scatter(
                    x=mine, y=np.full(mine.size, row + offsets[slot]), mode="markers",
                    name=label, legendgroup=label, showlegend=row == 0,
                    marker=dict(
                        symbol="line-ns-open", size=12, color=PALETTE[slot % len(PALETTE)]
                    ),
                    hovertemplate="%{x:.3f} s<extra>" + label + "</extra>",
                )
            )
    figure.update_yaxes(
        tickvals=list(range(len(names))), ticktext=names, autorange="reversed",
        showgrid=False, automargin=True,
    )
    figure.update_xaxes(title_text="time (s)")
    figure.update_layout(
        title=title, height=120 + 70 * len(names), legend=dict(orientation="h", y=1.1, x=0)
    )
    return figure


def counting_figure(paths: dict, interval, labels, title: str = ""):
    """The counting process of every type along several paths, one row per path.

    ``paths`` maps a row name to the ``(times, types)`` of its path, and ``interval`` is
    ``(a, b)``.  Each line is N_e(t) - N_e(a) on (a, b]: zero at ``a``, a step of one at each
    event of the type, and held to ``b`` after the last.  The rows share both axes, so the
    slopes are compared by eye.
    """
    import numpy as np
    from plotly.subplots import make_subplots

    start, end = interval
    names = list(paths)
    figure = make_subplots(
        rows=len(names), cols=1, shared_xaxes=True, shared_yaxes="all", vertical_spacing=0.04
    )
    for row, name in enumerate(names, start=1):
        times, types = (np.asarray(array) for array in paths[name])
        for slot, label in enumerate(labels):
            mine = times[(types == slot) & (times > start) & (times <= end)]
            figure.add_trace(
                _steps(
                    np.r_[start, mine, end], np.r_[np.arange(mine.size + 1), mine.size],
                    label, PALETTE[slot % len(PALETTE)], legendgroup=label,
                    showlegend=row == 1,
                    hovertemplate="%{x:.3f} s: %{y}<extra>" + label + "</extra>",
                ),
                row=row, col=1,
            )
        figure.update_yaxes(title_text=name, rangemode="tozero", row=row, col=1)
    figure.update_xaxes(title_text="time (s)", row=len(names), col=1)
    figure.update_layout(
        title=title, height=120 + 130 * len(names), legend=dict(orientation="h", y=1.06, x=0)
    )
    return figure


def monte_carlo_figure(x, samples, formula, labels, title: str = ""):
    """A formula against the mean of independent samples, with a band of two standard
    errors about the mean.

    ``samples`` is ``(paths, len(x), k)``: one value per path, per point of ``x`` and per
    series.  ``formula`` is ``(len(x), k)``.  The standard error is the spread across
    paths over the square root of their number, which is right only when the paths are
    independent; batch means of one long path are passed the same way, a batch per path.
    """
    import numpy as np
    import plotly.graph_objects as go

    samples = np.asarray(samples, dtype=float)
    formula = np.asarray(formula, dtype=float)
    mean = samples.mean(axis=0)
    error = samples.std(axis=0, ddof=1) / np.sqrt(samples.shape[0])
    figure = go.Figure()
    for slot, label in enumerate(labels):
        colour = PALETTE[slot % len(PALETTE)]
        upper = mean[:, slot] + 2 * error[:, slot]
        lower = mean[:, slot] - 2 * error[:, slot]
        figure.add_trace(
            go.Scatter(
                x=np.r_[x, x[::-1]], y=np.r_[upper, lower[::-1]], fill="toself",
                fillcolor=colour, opacity=0.2, line=dict(width=0),
                hoverinfo="skip", showlegend=False, legendgroup=label,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=x, y=mean[:, slot], mode="markers", name=f"{label}, Monte Carlo",
                marker=dict(color=colour, size=5), legendgroup=label,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=x, y=formula[:, slot], mode="lines", name=f"{label}, formula",
                line=dict(color=colour, width=2), legendgroup=label,
            )
        )
    figure.update_layout(title=title, height=420, legend=dict(orientation="h", y=1.1, x=0))
    return figure


def exponential_qq_figure(residuals: dict, levels: int = 1000, title: str = ""):
    """Quantiles of each sample against those of ``Exp(1)``, with two 95% bands.

    ``residuals`` maps a panel name to its sample.  The inner band is pointwise and exact:
    the ``k``-th of ``n`` order statistics of a uniform sample is ``Beta(k, n - k + 1)``,
    and ``-log(1 - u)`` carries it to the exponential.  The outer band is simultaneous: the
    Kolmogorov-Smirnov band ``p +- 1.358 / sqrt(n)``, carried the same way, and drawn
    where it is bounded, since its upper edge is infinite once ``p + 1.358 / sqrt(n)``
    reaches 1.  ``levels`` order statistics are drawn, evenly spread in probability.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from scipy import stats

    names = list(residuals)
    figure = make_subplots(rows=1, cols=len(names), subplot_titles=names)
    for column, name in enumerate(names, start=1):
        sample = np.sort(np.asarray(residuals[name], dtype=float))
        n = sample.size
        ranks = np.unique(np.clip(np.round(np.linspace(0, 1, levels) * n), 1, n)).astype(int)
        probability = ranks / (n + 1)
        theoretical = -np.log1p(-probability)
        pointwise = [
            -np.log1p(-stats.beta.ppf(q, ranks, n - ranks + 1)) for q in (0.025, 0.975)
        ]
        margin = 1.358 / np.sqrt(n)
        bounded = probability + margin < 1
        simultaneous = [
            -np.log1p(-np.clip(probability[bounded] + sign * margin, 0.0, None))
            for sign in (-1, 1)
        ]
        for grid, band, opacity in (
            (theoretical[bounded], simultaneous, 0.12),
            (theoretical, pointwise, 0.3),
        ):
            figure.add_trace(
                go.Scatter(
                    x=np.r_[grid, grid[::-1]],
                    y=np.r_[band[1], band[0][::-1]],
                    fill="toself", fillcolor=MUTED, opacity=opacity, line=dict(width=0),
                    hoverinfo="skip", showlegend=False,
                ),
                row=1, col=column,
            )
        figure.add_trace(
            go.Scatter(
                x=theoretical, y=theoretical, mode="lines", showlegend=False,
                line=dict(color=INK, width=1, dash="dot"), hoverinfo="skip",
            ),
            row=1, col=column,
        )
        figure.add_trace(
            go.Scatter(
                x=theoretical, y=sample[ranks - 1], mode="markers", showlegend=False,
                marker=dict(color=PALETTE[(column - 1) % len(PALETTE)], size=4),
                hovertemplate=(
                    "Exp(1): %{x:.3f}<br>sample: %{y:.3f}<extra>" + name + "</extra>"
                ),
            ),
            row=1, col=column,
        )
        figure.update_xaxes(title_text="Exp(1) quantile", row=1, col=column)
    figure.update_yaxes(title_text="sample quantile", row=1, col=1)
    figure.update_layout(title=title, height=420)
    return figure


# ---- three flows on one path ----------------------------------------------------------

#: Which flow a trace is about: one colour each in every figure of the study, and the dash
#: as a second encoding, so that the books stay apart where their lines coincide.
CKS_COLOUR = PALETTE[2]
HAW_1_COLOUR = PALETTE[4]
HAW_Q_COLOUR = PALETTE[3]
FLOW_STYLE = {
    "CKS": dict(color=CKS_COLOUR, dash="dot"),
    "haw-1": dict(color=HAW_1_COLOUR, dash="solid"),
    "haw-q": dict(color=HAW_Q_COLOUR, dash="dash"),
}

#: Predicted curves set against the coupled runs, in the order they are given: ink first.
FORMULA_LINES = (
    dict(color=INK, width=2, dash="dot"),
    dict(color=MUTED, width=2, dash="dash"),
    dict(color=MUTED, width=1.5, dash="dashdot"),
)


def _flow_style(label: str) -> dict:
    """The style of the flow a label names: the flow alone, ``"haw-1"``, or the flow and,
    after a comma, what sets the run apart, ``"haw-1, η = 0.2"``."""
    return FLOW_STYLE[label.split(",")[0]]


def _flow_steps(times, values, flow: str, **kwargs):
    style = _flow_style(flow)
    return _steps(
        times, values, flow, style["color"],
        line=dict(color=style["color"], width=2.5, dash=style["dash"]), **kwargs,
    )


def _formula_traces(clock, curves: dict, shown: set):
    """A line per predicted curve, styled by position, one legend entry a name."""
    import plotly.graph_objects as go

    for slot, (name, curve) in enumerate(curves.items()):
        yield go.Scatter(
            x=clock, y=curve, mode="lines", name=name, legendgroup=name,
            line=FORMULA_LINES[slot], showlegend=name not in shown,
            hovertemplate="%{x:.3g} s: %{y:.4g}<extra>" + name + "</extra>",
        )
        shown.add(name)


def mids_figure(pairs: dict, title: str = ""):
    """The mid-price of CKS and of each Hawkes flow on one path, with ``chi`` of each.

    ``pairs`` maps a Hawkes flow, ``"haw-1"`` or ``"haw-q"``, to its
    :class:`unito26.lob.coupling.CoupledFlows` on the path; the CKS mid is read from the
    first.  A rule in the colour of a flow marks the first event after which its mid and the
    CKS one differ.
    """
    import plotly.graph_objects as go

    figure = go.Figure()
    first = next(iter(pairs.values())).frame
    figure.add_trace(_flow_steps(first["TimeStamp"], first["CKSMidPrice"], "CKS"))
    for flow, pair in pairs.items():
        figure.add_trace(_flow_steps(pair.frame["TimeStamp"], pair.frame["HawMidPrice"], flow))
    for slot, (flow, pair) in enumerate(pairs.items()):
        time = pair.first_price_discrepancy_time
        if time is not None:
            figure.add_vline(
                x=time, line=dict(color=_flow_style(flow)["color"], width=1.5, dash="dash"),
                annotation_text=f"χ, {flow}", annotation_font_color=INK,
                annotation_position="top right" if slot % 2 == 0 else "bottom right",
            )
    figure.update_layout(
        title=title, template="simple_white", hovermode="x unified", height=460,
        xaxis_title="time (s)", yaxis_title="mid-price P<sup>m</sup> (ticks)",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return figure


def touch_walks_figure(walks, flow: str, title: str = ""):
    """The touch sizes of the CKS and of one Hawkes book up to the first move of each, the
    bid above and the ask below.

    ``walks`` is :func:`unito26.lob.coupling.touch_walks` and ``flow`` names its Hawkes book,
    ``"haw-1"`` or ``"haw-q"``.  A line ends where its book first moves a best price, and a
    rule in its colour marks ``psi`` there.
    """
    from plotly.subplots import make_subplots

    times = walks.index.to_numpy()
    books = {"CKS": "CKS", "Haw": flow}
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, shared_yaxes="all", vertical_spacing=0.08,
        subplot_titles=(
            "Size at the best bid S<sup>b</sup>", "Size at the best ask S<sup>a</sup>"
        ),
    )
    for row, side in enumerate(("Bid", "Ask"), start=1):
        for prefix, label in books.items():
            # A step is drawn only up to the next point, so the last size is carried onto
            # the row of the move for the line to reach it.
            sizes = walks[f"{prefix}{side}Size1"].ffill(limit=1)
            figure.add_trace(
                _flow_steps(times, sizes, label, showlegend=row == 1), row=row, col=1
            )
        figure.update_yaxes(title_text="units", rangemode="tozero", row=row, col=1)
    for prefix, label in books.items():
        moved = walks.index[walks[f"{prefix}BidSize1"].isna()]
        if not len(moved):
            continue
        rule = dict(color=_flow_style(label)["color"], width=1.5, dash="dash")
        figure.add_vline(
            x=moved[0], line=rule, annotation_text=f"ψ, {label}", annotation_font_color=INK,
            annotation_position="top", row=1, col=1,
        )
        figure.add_vline(x=moved[0], line=rule, row=2, col=1)
    figure.update_xaxes(title_text="time (s)", row=2, col=1)
    figure.update_layout(
        title=title, template="simple_white", hovermode="x unified", height=580,
        legend=dict(orientation="h", y=-0.15, x=0),
    )
    return figure


def first_times_figure(times: dict, clock, predicted: dict, y_title: str, title: str = ""):
    """The survival of a first time -- ``chi``, or a first move ``psi`` -- in a grid of
    panels, on a logarithmic time axis.

    ``times[row][column]`` maps a flow, ``"CKS"``, ``"haw-1"`` or ``"haw-q"``, to the first
    time of each path of one experiment, NaN where it had not come by the end of ``clock``;
    its empirical survival is drawn as steps in the colour of the flow.  The rows and the
    columns are what is varied, ``Sbar`` and ``DepthDecay`` say.  ``predicted[row][column]``,
    where present, maps a name to a curve on ``clock``, drawn in the styles of
    ``FORMULA_LINES`` by position.
    """
    import numpy as np
    from plotly.subplots import make_subplots

    clock = np.asarray(clock, dtype=float)
    row_labels = list(times)
    column_labels = list(next(iter(times.values())))
    figure = make_subplots(
        rows=len(row_labels), cols=len(column_labels), shared_xaxes=True, shared_yaxes=True,
        horizontal_spacing=0.025, vertical_spacing=0.1,
        subplot_titles=[f"{row}, {column}" for row in row_labels for column in column_labels],
    )
    shown = set()
    for r, row in enumerate(row_labels, start=1):
        for c, column in enumerate(column_labels, start=1):
            for flow, sample in times[row][column].items():
                sample = np.asarray(sample, dtype=float)
                come = np.sort(sample[np.isfinite(sample)])
                survival = 1.0 - np.searchsorted(come, clock, side="right") / sample.size
                figure.add_trace(
                    _flow_steps(
                        clock, survival, flow, legendgroup=flow, showlegend=flow not in shown,
                        hovertemplate="%{x:.3g} s: %{y:.3f}<extra>" + flow + "</extra>",
                    ),
                    row=r, col=c,
                )
                shown.add(flow)
            curves = predicted.get(row, {}).get(column, {})
            for trace in _formula_traces(clock, curves, shown):
                figure.add_trace(trace, row=r, col=c)
    figure.update_xaxes(type="log", range=[np.log10(clock[0]), np.log10(clock[-1])], dtick=1)
    for c in range(1, len(column_labels) + 1):
        figure.update_xaxes(title_text="time (s)", row=len(row_labels), col=c)
    for r in range(1, len(row_labels) + 1):
        figure.update_yaxes(title_text=y_title, row=r, col=1)
    figure.update_yaxes(range=[0, 1.04])
    figure.update_layout(
        title=title, template="simple_white", height=300 * len(row_labels) + 160,
        legend=dict(orientation="h", y=-0.3 / len(row_labels), x=0), hovermode="x unified",
    )
    return figure


def _side_by_side(flows, title: str, y_title: str):
    from plotly.subplots import make_subplots

    figure = make_subplots(
        rows=1, cols=len(flows), shared_yaxes=True, horizontal_spacing=0.04,
        subplot_titles=list(flows),
    )
    for column in range(1, len(flows) + 1):
        figure.update_xaxes(title_text="time (s)", row=1, col=column)
    figure.update_yaxes(title_text=y_title, row=1, col=1)
    figure.update_layout(
        title=title, template="simple_white", height=440, hovermode="x unified",
        legend=dict(orientation="h", y=-0.2, x=0),
    )
    return figure


def discrepancy_fan_figure(fans: dict, clock, shown: int, title: str = ""):
    """The fan of ``D_t = P^{m,CKS}_t - P^{m,haw}_t`` across runs, a panel per Hawkes flow.

    ``fans`` maps a panel, labelled by its flow, ``"haw-1"`` or ``"haw-q"``, alone or followed
    by a comma and what sets the runs apart, to the discrepancies of its runs on ``clock``,
    the last axis being time: one path placed with many mark seeds, or many paths
    with many each.  The first ``shown`` runs are drawn as thin lines, the mean over every
    run in the colour of the flow, and a band one standard deviation either side of it.
    """
    import numpy as np
    import plotly.graph_objects as go

    clock = np.asarray(clock, dtype=float)
    figure = _side_by_side(fans, title, "D<sub>t</sub> (ticks)")
    for column, (flow, fan) in enumerate(fans.items(), start=1):
        runs = np.asarray(fan, dtype=float).reshape(-1, clock.size)
        mean, spread = runs.mean(axis=0), runs.std(axis=0)
        colour = _flow_style(flow)["color"]
        for k, run in enumerate(runs[:shown]):
            figure.add_trace(
                go.Scatter(
                    x=clock, y=run, mode="lines", line_shape="hv", name="a run",
                    legendgroup="a run", line=dict(color=AXIS, width=1), hoverinfo="skip",
                    showlegend=column == 1 and k == 0,
                ),
                row=1, col=column,
            )
        figure.add_trace(
            go.Scatter(
                x=np.r_[clock, clock[::-1]], y=np.r_[mean + spread, (mean - spread)[::-1]],
                fill="toself", fillcolor=colour, opacity=0.2, line=dict(width=0),
                name="± 1 sd", legendgroup="band", showlegend=column == 1, hoverinfo="skip",
            ),
            row=1, col=column,
        )
        figure.add_trace(
            go.Scatter(
                x=clock, y=mean, mode="lines", name=f"mean, {flow}",
                line=dict(color=colour, width=2.5),
                hovertemplate="%{x:.0f} s: %{y:.3f}<extra>" + flow + "</extra>",
            ),
            row=1, col=column,
        )
    return figure


#: The three columns of a variance split, as each is drawn in the colour of its flow.
SPLIT_DASH = {"Total": "solid", "FlowPart": "dash", "PlacementPart": "dot"}
SPLIT_NAME = {"Total": "total", "FlowPart": "flow part", "PlacementPart": "placement part"}


def variance_split_figure(splits: dict, clock, predicted: dict, title: str = ""):
    """The variance of ``D_t`` and its two parts over time, a panel per Hawkes flow.

    ``splits`` maps a panel, labelled as in :func:`discrepancy_fan_figure`, to its
    :func:`unito26.lob.coupling.variance_split` on ``clock``; the splits stand side by side
    on one scale.  ``Total`` is drawn solid, ``FlowPart`` dashed and
    ``PlacementPart`` dotted, in the colour of the flow.  ``predicted[flow]``, where present,
    maps a name to a curve on ``clock``, drawn in the styles of ``FORMULA_LINES``.
    """
    import numpy as np
    import plotly.graph_objects as go

    clock = np.asarray(clock, dtype=float)
    figure = _side_by_side(splits, title, "variance (ticks²)")
    shown = set()
    for column, (flow, split) in enumerate(splits.items(), start=1):
        colour = _flow_style(flow)["color"]
        for part, dash in SPLIT_DASH.items():
            name = SPLIT_NAME[part]
            figure.add_trace(
                go.Scatter(
                    x=clock, y=split[part].to_numpy(), mode="lines", name=name,
                    legendgroup=name, showlegend=name not in shown,
                    line=dict(color=colour, width=2.5 if part == "Total" else 2, dash=dash),
                    hovertemplate="%{x:.0f} s: %{y:.4g}<extra>" + name + "</extra>",
                ),
                row=1, col=column,
            )
            shown.add(name)
        for trace in _formula_traces(clock, predicted.get(flow, {}), shown):
            figure.add_trace(trace, row=1, col=column)
    figure.update_yaxes(rangemode="tozero")
    return figure


def distance_terms_figure(terms, title: str = ""):
    """The distance ``2 Sbar D`` after each event, and the three terms it is the sum of,
    signed as they enter, on one time axis and one scale.

    ``terms`` is :func:`unito26.lob.coupling.distance_terms`.
    """
    from plotly.subplots import make_subplots

    rows = {
        "2S̄ (P<sup>m,CKS</sup> − P<sup>m,haw</sup>)": terms["Distance"],
        "(a) OFI<sup>CKS</sup> − OFI<sup>haw</sup>": terms["ImbalanceMismatch"],
        "−(b) the best sizes, CKS less Hawkes": -terms["TouchSizeMismatch"],
        "−(c) the outer sizes of the moves less S̄ a tick, CKS less Hawkes":
            -terms["DepthMismatch"],
    }
    figure = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True, shared_yaxes="all", vertical_spacing=0.06,
        subplot_titles=tuple(rows),
    )
    for row, (name, values) in enumerate(rows.items(), start=1):
        figure.add_trace(
            _steps(terms["TimeStamp"], values, name, INK,
                   line=dict(color=INK, width=2 if row == 1 else 1.5), showlegend=False),
            row=row, col=1,
        )
        figure.add_hline(y=0, line=dict(color=AXIS, width=1), row=row, col=1)
        figure.update_yaxes(title_text="units", row=row, col=1)
    figure.update_xaxes(title_text="time (s)", row=len(rows), col=1)
    figure.update_layout(title=title, template="simple_white", hovermode="x unified",
                         height=760)
    return figure
