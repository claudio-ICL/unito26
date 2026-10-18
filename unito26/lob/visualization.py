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
two placements read a :class:`unito26.lob.coupling.CoupledPlacements`.
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
    "coupled_mid_figure",
    "coupled_touch_figure",
    "coupled_path_figure",
    "coupled_book_figure",
    "coupled_depth_figure",
    "discrepancy_survival_figure",
    "discrepancy_survival_panels",
    "agreement_figure",
    "distance_terms_figure",
    "fan_panels_figure",
    "discrepancy_figure",
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


# ---- two placements of one flow ---------------------------------------------------

#: Which placement a trace is about: one colour each in every figure of a pair, and the
#: dash as a second encoding, so that the two books stay apart where their lines coincide.
IDEALISED_COLOUR = PALETTE[2]
GEOMETRIC_COLOUR = PALETTE[4]
IDEALISED_DASH = "dot"
GEOMETRIC_DASH = "solid"
PLACEMENT_STYLE = {
    "Idealised": dict(color=IDEALISED_COLOUR, dash=IDEALISED_DASH),
    "Geometric": dict(color=GEOMETRIC_COLOUR, dash=GEOMETRIC_DASH),
}


def _first_discrepancy_line(figure, pair, annotated: bool, **where) -> None:
    """A vertical rule at the first event after which the books differ, if there is one."""
    time = pair.first_discrepancy_time
    if time is None:
        return
    label = dict(annotation_text="first discrepancy χ<sup>≠</sup>", annotation_font_color=INK,
                 annotation_position="top right") if annotated else {}
    figure.add_vline(x=time, line=dict(color=INK, width=1, dash="dash"), **label, **where)


def _placement_steps(times, values, placement: str, **kwargs):
    style = PLACEMENT_STYLE[placement]
    return _steps(
        times, values, placement.lower(), style["color"],
        line=dict(color=style["color"], width=2.5, dash=style["dash"]), **kwargs,
    )


def coupled_mid_figure(pair):
    """The mid-price of both books over time, and beneath it the geometric minus the
    idealised one, which is zero until the first discrepancy."""
    from plotly.subplots import make_subplots

    frame = pair.frame
    times = frame["TimeStamp"]
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.65, 0.35],
        subplot_titles=("Mid-price P<sup>m</sup>", "P<sup>m,geo</sup> − P<sup>m,id</sup>"),
    )
    for placement in PLACEMENT_STYLE:
        figure.add_trace(
            _placement_steps(times, frame[f"{placement}MidPrice"], placement), row=1, col=1
        )
    difference = frame["GeometricMidPrice"] - frame["IdealisedMidPrice"]
    figure.add_trace(
        _steps(times, difference, "difference", INK, line=dict(color=INK, width=1.5),
               showlegend=False),
        row=2, col=1,
    )
    _first_discrepancy_line(figure, pair, True, row=1, col=1)
    _first_discrepancy_line(figure, pair, False, row=2, col=1)
    figure.update_layout(
        title="The mid-price under the two placements", template="simple_white",
        hovermode="x unified", height=560, legend=dict(orientation="h", y=1.08, x=0),
    )
    figure.update_yaxes(title_text="ticks", row=1, col=1)
    figure.update_yaxes(title_text="ticks", row=2, col=1)
    figure.update_xaxes(title_text="time (s)", row=2, col=1)
    return figure


def coupled_touch_figure(pair):
    """The size at each touch of both books over time, the bid above and the ask below."""
    from plotly.subplots import make_subplots

    frame = pair.frame
    times = frame["TimeStamp"]
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, shared_yaxes="all", vertical_spacing=0.08,
        subplot_titles=("Size at the best bid S<sup>b</sup>", "Size at the best ask S<sup>a</sup>"),
    )
    for row, side in enumerate(("Bid", "Ask"), start=1):
        for placement in PLACEMENT_STYLE:
            figure.add_trace(
                _placement_steps(
                    times, frame[f"{placement}{side}Size1"], placement, showlegend=row == 1
                ),
                row=row, col=1,
            )
        figure.update_yaxes(title_text="shares", rangemode="tozero", row=row, col=1)
        _first_discrepancy_line(figure, pair, row == 1, row=row, col=1)
    figure.update_layout(
        title="The touches under the two placements", template="simple_white",
        hovermode="x unified", height=560, legend=dict(orientation="h", y=1.08, x=0),
    )
    figure.update_xaxes(title_text="time (s)", row=2, col=1)
    return figure


