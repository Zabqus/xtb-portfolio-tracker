"""Wykresy dekompozycji FX: efekt ceny vs efekt waluty."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from core.fx_decomposition import FxDecompositionSummary
from ui.plotly_theme import style_figure

PRICE_COLOR = "#2563EB"
FX_COLOR = "#F59E0B"
TOTAL_COLOR = "#16A34A"
TOTAL_LOSS = "#DC2626"


def build_fx_waterfall_chart(summary: FxDecompositionSummary) -> go.Figure:
    """Wodospad: efekt ceny + efekt FX = PnL."""
    fig = go.Figure()
    if not summary.has_data:
        fig.update_layout(title="Brak danych do dekompozycji FX")
        return style_figure(fig)

    ccy = summary.currency
    values = [summary.price_effect, summary.fx_effect, summary.total_pnl]
    total_color = TOTAL_COLOR if summary.total_pnl >= 0 else TOTAL_LOSS

    fig.add_trace(
        go.Waterfall(
            x=["Z ceny (lokalnie)", "Z waluty (FX)", "PnL łącznie"],
            y=values,
            measure=["relative", "relative", "total"],
            text=[f"{v:+,.0f}" for v in values],
            textposition="outside",
            connector={"line": {"color": "rgba(128,128,128,0.5)"}},
            increasing={"marker": {"color": PRICE_COLOR}},
            decreasing={"marker": {"color": FX_COLOR}},
            totals={"marker": {"color": total_color}},
            hovertemplate="%{x}: %{y:,.2f} " + ccy + "<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Dekompozycja FX — cena vs waluta ({ccy})",
        height=400,
        showlegend=False,
        margin=dict(t=56),
    )
    fig.update_yaxes(title_text=f"Kwota ({ccy})")
    return style_figure(fig)


def build_fx_attribution_bars(
    decomposed: pd.DataFrame,
    currency: str,
    *,
    top_n: int = 15,
) -> go.Figure:
    """Pozycje: poziome słupki składowych PnL (cena vs FX)."""
    fig = go.Figure()
    if decomposed is None or decomposed.empty:
        fig.update_layout(title="Brak pozycji do dekompozycji FX")
        return style_figure(fig)

    label_col = "ticker_xtb" if "ticker_xtb" in decomposed.columns else "ticker_yahoo"
    df = decomposed.dropna(subset=["pnl_price", "pnl_fx"]).copy()
    if df.empty:
        fig.update_layout(title="Brak pozycji do dekompozycji FX")
        return style_figure(fig)

    df["_abs"] = df["pnl_price"].abs() + df["pnl_fx"].abs()
    df = df.sort_values("_abs", ascending=False).head(top_n)
    df = df.iloc[::-1]  # największe na górze w barh

    labels = df[label_col].astype(str).tolist()
    fig.add_trace(
        go.Bar(
            name="Z ceny",
            y=labels,
            x=df["pnl_price"],
            orientation="h",
            marker_color=PRICE_COLOR,
            text=df["pnl_price"].map(lambda v: f"{v:+,.0f}"),
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Z waluty",
            y=labels,
            x=df["pnl_fx"],
            orientation="h",
            marker_color=FX_COLOR,
            text=df["pnl_fx"].map(lambda v: f"{v:+,.0f}"),
            textposition="outside",
        )
    )
    fig.update_layout(
        title=f"Dekompozycja FX per pozycja ({currency})",
        barmode="relative",
        height=max(320, 28 * len(labels) + 100),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(t=72, l=80),
        xaxis_title=f"Kwota ({currency})",
        yaxis_title="",
    )
    return style_figure(fig)
