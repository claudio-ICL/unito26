"""Drawing a book and a session: as text for the documentation, as plotly elsewhere.

The text ladder goes into markdown and into the lecture notes, where it must survive
version control and be readable in a diff.  The plotly figures are for a notebook, where
a level can be hovered and read.

Two conventions hold for every time series here.  The lines are **steps**
(``line_shape="hv"``): the book holds each state until the next message, so a sloped
segment would draw a state the book never had.  And a padded level is plotted as NaN
with ``connectgaps=False``, so the line breaks where the side had no such level; drawn
literally, the sentinel price would take the axis to 10^10.

The book figures go through ``levels_map`` and know nothing about how a book stores its
levels; the session figures read the LOBSTER frame and its statistics.
"""

from __future__ import annotations

from unito26.lob.messages import BUY, SELL, MessageType, is_market_price
from unito26.lob.orderbook import AggregateBook

__all__ = [
    "ascii_ladder",
    "describe_message",
    "book_figure",
    "example_figure",
    "depth_figure",
    "level_evolution_figure",
    "touch_figure",
    "gap_figure",
    "imbalance_figure",
    "coverage_figure",
    "band_width_figure",
]

#: The first four slots of the categorical palette, in order.  A side keeps its colour
#: in every figure, so the mapping is learned once; the panels are told apart by their
#: axes rather than by their palette.
BID_COLOUR = "#2a78d6"
ASK_COLOUR = "#eb6834"
MID_COLOUR = "#1baf7a"
MICRO_COLOUR = "#eda100"


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
    empty levels of section 8's case B visible at a glance.
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
        title=f"{example.name} &mdash; {describe_message(example.message)}",
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