def coupled_path_figure(pair, title: str = ""):
    """The mid-price and the two touches of both books, on one time axis.

    Until the first discrepancy the books are equal and each geometric line hides its
    idealised one; the rule marks where they part.
    """
    from plotly.subplots import make_subplots

    frame = pair.frame
    times = frame["TimeStamp"]
    rows = {
        "MidPrice": "Mid-price P<sup>m</sup> (ticks)",
        "BidSize1": "Size at the best bid S<sup>b</sup> (shares)",
        "AskSize1": "Size at the best ask S<sup>a</sup> (shares)",
    }
    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
        row_heights=[0.4, 0.3, 0.3], subplot_titles=tuple(rows.values()),
    )
    for row, column in enumerate(rows, start=1):
        for placement in PLACEMENT_STYLE:
            figure.add_trace(
                _placement_steps(
                    times, frame[f"{placement}{column}"], placement, showlegend=row == 1
                ),
                row=row, col=1,
            )
        _first_discrepancy_line(figure, pair, row == 1, row=row, col=1)
    figure.update_yaxes(tickformat=".1f", row=1, col=1)
    figure.update_yaxes(rangemode="tozero", row=2, col=1)
    figure.update_yaxes(rangemode="tozero", row=3, col=1)
    figure.update_xaxes(title_text="time (s)", row=3, col=1)
    figure.update_layout(
        title=title, template="simple_white", hovermode="x unified", height=700,
        legend=dict(orientation="h", y=1.07, x=0),
    )
    return figure


def coupled_book_figure(pair, event: int, depth: int, title: str = ""):
    """Both books after ``event``, side by side on one price axis, ``depth`` levels a side."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    depths = {"Idealised": pair.idealised_depth, "Geometric": pair.geometric_depth}
    figure = make_subplots(
        rows=1, cols=2, shared_yaxes=True, shared_xaxes=True, horizontal_spacing=0.05,
        subplot_titles=tuple(f"{placement}, after event {event}" for placement in depths),
    )
    for column, depth_frame in enumerate(depths.values(), start=1):
        row = depth_frame.loc[event]
        bids = row[row > 0].sort_index(ascending=False).head(depth)
        asks = (-row[row < 0]).sort_index().head(depth)
        for name, side, colour in (("bid", bids, BID_COLOUR), ("ask", asks, ASK_COLOUR)):
            figure.add_trace(
                go.Bar(
                    x=side.to_numpy(), y=side.index.to_numpy(), orientation="h", name=name,
                    marker=dict(color=colour, line=dict(color=SURFACE, width=2)),
                    showlegend=column == 1,
                    hovertemplate="%{y}: %{x} shares<extra>" + name + "</extra>",
                ),
                row=1, col=column,
            )
        figure.update_xaxes(title_text="size (shares)", row=1, col=column)
    figure.update_yaxes(title_text="price (ticks)", dtick=1, row=1, col=1)
    figure.update_layout(
        title=title, template="simple_white", barmode="overlay", bargap=0.15, height=460,
        legend=dict(orientation="h", y=1.1, x=0),
    )
    return figure


#: Bid size positive, ask size negative, on the two side colours about a neutral zero.
DEPTH_SCALE = [[0.0, ASK_COLOUR], [0.5, "#f0efea"], [1.0, BID_COLOUR]]


def coupled_depth_figure(pair):
    """The whole of both books over time, as heatmaps side by side on one price axis.

    A cell is the size resting at a price in ticks after an event, positive on the bid and
    negative on the ask, so the boundary between the colours is the spread.  The two
    panels share one colour scale.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    depths = {"Idealised": pair.idealised_depth, "Geometric": pair.geometric_depth}
    prices = sorted(set(pair.idealised_depth.columns) | set(pair.geometric_depth.columns))
    top = max(float(np.abs(depth.to_numpy()).max(initial=0.0)) for depth in depths.values())
    times = pair.frame["TimeStamp"].to_numpy()
    figure = make_subplots(
        rows=1, cols=2, shared_yaxes=True, shared_xaxes=True, horizontal_spacing=0.04,
        subplot_titles=tuple(depths),
    )
    for column, depth in enumerate(depths.values(), start=1):
        z = depth.reindex(columns=prices, fill_value=0.0).to_numpy(dtype=float).T
        figure.add_trace(
            go.Heatmap(
                x=times, y=prices, z=z, zmin=-top, zmax=top, zmid=0.0,
                colorscale=DEPTH_SCALE, showscale=column == 2,
                colorbar=dict(title="size", tickfont=dict(color=MUTED)),
                hovertemplate="%{x:.3f} s, %{y}: %{z}<extra></extra>",
            ),
            row=1, col=column,
        )
        figure.update_xaxes(title_text="time (s)", row=1, col=column)
        _first_discrepancy_line(figure, pair, column == 1, row=1, col=column)
    figure.update_yaxes(title_text="price (ticks)", row=1, col=1)
    figure.update_layout(
        title="The book under the two placements", template="simple_white", height=520
    )
    return figure


