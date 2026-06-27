"""Wykresy strony Watchlist."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui.plotly_theme import reference_line_color, style_figure


def build_vs_portfolio_bar(
    table: pd.DataFrame,
    period_label: str,
    portfolio_return: float | None,
) -> go.Figure:
    """Słupki: zwrot watchlisty vs linia referencyjna portfela."""
    col = f"return_{period_label}"
    chart = table.dropna(subset=[col]).copy()
    if chart.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych zwrotu", height=400)
        return style_figure(fig)

    colors = [
        "#3498db" if not row.get("in_portfolio") else "#95a5a6"
        for _, row in chart.iterrows()
    ]

    fig = go.Figure(
        data=[
            go.Bar(
                x=chart["symbol"],
                y=chart[col],
                marker_color=colors,
                text=[f"{v:+.1f}%" for v in chart[col]],
                textposition="outside",
                name="Watchlist",
            )
        ]
    )
    if portfolio_return is not None:
        fig.add_hline(
            y=portfolio_return,
            line_dash="dash",
            line_color="#e67e22",
            line_width=2,
            annotation_text=f"Portfel (ważony): {portfolio_return:+.2f}%",
            annotation_position="top right",
            annotation_font_color="#e67e22",
        )
    fig.add_hline(y=0, line_dash="dot", line_color=reference_line_color())
    fig.update_layout(
        title=f"Zwrot {period_label} — watchlist vs portfel",
        xaxis_title="Symbol",
        yaxis_title="Zwrot (%)",
        height=450,
        showlegend=False,
    )
    return style_figure(fig)


def build_normalized_lines_chart(
    comparison: pd.DataFrame,
    period_label: str,
) -> go.Figure:
    """Linie znormalizowanego performance (100 = start)."""
    fig = go.Figure()
    if comparison.empty or "date" not in comparison.columns:
        fig.update_layout(title="Brak wspólnych sesji do porównania", height=420)
        return style_figure(fig)

    palette = {
        "portfel (śr.)": "#e67e22",
        "watchlista (śr.)": "#3498db",
    }
    for col in comparison.columns:
        if col == "date":
            continue
        fig.add_trace(
            go.Scatter(
                x=comparison["date"],
                y=comparison[col],
                name=col,
                line=dict(width=2.5, color=palette.get(col, "#9b59b6")),
            )
        )

    fig.update_layout(
        title=f"Performance znormalizowane (baza 100, {period_label})",
        xaxis_title="Data",
        yaxis_title="Indeks (100 = start okresu)",
        height=460,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.add_hline(y=100, line_dash="dot", line_color=reference_line_color(), opacity=0.5)
    return style_figure(fig)
