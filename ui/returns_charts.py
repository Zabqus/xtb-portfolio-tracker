"""Wykresy strony Zwroty: krzywa TWR, portfel vs benchmark, snapshoty."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

ACCENT = "#2563EB"
PROFIT = "#16A34A"
BENCH = "#F59E0B"


def build_twr_index_chart(twr_index: pd.DataFrame) -> go.Figure:
    """Krzywa wzrostu portfela (TWR) – 100 = start okresu."""
    fig = go.Figure()
    if twr_index is None or twr_index.empty:
        fig.update_layout(title="Brak danych do krzywej TWR")
        return fig

    df = twr_index.dropna(subset=["date", "twr_index"]).copy()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["twr_index"],
            mode="lines",
            name="Portfel (TWR)",
            line=dict(color=ACCENT, width=2),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.08)",
        )
    )
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    fig.update_layout(
        title="Krzywa wzrostu portfela (TWR, start = 100)",
        height=380,
        hovermode="x unified",
        margin=dict(t=56),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Indeks (100 = start)")
    return fig


def build_portfolio_vs_benchmark_chart(
    merged: pd.DataFrame,
    benchmark_name: str,
) -> go.Figure:
    """Porównanie indeksu TWR portfela z benchmarkiem (oba rebazowane do 100)."""
    fig = go.Figure()
    if merged is None or merged.empty:
        fig.update_layout(title="Brak danych do porównania z benchmarkiem")
        return fig

    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["portfolio"],
            mode="lines",
            name="Portfel (TWR)",
            line=dict(color=ACCENT, width=2.4),
        )
    )
    if "benchmark" in merged.columns:
        fig.add_trace(
            go.Scatter(
                x=merged["date"],
                y=merged["benchmark"],
                mode="lines",
                name=benchmark_name,
                line=dict(color=BENCH, width=2, dash="dot"),
            )
        )
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=f"Portfel vs {benchmark_name} (100 = start, oba znormalizowane)",
        height=430,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Indeks (100 = start)")
    return fig


def build_snapshots_chart(snapshots: pd.DataFrame, currency: str) -> go.Figure:
    """Wartość i koszt portfela z zapisanych snapshotów."""
    fig = go.Figure()
    if snapshots is None or snapshots.empty:
        fig.update_layout(title="Brak zapisanych snapshotów")
        return fig

    df = snapshots.sort_values("date").copy()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["total_value"],
            mode="lines+markers",
            name=f"Wartość ({currency})",
            line=dict(color=PROFIT, width=2),
            fill="tozeroy",
            fillcolor="rgba(22, 163, 74, 0.10)",
        )
    )
    if "total_cost" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["total_cost"],
                mode="lines+markers",
                name=f"Koszt ({currency})",
                line=dict(color=BENCH, width=2, dash="dash"),
            )
        )
    fig.update_layout(
        title=f"Wartość portfela ze snapshotów ({currency})",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=56),
    )
    fig.update_xaxes(title_text="Data snapshotu")
    fig.update_yaxes(title_text=f"Wartość ({currency})")
    return fig
