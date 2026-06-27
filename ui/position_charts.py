"""Wykresy analizy pojedynczej pozycji (Plotly)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui.plotly_theme import reference_line_color, style_figure


def build_price_volume_chart(
    history: pd.DataFrame,
    entry_price: float,
    ticker_label: str,
    period_label: str,
) -> go.Figure:
    """
    Wykres ceny (Close) + wolumen z poziomą linią średniej ceny zakupu.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.72, 0.28],
        subplot_titles=(f"{ticker_label} — cena ({period_label})", "Wolumen"),
    )

    dates = history["Date"]
    close = history["Close"]

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=close,
            name="Cena zamknięcia",
            line=dict(color="#4a9eff", width=2),
            fill="tozeroy",
            fillcolor="rgba(74, 158, 255, 0.12)",
        ),
        row=1,
        col=1,
    )

    fig.add_hline(
        y=entry_price,
        line_dash="dash",
        line_color="#f39c12",
        line_width=2,
        annotation_text=f"Śr. zakup: {entry_price:,.4f}",
        annotation_position="top left",
        annotation_font_color="#f39c12",
        row=1,
        col=1,
    )

    if "Volume" in history.columns:
        colors = [
            "#2ecc71" if history["Close"].iloc[i] >= history["Open"].iloc[i] else "#e74c3c"
            for i in range(len(history))
        ] if "Open" in history.columns else "#6c757d"
        fig.add_trace(
            go.Bar(x=dates, y=history["Volume"], name="Wolumen", marker_color=colors, opacity=0.7),
            row=2,
            col=1,
        )

    fig.update_layout(
        height=560,
        showlegend=False,
        margin=dict(t=60, b=40),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="Cena", row=1, col=1)
    fig.update_yaxes(title_text="Vol.", row=2, col=1)
    return style_figure(fig)


def build_price_drawdown_chart(
    history: pd.DataFrame,
    ticker: str,
    avg_price: float,
    period_label: str,
) -> go.Figure:
    """
    Dwa panele:
    - Górny: cena zamknięcia + linia avg_price (jak obecny wykres)
    - Dolny: drawdown od ATH (running max → % poniżej szczytu)
    """
    dates = history["Date"] if "Date" in history.columns else history.index
    close = history["Close"]
    running_max = close.cummax()
    drawdown_pct = (close - running_max) / running_max * 100  # zawsze ≤ 0

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.03,
    )

    # Cena
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=close,
            name="Cena",
            line=dict(color="#2196F3", width=1.5),
        ),
        row=1,
        col=1,
    )

    # Linia avg_price
    fig.add_hline(
        y=avg_price,
        line_dash="dash",
        line_color="#FF9800",
        annotation_text=f"Twoja śr. cena: {avg_price:.4f}",
        annotation_position="bottom right",
        row=1,
        col=1,
    )

    # Drawdown
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdown_pct,
            fill="tozeroy",
            name="Drawdown od ATH",
            line=dict(color="#e74c3c", width=1),
            fillcolor="rgba(231, 76, 60, 0.2)",
        ),
        row=2,
        col=1,
    )

    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color(), row=2, col=1)

    current_dd = float(drawdown_pct.iloc[-1])
    fig.update_yaxes(title_text="Cena", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
    fig.update_layout(
        title=f"{ticker} — cena i drawdown od ATH ({period_label}) | Aktualny DD: {current_dd:.1f}%",
        height=500,
        showlegend=False,
    )
    return style_figure(fig)


def build_benchmark_overlay_chart(
    merged: pd.DataFrame,
    instrument_name: str,
    benchmark_name: str,
    period_label: str,
) -> go.Figure:
    """Overlay znormalizowanego zwrotu (baza 100) instrument vs indeks."""
    date_col = "date" if "date" in merged.columns else merged.columns[0]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=merged[date_col],
            y=merged["instrument"],
            name=instrument_name,
            line=dict(color="#4a9eff", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=merged[date_col],
            y=merged["benchmark"],
            name=benchmark_name,
            line=dict(color="#e74c3c", width=2, dash="dot"),
        )
    )

    fig.update_layout(
        title=f"Performance vs {benchmark_name} ({period_label}, baza 100)",
        xaxis_title="Data",
        yaxis_title="Zindeksowany zwrot",
        height=420,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.add_hline(y=100, line_dash="dash", line_color=reference_line_color(), opacity=0.5)
    return style_figure(fig)


def build_timing_gauge(percentile: float, label: str) -> go.Figure:
    """Wizualizacja percentyla timingu wejścia."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=percentile,
            number={"suffix": "%", "font": {"size": 36}},
            title={"text": f"Timing wejścia — {label}"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#4a9eff"},
                "steps": [
                    {"range": [0, 25], "color": "rgba(46, 204, 113, 0.35)"},
                    {"range": [25, 75], "color": "rgba(241, 196, 15, 0.25)"},
                    {"range": [75, 100], "color": "rgba(231, 76, 60, 0.35)"},
                ],
                "threshold": {
                    "line": {"color": "#f39c12", "width": 3},
                    "value": percentile,
                },
            },
        )
    )
    fig.update_layout(height=280, margin=dict(t=50, b=20))
    return style_figure(fig)
