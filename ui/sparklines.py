"""Mini-wykresy trendu (sparkline) dla metryk KPI."""

from __future__ import annotations

import plotly.graph_objects as go

from ui.theme import loss_color, profit_color


def build_sparkline(values: list[float], *, height: int = 48) -> go.Figure | None:
    """Prosty wykres liniowy bez osi — kolor zależny od trendu."""
    if not values or len(values) < 2:
        return None

    color = profit_color() if values[-1] >= values[0] else loss_color()
    fig = go.Figure(
        data=[
            go.Scatter(
                x=list(range(len(values))),
                y=values,
                mode="lines",
                line=dict(color=color, width=2),
                hoverinfo="skip",
            )
        ]
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0, pad=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        showlegend=False,
    )
    return fig


def sparkline_trend_pct(values: list[float]) -> float | None:
    """Zmiana % między pierwszym a ostatnim punktem sparkline."""
    if not values or len(values) < 2 or values[0] == 0:
        return None
    return (values[-1] / values[0] - 1.0) * 100.0