def discrepancy_survival_figure(times, horizon: float, theoretical=None):
    """The fraction of paths whose books have not yet differed, against time.

    ``times`` holds the first discrepancy time of each path, NaN for a path whose books
    never differed by ``horizon``.  Every path is followed to the same horizon, so the
    curve is the plain empirical survival function on ``[0, horizon]``.  ``theoretical``,
    when given, is ``(t, S(t))`` and is drawn as a line.
    """
    import numpy as np
    import plotly.graph_objects as go

    times = np.asarray(times, dtype=float)
    observed = np.sort(times[np.isfinite(times)])
    paths = times.size
    figure = go.Figure(
        _steps(
            np.r_[0.0, observed, horizon],
            np.r_[1.0, 1.0 - np.arange(1, observed.size + 1) / paths,
                  1.0 - observed.size / paths],
            "empirical", GEOMETRIC_COLOUR,
            hovertemplate="%{x:.3f} s: %{y:.3f}<extra>empirical</extra>",
        )
    )
    if theoretical is not None:
        grid, survival = theoretical
        figure.add_trace(
            go.Scatter(
                x=grid, y=survival, mode="lines", name="theoretical",
                line=dict(color=INK, width=1.5, dash="dot"),
            )
        )
    figure.update_layout(
        title=f"Survival of the first discrepancy, {paths} paths", template="simple_white",
        height=420, xaxis_title="time (s)", yaxis_title="fraction not yet differed",
        yaxis_range=[0, 1.02], legend=dict(orientation="h", y=1.08, x=0),
    )
    return figure


#: The curves set against the coupled runs, in the order they are given: ink first.
FORMULA_LINES = (
    dict(color=INK, width=2, dash="dot"),
    dict(color=MUTED, width=2, dash="dash"),
    dict(color=MUTED, width=1.5, dash="dashdot"),
)


def discrepancy_survival_panels(times: dict, clock, theoretical: dict, title: str = ""):
    """The survival of the first discrepancy in a grid of panels, on a logarithmic time axis.

    ``times[row][column]`` holds the first discrepancy time of each path of one experiment,
    NaN where the books had not differed by the end of ``clock``; its empirical survival
    is drawn as steps in the geometric colour.  ``theoretical[row][column]`` maps a name to
    a curve on ``clock``, drawn in the styles of ``FORMULA_LINES`` by position, one legend
    entry a name.
    """
    import numpy as np
    import plotly.graph_objects as go
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
            sample = np.asarray(times[row][column], dtype=float)
            parted = np.sort(sample[np.isfinite(sample)])
            survival = 1.0 - np.searchsorted(parted, clock, side="right") / sample.size
            figure.add_trace(
                _steps(clock, survival, "coupled runs", GEOMETRIC_COLOUR,
                       line=dict(color=GEOMETRIC_COLOUR, width=2.5),
                       showlegend="coupled runs" not in shown, legendgroup="coupled runs",
                       hovertemplate="%{x:.3f} s: %{y:.3f}<extra>coupled runs</extra>"),
                row=r, col=c,
            )
            shown.add("coupled runs")
            for slot, (name, curve) in enumerate(theoretical[row][column].items()):
                figure.add_trace(
                    go.Scatter(
                        x=clock, y=curve, mode="lines", name=name, legendgroup=name,
                        line=FORMULA_LINES[slot], showlegend=name not in shown,
                        hovertemplate="%{x:.3f} s: %{y:.3f}<extra>" + name + "</extra>",
                    ),
                    row=r, col=c,
                )
                shown.add(name)
    figure.update_xaxes(type="log", range=[np.log10(clock[0]), np.log10(clock[-1])],
                        dtick=1)
    for c in range(1, len(column_labels) + 1):
        figure.update_xaxes(title_text="time (s)", row=len(row_labels), col=c)
    for r in range(1, len(row_labels) + 1):
        figure.update_yaxes(title_text="P(χ<sup>≠</sup> > t)", row=r, col=1)
    figure.update_yaxes(range=[0, 1.04])
    figure.update_layout(
        title=title, template="simple_white", height=300 * len(row_labels) + 160,
        legend=dict(orientation="h", y=-0.3 / len(row_labels), x=0), hovermode="x unified",
    )
    return figure


