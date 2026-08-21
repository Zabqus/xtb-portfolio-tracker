"""Wykresy optymalizacji podatkowej (IKE / IKZE vs zwykłe)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui.plotly_theme import style_figure
from ui.theme import accent_color, loss_color, profit_color


def build_ike_ikze_comparison_chart(trajectory: pd.DataFrame, currency: str) -> go.Figure:
    """Trajektoria wartości netto: zwykłe / IKE / IKZE na zadanym horyzoncie."""
    fig = go.Figure()
    if trajectory is None or trajectory.empty:
        return style_figure(fig)

    accent = accent_color()
    profit = profit_color()
    loss = loss_color()

    series = [
        ("taxable_net", f"Zwykłe (netto, Belka)", loss, "dot"),
        ("ike_net", "IKE (netto)", profit, "solid"),
        ("ikze_net", "IKZE (netto + zwroty PIT)", accent, "solid"),
    ]
    for col, name, color, dash in series:
        if col not in trajectory.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=trajectory["year"],
                y=trajectory[col],
                mode="lines",
                name=name,
                line=dict(color=color, width=2.4, dash=dash),
            )
        )

    fig.update_layout(
        title=f"Wartość netto w czasie ({currency})",
        height=420,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Rok")
    fig.update_yaxes(title_text=f"Wartość netto ({currency})")
    return style_figure(fig)


def build_ike_ikze_bars_chart(
    taxable_net: float,
    ike_net: float,
    ikze_net: float,
    currency: str,
) -> go.Figure:
    """Słupki wartości netto na końcu horyzontu."""
    fig = go.Figure()
    labels = ["Zwykłe", "IKE", "IKZE"]
    values = [taxable_net, ike_net, ikze_net]
    colors = [loss_color(), profit_color(), accent_color()]

    fig.add_trace(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:,.0f}" for v in values],
            textposition="outside",
            name=f"Wartość netto ({currency})",
        )
    )
    fig.update_layout(
        title=f"Wartość netto na końcu horyzontu ({currency})",
        height=360,
        showlegend=False,
        margin=dict(t=50, b=40),
        yaxis_title=f"Wartość netto ({currency})",
    )
    return style_figure(fig)
