"""Wykresy trade analytics i cost basis."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ui.plotly_theme import reference_line_color, style_figure


def build_cost_basis_chart(history: pd.DataFrame, ticker_xtb: str) -> go.Figure:
    """Linia średniej ceny zakupu + markery transakcji BUY/SELL."""
    df = history[history["ticker_xtb"] == ticker_xtb].copy()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"Brak danych dla {ticker_xtb}")
        return style_figure(fig)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["trade_time"],
            y=df["avg_price_after"],
            mode="lines+markers",
            name="Średnia cena (po transakcji)",
            line=dict(color="#4a9eff", width=2),
        )
    )

    buys = df[df["event"] == "BUY"]
    sells = df[df["event"] == "SELL"]

    if not buys.empty:
        fig.add_trace(
            go.Scatter(
                x=buys["trade_time"],
                y=buys["trade_price"],
                mode="markers",
                name="Kupno",
                marker=dict(symbol="triangle-up", size=12, color="#2ecc71"),
                text=buys["trade_qty"].round(4),
            )
        )
    if not sells.empty:
        fig.add_trace(
            go.Scatter(
                x=sells["trade_time"],
                y=sells["trade_price"],
                mode="markers",
                name="Sprzedaż",
                marker=dict(symbol="triangle-down", size=12, color="#e74c3c"),
                text=sells["trade_qty"].round(4),
            )
        )

    fig.update_layout(
        title=f"Cost basis — {ticker_xtb}",
        xaxis_title="Data",
        yaxis_title="Cena",
        height=420,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    return style_figure(fig)


def build_holding_period_chart(round_trips: pd.DataFrame) -> go.Figure:
    """Histogram czasu trzymania pozycji (dni)."""
    if round_trips.empty or "holding_days" not in round_trips.columns:
        fig = go.Figure()
        fig.update_layout(title="Brak danych o czasie trzymania")
        return style_figure(fig)

    fig = px.histogram(
        round_trips,
        x="holding_days",
        color="is_win",
        color_discrete_map={True: "#2ecc71", False: "#e74c3c"},
        labels={"holding_days": "Dni trzymania", "is_win": "Wynik"},
        title="Rozkład czasu trzymania pozycji",
        nbins=20,
    )
    fig.update_layout(height=380, barmode="overlay")
    return style_figure(fig)


def build_win_loss_comparison(avg_win: float, avg_loss: float, currency: str) -> go.Figure:
    """Słupki: średni zysk vs średnia strata."""
    fig = go.Figure(
        data=[
            go.Bar(
                x=["Średni zysk", "Średnia strata"],
                y=[avg_win, abs(avg_loss)],
                marker_color=["#2ecc71", "#e74c3c"],
                text=[f"{avg_win:,.2f}", f"{abs(avg_loss):,.2f}"],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=f"Średni zysk vs średnia strata ({currency})",
        yaxis_title=currency,
        height=360,
    )
    return style_figure(fig)


def build_round_trip_pnl_chart(round_trips: pd.DataFrame) -> go.Figure:
    """PnL per zamknięty round-trip (trafione vs nietrafione)."""
    if round_trips.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak round-tripów")
        return style_figure(fig)

    df = round_trips.sort_values("close_time").copy()
    colors = ["#2ecc71" if w else "#e74c3c" for w in df["is_win"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["ticker_xtb"] + " " + df["close_time"].dt.strftime("%Y-%m-%d"),
                y=df["realized_pnl"],
                marker_color=colors,
                text=df["realized_pnl"].round(2),
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title="Zrealizowany PnL — round-tripy (FIFO)",
        xaxis_title="Transakcja",
        yaxis_title="PnL",
        height=400,
    )
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color())
    return style_figure(fig)