def agreement_figure(tables: dict, title: str = ""):
    """The frequency of agreement at a limit event against ``eta (1 - eta)^zeta*``, one panel per
    ``DepthDecay``.

    ``tables`` maps a depth decay to :func:`unito26.lob.coupling.agreement_by_case`.  A case
    is a marker at its target offset, a circle when the touch of the order's side held less
    than ``Sbar`` and a diamond when it was full, with two standard errors either side.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from unito26.lob.coupling import agreement_probability

    figure = make_subplots(
        rows=1, cols=len(tables), shared_yaxes=True, horizontal_spacing=0.04,
        subplot_titles=[f"η = {decay:g}" for decay in tables],
    )
    for column, (decay, table) in enumerate(tables.items(), start=1):
        offsets = np.arange(-1, int(table["TargetOffset"].max()) + 1)
        figure.add_trace(
            go.Scatter(
                x=offsets, y=agreement_probability(offsets, decay), mode="lines+markers",
                name="η(1−η)<sup>ζ*</sup>", showlegend=column == 1,
                line=dict(color=INK, width=1.5, dash="dot"),
                marker=dict(color=INK, size=9, symbol="line-ew-open", line=dict(width=2)),
                hovertemplate="ζ* = %{x}: %{y:.3f}<extra>η(1−η)^ζ*</extra>",
            ),
            row=1, col=column,
        )
        for full, symbol, label in ((False, "circle", "touch below S̄"),
                                    (True, "diamond", "touch at S̄")):
            cases = table[table.index.get_level_values("TouchFull") == full]
            figure.add_trace(
                go.Scatter(
                    x=cases["TargetOffset"], y=cases["Agreed"], mode="markers",
                    name=f"coupled runs, {label}", showlegend=column == 1,
                    marker=dict(color=GEOMETRIC_COLOUR, size=11, symbol=symbol,
                                line=dict(color=SURFACE, width=2)),
                    error_y=dict(type="data", array=2 * cases["StandardError"],
                                 color=GEOMETRIC_COLOUR, thickness=1.5, width=4),
                    customdata=np.c_[cases.index.get_level_values("Spread"),
                                     cases["LimitEvents"]],
                    hovertemplate="spread %{customdata[0]} ticks, %{customdata[1]} events: "
                                  "%{y:.3f}<extra></extra>",
                ),
                row=1, col=column,
            )
        figure.update_xaxes(title_text="target offset ζ*", dtick=1, row=1, col=column)
    figure.update_yaxes(title_text="frequency of agreement", range=[-0.03, 1.03], row=1, col=1)
    figure.update_layout(
        title=title, template="simple_white", height=440,
        legend=dict(orientation="h", y=-0.2, x=0),
    )
    return figure


def distance_terms_figure(terms, title: str = ""):
    """The distance ``2 Sbar (P^m_geometric - P^m_idealised)`` after each event, and the
    three terms it is the sum of, signed as they enter, on one time axis and one scale.

    ``terms`` is :func:`unito26.lob.coupling.distance_terms`.
    """
    from plotly.subplots import make_subplots

    rows = {
        "2S̄ (P<sup>m,geo</sup> − P<sup>m,id</sup>)": terms["Distance"],
        "(a) OFI<sup>geo</sup> − OFI<sup>id</sup>": terms["ImbalanceMismatch"],
        "−(b) the best sizes, geometric less idealised": -terms["TouchSizeMismatch"],
        "−(c) the outer sizes of the geometric moves, less S̄ a tick": -terms["DepthMismatch"],
    }
    figure = make_subplots(
        rows=len(rows), cols=1, shared_xaxes=True, shared_yaxes="all", vertical_spacing=0.06,
        subplot_titles=tuple(rows),
    )
    for row, (name, values) in enumerate(rows.items(), start=1):
        colour = GEOMETRIC_COLOUR if row == 1 else INK
        figure.add_trace(
            _steps(terms["TimeStamp"], values, name, colour,
                   line=dict(color=colour, width=2 if row == 1 else 1.5), showlegend=False),
            row=row, col=1,
        )
        figure.add_hline(y=0, line=dict(color=AXIS, width=1), row=row, col=1)
        figure.update_yaxes(title_text="shares", row=row, col=1)
    figure.update_xaxes(title_text="time (s)", row=len(rows), col=1)
    figure.update_layout(title=title, template="simple_white", hovermode="x unified",
                         height=760)
    return figure


def fan_panels_figure(
    paths: dict, clock, curves: dict, shown: int, y_title: str, shared_yaxes, title: str = ""
):
    """A fan of paths in a grid of panels, with summary curves over it.

    ``paths[row][column]`` is an array with a row per path and a column per time of
    ``clock``; its first ``shown`` rows are drawn as thin lines.  ``curves[row][column]``
    maps a name to a curve on ``clock``, the first drawn in the geometric colour and the
    others in the styles of ``FORMULA_LINES``, one legend entry a name.  ``shared_yaxes`` is
    plotly's: True within a row, ``"all"`` across the grid, False for none.
    """
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    row_labels = list(paths)
    column_labels = list(next(iter(paths.values())))
    figure = make_subplots(
        rows=len(row_labels), cols=len(column_labels), shared_xaxes=True,
        shared_yaxes=shared_yaxes, horizontal_spacing=0.025 if shared_yaxes else 0.06,
        vertical_spacing=0.1,
        subplot_titles=[f"{row}, {column}" for row in row_labels for column in column_labels],
    )
    legend = set()
    for r, row in enumerate(row_labels, start=1):
        for c, column in enumerate(column_labels, start=1):
            sample = np.asarray(paths[row][column], dtype=float)
            for k, path in enumerate(sample[:shown]):
                figure.add_trace(
                    go.Scatter(
                        x=clock, y=path, mode="lines", name="a path", legendgroup="a path",
                        line=dict(color=AXIS, width=1), hoverinfo="skip",
                        showlegend=k == 0 and "a path" not in legend,
                    ),
                    row=r, col=c,
                )
            legend.add("a path")
            for slot, (name, curve) in enumerate(curves[row][column].items()):
                line = (dict(color=GEOMETRIC_COLOUR, width=2.5) if slot == 0
                        else FORMULA_LINES[slot - 1])
                figure.add_trace(
                    go.Scatter(
                        x=clock, y=curve, mode="lines", name=name, legendgroup=name,
                        line=line, showlegend=name not in legend,
                        hovertemplate="%{x:.0f} s: %{y:.2f}<extra>" + name + "</extra>",
                    ),
                    row=r, col=c,
                )
                legend.add(name)
    for c in range(1, len(column_labels) + 1):
        figure.update_xaxes(title_text="time (s)", row=len(row_labels), col=c)
    for r in range(1, len(row_labels) + 1):
        figure.update_yaxes(title_text=y_title, row=r, col=1)
    figure.update_layout(
        title=title, template="simple_white", height=320 * len(row_labels) + 160,
        legend=dict(orientation="h", y=-0.3 / len(row_labels), x=0),
    )
    return figure


def discrepancy_figure(discrepancies: dict, title: str = ""):
    """A measure of how far the two books lie apart, against ``DepthDecay``.

    ``discrepancies`` maps a label -- a size law, say -- to a series indexed by the depth
    decay.  One line per label, the colour by slot.
    """
    import plotly.graph_objects as go

    figure = go.Figure()
    for slot, (label, series) in enumerate(discrepancies.items()):
        colour = PALETTE[slot % len(PALETTE)]
        figure.add_trace(
            go.Scatter(
                x=series.index, y=series.to_numpy(), name=label, mode="lines+markers",
                line=dict(color=colour, width=2), marker=dict(color=colour, size=8),
                hovertemplate="DepthDecay %{x}: %{y:.4g}<extra>" + label + "</extra>",
            )
        )
    figure.update_layout(
        title=title, template="simple_white", height=420,
        xaxis_title="DepthDecay", legend=dict(orientation="h", y=1.08, x=0),
    )
    return figure
