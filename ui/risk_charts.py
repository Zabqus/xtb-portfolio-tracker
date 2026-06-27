"""Wykresy metryk ryzyka — korelacja, koncentracja, rolling risk, mapa pozycji."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.concentration import ConcentrationMetrics
from ui.plotly_theme import heatmap_color_scale, reference_line_color, style_figure

ACCENT = "#2563EB"
LOSS = "#DC2626"
PROFIT = "#16A34A"


def build_correlation_heatmap(corr: pd.DataFrame) -> go.Figure:
    """Heatmap korelacji: niebieski (−1) → biały (0) → czerwony (+1)."""
    if corr is None or corr.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do macierzy korelacji")
        return style_figure(fig)

    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale=heatmap_color_scale(),
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    fig.update_layout(
        title="Macierz korelacji dziennych zwrotów",
        height=max(380, 60 * len(corr.columns)),
        margin=dict(t=60),
    )
    fig.update_xaxes(side="bottom")
    return style_figure(fig, heatmap=True)


def build_concentration_chart(
    metrics: ConcentrationMetrics,
    history: pd.DataFrame | None = None,
) -> go.Figure:
    """Słupki Top-N wag + linia HHI w czasie (gdy są snapshoty)."""
    if metrics.top_weights.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do wykresu koncentracji")
        return style_figure(fig)

    has_history = history is not None and not history.empty and "hhi" in history.columns
    rows = 2 if has_history else 1
    row_heights = [0.55, 0.45] if has_history else [1.0]
    specs: list = [[{}]]
    if has_history:
        specs.append([{"secondary_y": True}])

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.12,
        row_heights=row_heights,
        specs=specs,
        subplot_titles=(
            [f"Top {len(metrics.top_weights)} pozycji (% portfela)"]
            + (["HHI i Top-5 w czasie (snapshoty)"] if has_history else [])
        ),
    )

    tw = metrics.top_weights.copy()
    colors = [PROFIT if i < 5 else ACCENT for i in range(len(tw))]
    fig.add_trace(
        go.Bar(
            x=tw["ticker"],
            y=tw["weight_pct"],
            marker_color=colors,
            text=[f"{v:.1f}%" for v in tw["weight_pct"]],
            textposition="outside",
            name="Udział %",
        ),
        row=1,
        col=1,
    )

    if has_history:
        hist = history.sort_values("date")
        fig.add_trace(
            go.Scatter(
                x=hist["date"],
                y=hist["hhi"] * 100,
                mode="lines+markers",
                name="HHI (×100)",
                line=dict(color=LOSS, width=2),
            ),
            row=2,
            col=1,
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=hist["date"],
                y=hist["top5_pct"],
                mode="lines+markers",
                name="Top-5 %",
                line=dict(color=ACCENT, width=2, dash="dot"),
            ),
            row=2,
            col=1,
            secondary_y=True,
        )

    hhi_label = f"{metrics.hhi * 100:.0f}" if metrics.hhi < 1 else f"{metrics.hhi:.2f}"
    fig.update_layout(
        title=(
            f"Koncentracja portfela — Top-5 = {metrics.top5_pct:.1f}% · "
            f"HHI = {hhi_label} · efektywne N ≈ {metrics.effective_n:.1f}"
        ),
        height=520 if has_history else 380,
        showlegend=has_history,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=80),
    )
    fig.update_yaxes(title_text="Udział %", row=1, col=1)
    if has_history:
        fig.update_yaxes(title_text="HHI (×100)", row=2, col=1, secondary_y=False)
        fig.update_yaxes(title_text="Top-5 %", row=2, col=1, secondary_y=True, showgrid=False)
    return style_figure(fig)


def build_rolling_risk_chart(rolling: pd.DataFrame) -> go.Figure:
    """Linie: rolling vol 30/60/90d, Sharpe i max drawdown."""
    if rolling is None or rolling.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do rolling risk metrics")
        return style_figure(fig)

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.34, 0.33, 0.33],
        subplot_titles=(
            "Zmienność roczna (rolling)",
            "Sharpe ratio (rolling)",
            "Max drawdown w oknie (rolling)",
        ),
    )

    vol_colors = {"30": "#2563EB", "60": "#7C3AED", "90": "#DB2777"}
    for col in rolling.columns:
        if col.startswith("vol_"):
            days = col.replace("vol_", "").replace("d", "")
            fig.add_trace(
                go.Scatter(
                    x=rolling["date"],
                    y=rolling[col],
                    mode="lines",
                    name=f"Vol {days}d",
                    line=dict(color=vol_colors.get(days, ACCENT), width=1.5),
                ),
                row=1,
                col=1,
            )
        elif col.startswith("sharpe_"):
            days = col.replace("sharpe_", "").replace("d", "")
            fig.add_trace(
                go.Scatter(
                    x=rolling["date"],
                    y=rolling[col],
                    mode="lines",
                    name=f"Sharpe {days}d",
                    line=dict(color=vol_colors.get(days, ACCENT), width=1.5),
                    showlegend=False,
                ),
                row=2,
                col=1,
            )
        elif col.startswith("max_dd_"):
            days = col.replace("max_dd_", "").replace("d", "")
            fig.add_trace(
                go.Scatter(
                    x=rolling["date"],
                    y=rolling[col],
                    mode="lines",
                    name=f"Max DD {days}d",
                    line=dict(color=vol_colors.get(days, LOSS), width=1.5),
                    showlegend=False,
                ),
                row=3,
                col=1,
            )

    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color(), row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color(), row=3, col=1)
    fig.update_layout(
        title="Rolling risk metrics (30 / 60 / 90 dni)",
        height=620,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=80),
    )
    fig.update_yaxes(title_text="Vol %", row=1, col=1)
    fig.update_yaxes(title_text="Sharpe", row=2, col=1)
    fig.update_yaxes(title_text="Max DD %", row=3, col=1)
    return style_figure(fig)


def build_position_risk_bubble(
    risk_df: pd.DataFrame,
    currency: str,
) -> go.Figure:
    """Bubble: X=waga%, Y=ROI%, rozmiar=vol 90d, kolor=sektor."""
    if risk_df is None or risk_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do mapy ryzyka pozycji")
        return style_figure(fig)

    df = risk_df.dropna(subset=["weight_pct", "roi_pct"]).copy()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do mapy ryzyka pozycji")
        return style_figure(fig)

    df["vol_90d_pct"] = df["vol_90d_pct"].fillna(df["vol_90d_pct"].median())
    df["size_scaled"] = df["vol_90d_pct"].clip(lower=5)

    fig = px.scatter(
        df,
        x="weight_pct",
        y="roi_pct",
        size="size_scaled",
        color="sector",
        hover_name="ticker",
        custom_data=["vol_90d_pct", "market_value"],
        labels={
            "weight_pct": "Waga w portfelu (%)",
            "roi_pct": "ROI (%)",
            "sector": "Sektor",
        },
        title=f"Mapa ryzyka pozycji ({currency})",
    )
    fig.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Waga: %{x:.1f}%<br>"
            "ROI: %{y:.1f}%<br>"
            "Vol 90d: %{customdata[0]:.1f}%<br>"
            f"Wartość: %{{customdata[1]:,.0f}} {currency}<extra></extra>"
        ),
        marker=dict(opacity=0.75, line=dict(width=1, color="rgba(255,255,255,0.4)")),
    )
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color())
    fig.add_vline(x=0, line_dash="dash", line_color=reference_line_color(), opacity=0.3)
    fig.update_layout(
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=56),
    )
    fig.update_xaxes(title_text="Waga w portfelu (%)")
    fig.update_yaxes(title_text="ROI (%)")
    return style_figure(fig)
