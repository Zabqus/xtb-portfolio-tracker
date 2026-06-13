"""Wykresy Plotly dla dashboardu."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_allocation_pie(df: pd.DataFrame, currency: str) -> go.Figure:
    """Wykres kołowy – udział procentowy pozycji w wartości portfela."""
    chart_df = df.dropna(subset=["market_value"]).copy()
    label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"

    fig = px.pie(
        chart_df,
        names=label_col,
        values="market_value",
        title=f"Struktura portfela (% wartości, {currency})",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(showlegend=True, height=450)
    return fig


def build_portfolio_treemap(df: pd.DataFrame, currency: str) -> go.Figure:
    """
    Treemap: rozmiar kafla = wartość rynkowa, kolor = ROI%.
    Używa px.treemap z color_continuous_scale diverging (czerwony–żółty–zielony).
    """
    chart_df = df.dropna(subset=["market_value", "roi_pct"]).copy()
    label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"

    fig = px.treemap(
        chart_df,
        path=[label_col],
        values="market_value",
        color="roi_pct",
        color_continuous_scale="RdYlGn",  # czerwony → żółty → zielony
        color_continuous_midpoint=0,
        custom_data=["pnl", "market_price", "avg_price", "roi_pct"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[3]:.1f}%",
        hovertemplate=(
            "<b>%{label}</b><br>"
            f"Wartość: %{{value:,.2f}} {currency}<br>"
            "ROI: %{customdata[3]:.2f}%<br>"
            "PnL: %{customdata[0]:,.2f}<br>"
            "Cena rynk.: %{customdata[1]:,.2f}<br>"
            "Śr. cena: %{customdata[2]:,.2f}<extra></extra>"
        ),
    )
    fig.update_layout(
        title=f"Mapa portfela — rozmiar = wartość, kolor = ROI% ({currency})",
        height=420,
        margin=dict(t=40, l=0, r=0, b=0),
        coloraxis_colorbar=dict(title="ROI %"),
    )
    return fig


def build_pnl_bar_chart(df: pd.DataFrame, currency: str) -> go.Figure:
    """Wykres słupkowy – zysk/strata na poszczególnych aktywach."""
    chart_df = df.dropna(subset=["pnl"]).copy()
    label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in chart_df["pnl"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=chart_df[label_col],
                y=chart_df["pnl"],
                marker_color=colors,
                text=chart_df["pnl"].round(2),
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=f"Zysk / strata na pozycjach ({currency})",
        xaxis_title="Instrument",
        yaxis_title=f"Zysk / strata ({currency})",
        height=450,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig


def build_closed_pnl_chart(closed: pd.DataFrame, currency: str) -> go.Figure:
    """Wykres słupkowy PnL zamkniętych pozycji."""
    chart_df = closed.dropna(subset=["pnl", "ticker_xtb"]).copy()
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in chart_df["pnl"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=chart_df["ticker_xtb"],
                y=chart_df["pnl"],
                marker_color=colors,
                text=chart_df["pnl"].round(2),
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=f"Zrealizowany PnL – zamknięte pozycje ({currency})",
        xaxis_title="Instrument",
        yaxis_title=f"Profit/Loss ({currency})",
        height=450,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig
