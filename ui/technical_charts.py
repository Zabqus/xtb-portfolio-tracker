"""Wykresy analizy technicznej (Plotly)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.technicals import (
    COL_BB_LOWER,
    COL_BB_MID,
    COL_BB_UPPER,
    COL_MA20,
    COL_MA50,
    COL_MA200,
    COL_MACD,
    COL_MACD_HIST,
    COL_MACD_SIGNAL,
    COL_RSI,
)


def build_price_ma_rsi_chart(
    df: pd.DataFrame,
    ticker: str,
    entry_price: float | None = None,
) -> go.Figure:
    """
    Wykres łączony: cena + MA (overlay, górny panel) + RSI(14) (dolny subplot).
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
        subplot_titles=(f"{ticker} — cena i średnie kroczące", "RSI(14)"),
    )

    # --- Panel 1: Close + MA ---
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["Close"],
            name="Close",
            line=dict(color="#4a9eff", width=2),
        ),
        row=1,
        col=1,
    )

    ma_styles = [
        (COL_MA20, "#f39c12", "MA20"),
        (COL_MA50, "#9b59b6", "MA50"),
        (COL_MA200, "#e74c3c", "MA200"),
    ]
    for col, color, label in ma_styles:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df[col],
                    name=label,
                    line=dict(color=color, width=1.5, dash="dot"),
                ),
                row=1,
                col=1,
            )

    if entry_price is not None and entry_price > 0:
        fig.add_hline(
            y=entry_price,
            line_dash="dash",
            line_color="#f39c12",
            line_width=1.5,
            annotation_text=f"Śr. zakup: {entry_price:,.4f}",
            annotation_position="top left",
            row=1,
            col=1,
        )

    # --- Panel 2: RSI ---
    if COL_RSI in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[COL_RSI],
                name="RSI(14)",
                line=dict(color="#4a9eff", width=2),
                fill="tozeroy",
                fillcolor="rgba(74, 158, 255, 0.1)",
            ),
            row=2,
            col=1,
        )

    fig.add_hline(y=70, line_dash="dash", line_color="#e74c3c", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#2ecc71", row=2, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor="gray", opacity=0.06, line_width=0, row=2, col=1)

    fig.update_layout(
        height=620,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=0),
        margin=dict(t=80, b=40),
        showlegend=True,
    )
    fig.update_yaxes(title_text="Cena", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_xaxes(title_text="Data", row=2, col=1)
    return fig


def build_ma_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Cena zamknięcia + MA20 / MA50 / MA200."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["Close"],
            name="Close",
            line=dict(color="#4a9eff", width=2),
        )
    )
    ma_styles = [
        (COL_MA20, "#f39c12", "MA20"),
        (COL_MA50, "#9b59b6", "MA50"),
        (COL_MA200, "#e74c3c", "MA200"),
    ]
    for col, color, label in ma_styles:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=df[col],
                    name=label,
                    line=dict(color=color, width=1.5, dash="dot"),
                )
            )
    fig.update_layout(
        title=f"Średnie kroczące — {ticker}",
        xaxis_title="Data",
        yaxis_title="Cena",
        height=440,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    return fig


def build_rsi_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """RSI(14) z poziomami 30 / 70."""
    fig = go.Figure()
    if COL_RSI in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[COL_RSI],
                name="RSI(14)",
                line=dict(color="#4a9eff", width=2),
                fill="tozeroy",
                fillcolor="rgba(74, 158, 255, 0.08)",
            )
        )
    fig.add_hline(y=70, line_dash="dash", line_color="#e74c3c", annotation_text="70")
    fig.add_hline(y=30, line_dash="dash", line_color="#2ecc71", annotation_text="30")
    fig.add_hrect(y0=30, y1=70, fillcolor="gray", opacity=0.05, line_width=0)
    fig.update_layout(
        title=f"RSI(14) — {ticker}",
        xaxis_title="Data",
        yaxis_title="RSI",
        yaxis=dict(range=[0, 100]),
        height=320,
        hovermode="x unified",
    )
    return fig


def build_macd_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """MACD, sygnał i histogram."""
    fig = make_subplots(specs=[[{"secondary_y": False}]])

    if COL_MACD in df.columns:
        fig.add_trace(
            go.Scatter(x=df["Date"], y=df[COL_MACD], name="MACD", line=dict(color="#4a9eff", width=2))
        )
    if COL_MACD_SIGNAL in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[COL_MACD_SIGNAL],
                name="Sygnał",
                line=dict(color="#f39c12", width=1.5),
            )
        )
    if COL_MACD_HIST in df.columns:
        colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in df[COL_MACD_HIST].fillna(0)]
        fig.add_trace(
            go.Bar(x=df["Date"], y=df[COL_MACD_HIST], name="Histogram", marker_color=colors, opacity=0.6)
        )

    fig.update_layout(
        title=f"MACD (12, 26, 9) — {ticker}",
        xaxis_title="Data",
        height=360,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12),
        barmode="overlay",
    )
    return fig


def build_bollinger_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Bollinger Bands (20, 2) + cena."""
    fig = go.Figure()

    if COL_BB_UPPER in df.columns and COL_BB_LOWER in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[COL_BB_UPPER],
                name="Górna BB",
                line=dict(color="rgba(231, 76, 60, 0.5)", width=1),
                showlegend=True,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[COL_BB_LOWER],
                name="Dolna BB",
                line=dict(color="rgba(46, 204, 113, 0.5)", width=1),
                fill="tonexty",
                fillcolor="rgba(128, 128, 128, 0.12)",
            )
        )

    if COL_BB_MID in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Date"],
                y=df[COL_BB_MID],
                name="Środek (SMA20)",
                line=dict(color="#9b59b6", width=1, dash="dash"),
            )
        )

    fig.add_trace(
        go.Scatter(
            x=df["Date"],
            y=df["Close"],
            name="Close",
            line=dict(color="#4a9eff", width=2),
        )
    )

    fig.update_layout(
        title=f"Bollinger Bands (20, 2σ) — {ticker}",
        xaxis_title="Data",
        yaxis_title="Cena",
        height=440,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    return fig
