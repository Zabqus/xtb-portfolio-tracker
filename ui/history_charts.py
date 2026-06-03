"""Wykresy strony Historia."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_portfolio_timeline_chart(
    timeline: pd.DataFrame,
    currency: str,
) -> go.Figure:
    """Wykres liniowy wartości portfela i bazy kosztowej w czasie."""
    df = timeline.dropna(subset=["date"]).copy()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if "market_value" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["market_value"],
                name=f"Wartość rynkowa ({currency})",
                line=dict(color="#4a9eff", width=2),
                fill="tozeroy",
                fillcolor="rgba(74, 158, 255, 0.1)",
            ),
            secondary_y=False,
        )

    if "cost_basis" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["cost_basis"],
                name=f"Baza kosztowa ({currency})",
                line=dict(color="#f39c12", width=2, dash="dash"),
            ),
            secondary_y=False,
        )

    if "position_count" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["position_count"],
                name="Liczba pozycji",
                marker_color="rgba(108, 117, 125, 0.35)",
                opacity=0.6,
            ),
            secondary_y=True,
        )

    fig.update_layout(
        title=f"Timeline portfela ({currency})",
        height=480,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text=f"Wartość ({currency})", secondary_y=False)
    fig.update_yaxes(title_text="Pozycje", secondary_y=True, showgrid=False)
    return fig


def build_cumulative_realized_pnl(closed: pd.DataFrame, currency: str) -> go.Figure:
    """Skumulowany zrealizowany PnL z zamkniętych pozycji."""
    if closed is None or closed.empty or "close_time" not in closed.columns:
        fig = go.Figure()
        fig.update_layout(title="Brak danych zamkniętych pozycji")
        return fig

    df = closed.dropna(subset=["close_time", "pnl"]).sort_values("close_time").copy()
    df["cumulative_pnl"] = df["pnl"].cumsum()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["close_time"],
            y=df["cumulative_pnl"],
            mode="lines+markers",
            name="Skumulowany PnL",
            line=dict(color="#2ecc71", width=2),
            fill="tozeroy",
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=f"Skumulowany zrealizowany PnL ({currency})",
        xaxis_title="Data zamknięcia",
        yaxis_title=f"PnL ({currency})",
        height=380,
    )
    return fig
