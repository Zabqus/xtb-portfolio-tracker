"""Wykres wodospadowy P&L portfela."""

from __future__ import annotations

import plotly.graph_objects as go

from core.pnl_breakdown import PnLBreakdown
from ui.plotly_theme import style_figure


def build_pnl_waterfall_chart(breakdown: PnLBreakdown) -> go.Figure:
    """Waterfall: niezrealizowany + zrealizowany + dywidendy − podatek = wynik."""
    fig = go.Figure()
    if not breakdown.has_data:
        fig.update_layout(title="Brak danych do wykresu wodospadowego P&L")
        return style_figure(fig)

    ccy = breakdown.currency
    measures = ["relative", "relative", "relative", "relative", "total"]
    labels = [
        "Niezrealizowany P&L",
        "Zrealizowany P&L",
        "Dywidendy",
        "Podatek (szac.)",
        "Całkowity wynik",
    ]
    values = [
        breakdown.unrealized_pnl,
        breakdown.realized_pnl,
        breakdown.dividends,
        -breakdown.estimated_tax,
        breakdown.total_result,
    ]

    fig.add_trace(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measures,
            text=[f"{v:+,.0f}" for v in values],
            textposition="outside",
            connector={"line": {"color": "rgba(128,128,128,0.5)"}},
            increasing={"marker": {"color": "#16A34A"}},
            decreasing={"marker": {"color": "#DC2626"}},
            totals={"marker": {"color": "#2563EB"}},
        )
    )
    fig.update_layout(
        title=f"Wodospad P&L portfela ({ccy})",
        height=420,
        showlegend=False,
        margin=dict(t=56),
    )
    fig.update_yaxes(title_text=f"Kwota ({ccy})")
    return style_figure(fig)
