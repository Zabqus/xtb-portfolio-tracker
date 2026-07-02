"""Wykresy konsensusu analityków — upside ladder, scatter, rozkład, target fan, bullet."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.analyst_consensus import rating_color
from ui.plotly_theme import reference_line_color, style_figure

BUCKET_COLORS = {
    "Kupno": "#2ecc71",
    "Trzymaj": "#f39c12",
    "Sprzedaj": "#e74c3c",
}

QUADRANT_LABELS = {
    "tl": "Analitycy optymistyczni,\nTy w zysku",
    "tr": "Analitycy optymistyczni,\nTy w stracie",
    "bl": "Analitycy pesymistyczni,\nTy w zysku",
    "br": "Analitycy pesymistyczni,\nTy w stracie",
}


def build_upside_ladder(df: pd.DataFrame, currency: str) -> go.Figure:
    """Poziome słupki upside % posortowane; kolor = rating; opacity = waga portfela."""
    chart = df.dropna(subset=["Upside %", "weight_pct"]).copy()
    if chart.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do wykresu upside ladder")
        return style_figure(fig)

    chart = chart.sort_values("Upside %", ascending=True)
    max_w = float(chart["weight_pct"].max()) or 1.0
    opacities = (0.35 + 0.65 * (chart["weight_pct"] / max_w)).clip(0.35, 1.0)
    colors = [rating_color(k) for k in chart["_rating_key"]]

    fig = go.Figure(
        go.Bar(
            x=chart["Upside %"],
            y=chart["Ticker"],
            orientation="h",
            marker=dict(color=colors, opacity=opacities),
            text=[
                f"{u:+.1f}% · {w:.1f}% portf."
                for u, w in zip(chart["Upside %"], chart["weight_pct"])
            ],
            textposition="outside",
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Upside: %{x:+.1f}%<br>"
                "Waga: %{customdata[0]:.1f}%<br>"
                "Weighted upside: %{customdata[1]:+.2f} pp<extra></extra>"
            ),
            customdata=list(
                zip(chart["weight_pct"], chart.get("weighted_upside", chart["Upside %"] * chart["weight_pct"] / 100))
            ),
        )
    )
    weighted_total = chart.get("weighted_upside", chart["Upside %"] * chart["weight_pct"] / 100).sum()
    fig.add_vline(x=0, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title=f"Upside ladder — wagowy upside portfela: {weighted_total:+.1f} pp ({currency})",
        xaxis_title="Upside % do śr. celu analityków",
        yaxis_title="",
        height=max(320, 44 * len(chart)),
        margin=dict(l=80, r=40, t=56),
    )
    return style_figure(fig)


def build_pnl_vs_consensus_scatter(df: pd.DataFrame, currency: str) -> go.Figure:
    """Scatter: X = upside %, Y = Twój ROI %; rozmiar = waga portfela."""
    chart = df.dropna(subset=["Upside %", "Twój P&L %", "weight_pct"]).copy()
    if chart.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do scatter P&L vs konsensus")
        return style_figure(fig)

    chart["size_scaled"] = chart["weight_pct"].clip(lower=1) * 3

    fig = px.scatter(
        chart,
        x="Upside %",
        y="Twój P&L %",
        size="size_scaled",
        color="Rating",
        hover_name="Ticker",
        color_discrete_map="set2",
        labels={"Upside %": "Upside do celu (%)", "Twój P&L %": "Twój ROI (%)"},
        title=f"Twój P&L vs konsensus analityków ({currency})",
    )
    fig.update_traces(
        marker=dict(opacity=0.8, line=dict(width=1, color="rgba(255,255,255,0.35)")),
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Upside: %{x:+.1f}%<br>"
            "ROI: %{y:+.1f}%<extra></extra>"
        ),
    )

    x_mid = 0.0
    y_mid = 0.0
    x_range = chart["Upside %"]
    y_range = chart["Twój P&L %"]
    x_pad = max(5.0, (x_range.max() - x_range.min()) * 0.08)
    y_pad = max(5.0, (y_range.max() - y_range.min()) * 0.08)
    x0, x1 = float(x_range.min()) - x_pad, float(x_range.max()) + x_pad
    y0, y1 = float(y_range.min()) - y_pad, float(y_range.max()) + y_pad

    fig.add_hline(y=y_mid, line_dash="dash", line_color=reference_line_color())
    fig.add_vline(x=x_mid, line_dash="dash", line_color=reference_line_color())

    annotations = [
        (x0 + (x_mid - x0) * 0.5, y1 - y_pad * 0.3, "tl"),
        (x_mid + (x1 - x_mid) * 0.5, y1 - y_pad * 0.3, "tr"),
        (x0 + (x_mid - x0) * 0.5, y0 + y_pad * 0.3, "bl"),
        (x_mid + (x1 - x_mid) * 0.5, y0 + y_pad * 0.3, "br"),
    ]
    for ax, ay, key in annotations:
        fig.add_annotation(
            x=ax,
            y=ay,
            text=QUADRANT_LABELS[key],
            showarrow=False,
            font=dict(size=10, color=reference_line_color()),
            opacity=0.75,
        )

    fig.update_layout(height=480, margin=dict(t=56))
    fig.update_xaxes(range=[x0, x1])
    fig.update_yaxes(range=[y0, y1])
    return style_figure(fig)


def build_rating_distribution_chart(
    current: dict[str, float],
    previous: dict[str, float] | None = None,
) -> go.Figure:
    """Stacked bar: udział wagowy portfela wg ratingu (bieżący vs poprzedni snapshot)."""
    if not current:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do rozkładu rekomendacji")
        return style_figure(fig)

    order = ["Kupno", "Trzymaj", "Sprzedaj"]
    periods = ["Teraz"]
    if previous:
        periods.append("Poprzedni snapshot")

    fig = go.Figure()
    for bucket in order:
        y_vals = [current.get(bucket, 0.0)]
        if previous:
            y_vals.append(previous.get(bucket, 0.0))
        fig.add_trace(
            go.Bar(
                name=bucket,
                x=periods,
                y=y_vals,
                marker_color=BUCKET_COLORS.get(bucket, "#94a3b8"),
                text=[f"{v:.1f}%" if v > 0 else "" for v in y_vals],
                textposition="inside",
            )
        )

    fig.update_layout(
        barmode="stack",
        title="Rozkład rekomendacji (% wartości portfela, wagowo)",
        yaxis_title="Udział %",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=72),
    )
    return style_figure(fig)


def build_target_price_fan(
    *,
    ticker: str,
    current_price: float | None,
    avg_price: float | None,
    target_mean: float | None,
    target_low: float | None,
    target_high: float | None,
    currency: str,
) -> go.Figure:
    """Range forecast: cena bieżąca, cel średni, low/high target, śr. cena zakupu."""
    fig = go.Figure()
    prices = [p for p in (current_price, avg_price, target_mean, target_low, target_high) if p is not None]
    if not prices:
        fig.update_layout(title=f"Brak danych cenowych dla {ticker}")
        return style_figure(fig)

    y_min = min(prices) * 0.95
    y_max = max(prices) * 1.05

    if target_low is not None and target_high is not None:
        fig.add_trace(
            go.Bar(
                x=[ticker],
                y=[target_high - target_low],
                base=[target_low],
                marker_color="rgba(46, 204, 113, 0.25)",
                name="Zakres celów (low–high)",
                hovertemplate=(
                    f"Low: {target_low:.2f}<br>High: {target_high:.2f}<extra></extra>"
                ),
                width=0.35,
            )
        )

    markers = []
    if current_price is not None:
        markers.append(("Cena rynkowa", current_price, "#2563EB", "circle"))
    if avg_price is not None:
        markers.append(("Śr. cena zakupu", avg_price, "#f39c12", "diamond"))
    if target_mean is not None:
        markers.append(("Śr. cel analityków", target_mean, "#2ecc71", "square"))

    for label, price, color, symbol in markers:
        fig.add_trace(
            go.Scatter(
                x=[ticker],
                y=[price],
                mode="markers+text",
                name=label,
                marker=dict(size=14, color=color, symbol=symbol, line=dict(width=2, color="white")),
                text=[f"{price:.2f}"],
                textposition="top center",
                hovertemplate=f"{label}: %{{y:.2f}} {currency}<extra></extra>",
            )
        )

    fig.update_layout(
        title=f"Target price fan — {ticker}",
        yaxis_title=f"Cena ({currency})",
        height=420,
        barmode="overlay",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=72),
    )
    fig.update_yaxes(range=[y_min, y_max])
    return style_figure(fig)


def build_signal_radar(
    *,
    ticker: str,
    technical_score: float,
    consensus_score: float,
    pl_score: float,
) -> go.Figure:
    """Radar składników sygnału 40/40/20 (skala 0–4 / 0–2)."""
    categories = ["Technika (0–4)", "Konsensus (0–4)", "P&L (0–2)"]
    values = [technical_score, consensus_score, pl_score]
    max_vals = [4.0, 4.0, 2.0]
    normalized = [v / m * 100 if m > 0 else 0 for v, m in zip(values, max_vals)]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=normalized + [normalized[0]],
            theta=categories + [categories[0]],
            fill="toself",
            name=ticker,
            line=dict(color="#2563EB"),
            fillcolor="rgba(37, 99, 235, 0.2)",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")),
        title=f"Składniki sygnału — {ticker}",
        height=380,
        showlegend=False,
        margin=dict(t=56),
    )
    return style_figure(fig)


def build_tech_vs_consensus_bubble(df: pd.DataFrame, currency: str) -> go.Figure:
    """Bubble: technika vs konsensus; rozmiar = waga portfela."""
    chart = df.dropna(subset=["technical_score", "consensus_score", "weight_pct"]).copy()
    if chart.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do mapy technika vs konsensus")
        return style_figure(fig)

    chart["size_scaled"] = chart["weight_pct"].clip(lower=1) * 4
    fig = px.scatter(
        chart,
        x="consensus_score",
        y="technical_score",
        size="size_scaled",
        color="Rating",
        hover_name="Ticker",
        labels={
            "consensus_score": "Wynik konsensusu (0–4)",
            "technical_score": "Wynik techniki (0–4)",
        },
        title=f"Mapa analityk vs technika ({currency})",
    )
    fig.update_traces(
        marker=dict(opacity=0.78, line=dict(width=1, color="rgba(255,255,255,0.35)")),
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Konsensus: %{x:.1f}<br>"
            "Technika: %{y:.1f}<br>"
            "Waga: %{customdata[0]:.1f}%<extra></extra>"
        ),
        customdata=chart[["weight_pct"]],
    )
    fig.add_hline(y=2.0, line_dash="dot", line_color=reference_line_color(), opacity=0.5)
    fig.add_vline(x=2.0, line_dash="dot", line_color=reference_line_color(), opacity=0.5)
    fig.update_layout(height=460, margin=dict(t=56))
    return style_figure(fig)


def build_consensus_bullet_chart(df: pd.DataFrame, currency: str) -> go.Figure:
    """
    Bullet chart: zakres 52W, markery — cena rynkowa, śr. zakupu, cel analityków.
    """
    chart = df.dropna(subset=["Cena"]).copy()
    if chart.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do bullet chart")
        return style_figure(fig)

    chart = chart.sort_values("Upside %", ascending=False, na_position="last")
    tickers = chart["Ticker"].tolist()
    n = len(tickers)

    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=tickers,
    )

    for i, (_, row) in enumerate(chart.iterrows(), start=1):
        low = row.get("week_52_low")
        high = row.get("week_52_high")
        price = row.get("Cena")
        avg = row.get("avg_price")
        target = row.get("Cel")

        refs = [p for p in (low, high, price, avg, target) if p is not None and not pd.isna(p)]
        if not refs:
            continue
        x_min = min(refs) * 0.92
        x_max = max(refs) * 1.08

        if low is not None and high is not None and not pd.isna(low) and not pd.isna(high):
            fig.add_trace(
                go.Bar(
                    x=[high - low],
                    y=[0],
                    base=[low],
                    orientation="h",
                    marker_color="rgba(148, 163, 184, 0.35)",
                    showlegend=False,
                    hovertemplate=f"52W: {low:.2f} – {high:.2f}<extra></extra>",
                    width=0.5,
                ),
                row=i,
                col=1,
            )

        point_specs = [
            (price, "#2563EB", "Cena", "circle"),
            (avg, "#f39c12", "Zakup", "diamond"),
            (target, "#2ecc71", "Cel", "square"),
        ]
        for val, color, label, symbol in point_specs:
            if val is None or pd.isna(val):
                continue
            fig.add_trace(
                go.Scatter(
                    x=[val],
                    y=[0],
                    mode="markers",
                    marker=dict(size=11, color=color, symbol=symbol, line=dict(width=1.5, color="white")),
                    name=label if i == 1 else None,
                    showlegend=i == 1,
                    hovertemplate=f"{label}: %{{x:.2f}} {currency}<extra></extra>",
                ),
                row=i,
                col=1,
            )

        fig.update_xaxes(range=[x_min, x_max], row=i, col=1, showticklabels=(i == n))
        fig.update_yaxes(visible=False, row=i, col=1)

    fig.update_layout(
        title=f"Bullet chart — cel analityków vs Twoja cena vs rynek ({currency})",
        height=max(360, 72 * n),
        barmode="overlay",
        margin=dict(t=64, l=40, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.01),
    )
    return style_figure(fig)
