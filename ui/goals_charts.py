"""Wykresy strony Cele: trajektoria do celu i dividend snowball."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui.plotly_theme import reference_line_color, style_figure
from ui.theme import accent_color, muted_text_color, profit_color


def build_goal_trajectory_chart(
    trajectory: pd.DataFrame,
    target_value: float,
    currency: str,
) -> go.Figure:
    """Projekcja wartości portfela vs wpłacony kapitał, z linią celu."""
    fig = go.Figure()
    if trajectory is None or trajectory.empty:
        return style_figure(fig)

    accent = accent_color()
    profit = profit_color()

    fig.add_trace(
        go.Scatter(
            x=trajectory["date"],
            y=trajectory["value"],
            mode="lines",
            name=f"Wartość portfela ({currency})",
            line=dict(color=accent, width=2.4),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.08)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trajectory["date"],
            y=trajectory["invested"],
            mode="lines",
            name=f"Wpłacony kapitał ({currency})",
            line=dict(color=profit, width=2, dash="dash"),
        )
    )
    if target_value > 0:
        fig.add_hline(
            y=target_value,
            line_dash="dot",
            line_color=reference_line_color(),
            annotation_text=f"Cel: {target_value:,.0f} {currency}",
            annotation_position="top left",
        )
    fig.update_layout(
        title="Droga do celu (procent składany + dopłaty)",
        height=420,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Rok")
    fig.update_yaxes(title_text=f"Wartość ({currency})")
    return style_figure(fig)


def build_snowball_chart(snowball: pd.DataFrame, currency: str) -> go.Figure:
    """Roczny dochód z dywidend vs wydatki — moment przecięcia = FIRE z dywidend."""
    fig = go.Figure()
    if snowball is None or snowball.empty:
        return style_figure(fig)

    profit = profit_color()
    fig.add_trace(
        go.Bar(
            x=snowball["year"],
            y=snowball["dividends"],
            name=f"Dochód z dywidend ({currency}/rok)",
            marker_color=profit,
            opacity=0.85,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=snowball["year"],
            y=snowball["expenses"],
            mode="lines",
            name=f"Roczne wydatki ({currency})",
            line=dict(color="#F59E0B", width=2.4, dash="dash"),
        )
    )
    fig.update_layout(
        title="Dividend snowball — kiedy dywidendy pokryją wydatki",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=56),
        barmode="overlay",
    )
    fig.update_xaxes(title_text="Rok od dziś")
    fig.update_yaxes(title_text=f"Kwota ({currency}/rok)")
    return style_figure(fig)
