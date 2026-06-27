"""Wykresy alokacji sektorowej i geograficznej."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ui.plotly_theme import style_figure

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
        return style_figure(fig)

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
    return style_figure(fig)


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
        return style_figure(fig)

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
    return style_figure(fig)


def build_rebalance_chart(rebalance: pd.DataFrame, group_col: str) -> go.Figure:
    """Grupowany słupek: bieżący udział vs docelowy dla każdego koszyka."""
    fig = go.Figure()
    if rebalance is None or rebalance.empty:
        fig.update_layout(title="Brak danych do rebalansu", height=360)
        return style_figure(fig)

    chart = rebalance.copy()
    labels = chart[group_col].astype(str)
    fig.add_trace(
        go.Bar(
            x=labels, y=chart["current_pct"], name="Obecnie",
            marker_color="#94A3B8",
            text=[f"{v:.0f}%" for v in chart["current_pct"]], textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels, y=chart["target_pct"], name="Cel",
            marker_color="#2563EB",
            text=[f"{v:.0f}%" for v in chart["target_pct"]], textposition="outside",
        )
    )
    fig.update_layout(
        title="Alokacja: obecna vs docelowa",
        barmode="group",
        height=400,
        yaxis_title="Udział (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=56),
    )
    return style_figure(fig)
