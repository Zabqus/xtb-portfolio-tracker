"""Wykresy alokacji sektorowej i geograficznej."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

REGION_COLORS = {
    "USA": "#3498db",
    "EU": "#2ecc71",
    "PL": "#e74c3c",
    "Inne": "#95a5a6",
}


def build_breakdown_pie(
    breakdown: pd.DataFrame,
    label_col: str,
    currency: str,
    title: str,
    color_map: dict[str, str] | None = None,
) -> go.Figure:
    """Wykres kołowy udziału wartości portfela wg kolumny grupującej."""
    if breakdown.empty:
        fig = go.Figure()
        fig.update_layout(title=title, height=440)
        return fig

    chart = breakdown.copy()
    chart["label"] = chart[label_col].astype(str)

    fig = px.pie(
        chart,
        names="label",
        values="market_value",
        title=f"{title} ({currency})",
        hole=0.38,
        color="label" if color_map else None,
        color_discrete_map=color_map if color_map else None,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="%{label}<br>%{value:,.2f} %{customdata}<extra></extra>",
        customdata=[currency] * len(chart),
    )
    fig.update_layout(showlegend=True, height=440, margin=dict(t=50, b=20))
    return fig


def build_breakdown_bar(
    breakdown: pd.DataFrame,
    label_col: str,
    currency: str,
    title: str,
    color_map: dict[str, str] | None = None,
) -> go.Figure:
    """Wykres słupkowy poziomy — alternatywa do koła przy wielu kategoriach."""
    if breakdown.empty:
        fig = go.Figure()
        fig.update_layout(title=title, height=400)
        return fig

    chart = breakdown.sort_values("weight_pct", ascending=True)
    colors = [
        color_map.get(str(row[label_col]), "#7f8c8d") if color_map else "#4a9eff"
        for _, row in chart.iterrows()
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                y=chart[label_col].astype(str),
                x=chart["weight_pct"],
                orientation="h",
                marker_color=colors,
                text=[f"{v:.1f}%" for v in chart["weight_pct"]],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=title,
        xaxis_title="Udział (%)",
        yaxis_title="",
        height=max(320, 40 * len(chart)),
    )
    return fig
