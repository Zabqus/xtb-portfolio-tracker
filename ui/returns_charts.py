"""Wykresy strony Zwroty: krzywa TWR, portfel vs benchmark, snapshoty, drawdown, beta."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui.plotly_theme import heatmap_color_scale, reference_line_color, style_figure

ACCENT = "#2563EB"
PROFIT = "#16A34A"
BENCH = "#F59E0B"
LOSS = "#DC2626"

BENCH_COLORS = ["#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899", "#64748B"]
BENCH_DASHES = ["dot", "dash", "dashdot", "longdash", "solid"]


def _build_equity_drawdown_panels(
    dates: pd.Series,
    values: pd.Series,
    *,
    value_name: str,
    value_title: str,
    y_title: str,
    chart_title: str,
    height: int = 480,
) -> go.Figure:
    """Dwa panele: krzywa wartości + underwater drawdown (%)."""
    running_max = values.cummax()
    drawdown = (values - running_max) / running_max * 100

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.03,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines",
            name=value_name,
            line=dict(color=ACCENT, width=2),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.08)",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=drawdown,
            fill="tozeroy",
            name="Drawdown",
            line=dict(color=LOSS, width=1),
            fillcolor="rgba(220, 38, 38, 0.2)",
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color(), row=2, col=1)
    current_dd = float(drawdown.iloc[-1]) if len(drawdown) else 0.0
    fig.update_layout(
        title=f"{chart_title} | Aktualny DD: {current_dd:.1f}%",
        height=height,
        showlegend=False,
        hovermode="x unified",
        margin=dict(t=60),
    )
    fig.update_yaxes(title_text=y_title, row=1, col=1)
    fig.update_yaxes(title_text="Drawdown %", row=2, col=1)
    fig.update_xaxes(title_text="Data", row=2, col=1)
    return style_figure(fig)


def build_twr_index_chart(twr_index: pd.DataFrame) -> go.Figure:
    """Krzywa wzrostu portfela (TWR) – 100 = start okresu."""
    fig = go.Figure()
    if twr_index is None or twr_index.empty:
        fig.update_layout(title="Brak danych do krzywej TWR")
        return style_figure(fig)

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
    fig.add_hline(y=100, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title="Krzywa wzrostu portfela (TWR, start = 100)",
        height=380,
        hovermode="x unified",
        margin=dict(t=56),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Indeks (100 = start)")
    return style_figure(fig)


def build_twr_with_drawdown_chart(twr_index: pd.DataFrame) -> go.Figure:
    """Krzywa TWR + panel drawdownu (underwater)."""
    if twr_index is None or twr_index.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do krzywej TWR z drawdownem")
        return style_figure(fig)

    df = twr_index.dropna(subset=["date", "twr_index"]).copy()
    return _build_equity_drawdown_panels(
        df["date"],
        df["twr_index"],
        value_name="Portfel (TWR)",
        value_title="Indeks TWR",
        y_title="Indeks (100 = start)",
        chart_title="Krzywa TWR + drawdown (start = 100)",
    )


def build_portfolio_value_drawdown_chart(
    timeline: pd.DataFrame,
    currency: str,
) -> go.Figure:
    """Wartość rynkowa portfela + panel drawdownu."""
    if timeline is None or timeline.empty or "market_value" not in timeline.columns:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do wykresu wartości z drawdownem")
        return style_figure(fig)

    df = timeline.dropna(subset=["date", "market_value"]).copy()
    df = df[df["market_value"] > 0]
    return _build_equity_drawdown_panels(
        df["date"],
        df["market_value"],
        value_name=f"Wartość ({currency})",
        value_title="Wartość rynkowa",
        y_title=f"Wartość ({currency})",
        chart_title=f"Wartość portfela + drawdown ({currency})",
        height=500,
    )


def build_benchmark_risk_chart(
    risk_series: pd.DataFrame,
    benchmark_name: str,
) -> go.Figure:
    """Rolling beta, tracking error i information ratio vs benchmark."""
    if risk_series is None or risk_series.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do beta / tracking error")
        return style_figure(fig)

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.34, 0.33, 0.33],
        subplot_titles=(
            f"Beta (rolling 1Y) vs {benchmark_name}",
            "Tracking error (roczny %)",
            "Information ratio",
        ),
    )
    df = risk_series.sort_values("date")
    fig.add_trace(
        go.Scatter(x=df["date"], y=df["beta"], mode="lines", name="Beta", line=dict(color=ACCENT, width=2)),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["tracking_error_pct"],
            mode="lines",
            name="Tracking error",
            line=dict(color=BENCH, width=2),
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["information_ratio"],
            mode="lines",
            name="IR",
            line=dict(color=PROFIT, width=2),
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    fig.add_hline(y=1.0, line_dash="dot", line_color=reference_line_color(), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color(), row=3, col=1)
    fig.update_layout(
        title=f"Beta i tracking error vs {benchmark_name}",
        height=580,
        hovermode="x unified",
        margin=dict(t=80),
    )
    fig.update_yaxes(title_text="Beta", row=1, col=1)
    fig.update_yaxes(title_text="TE %", row=2, col=1)
    fig.update_yaxes(title_text="IR", row=3, col=1)
    return style_figure(fig)


def build_portfolio_vs_benchmark_chart(
    merged: pd.DataFrame,
    benchmark_name: str,
) -> go.Figure:
    """Porównanie indeksu TWR portfela z benchmarkiem (oba rebazowane do 100)."""
    fig = go.Figure()
    if merged is None or merged.empty:
        fig.update_layout(title="Brak danych do porównania z benchmarkiem")
        return style_figure(fig)

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
    fig.add_hline(y=100, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title=f"Portfel vs {benchmark_name} (100 = start, oba znormalizowane)",
        height=430,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Indeks (100 = start)")
    return style_figure(fig)


def build_snapshots_chart(snapshots: pd.DataFrame, currency: str) -> go.Figure:
    """Wartość i koszt portfela z zapisanych snapshotów."""
    fig = go.Figure()
    if snapshots is None or snapshots.empty:
        fig.update_layout(title="Brak zapisanych snapshotów")
        return style_figure(fig)

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
    return style_figure(fig)


def build_return_attribution_chart(attribution: pd.DataFrame, title_suffix: str = "") -> go.Figure:
    """Słupkowy wykres atrybucji zwrotu (pp) — pozycje / sektory / regiony."""
    fig = go.Figure()
    if attribution is None or attribution.empty:
        fig.update_layout(title="Brak danych do atrybucji zwrotu")
        return style_figure(fig)

    df = attribution.copy()
    colors = [PROFIT if v >= 0 else LOSS for v in df["contribution_pp"]]
    fig.add_trace(
        go.Bar(
            y=df["label"],
            x=df["contribution_pp"],
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f} pp" for v in df["contribution_pp"]],
            textposition="outside",
        )
    )
    fig.add_vline(x=0, line_dash="dash", line_color=reference_line_color())
    title = "Atrybucja zwrotu TWR"
    if title_suffix:
        title += f" ({title_suffix})"
    fig.update_layout(
        title=title,
        height=max(320, 40 * len(df)),
        margin=dict(t=56, l=120),
        xaxis_title="Wkład w zwrot (pp)",
        yaxis_title="",
    )
    return style_figure(fig)


def build_rolling_returns_heatmap(heatmap_df: pd.DataFrame) -> go.Figure:
    """Heatmapa rolling returns: okres × horyzont (1M/3M/6M/1Y)."""
    fig = go.Figure()
    if heatmap_df is None or heatmap_df.empty:
        fig.update_layout(title="Brak danych do heatmapy rolling returns")
        return style_figure(fig)

    value_cols = [c for c in ("1M", "3M", "6M", "1Y") if c in heatmap_df.columns]
    z = heatmap_df[value_cols].values
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=value_cols,
            y=heatmap_df["period"].tolist(),
            colorscale=heatmap_color_scale(),
            zmid=0,
            text=[[f"{v:+.1f}%" if pd.notna(v) else "—" for v in row] for row in z],
            texttemplate="%{text}",
            hovertemplate="Okres: %{y}<br>%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Rolling returns — czy ostatnie miesiące odstają od trendu?",
        height=max(400, 28 * len(heatmap_df)),
        margin=dict(t=60, l=80),
        xaxis_title="Horyzont",
        yaxis_title="Okres",
        yaxis=dict(autorange="reversed"),
    )
    return style_figure(fig, heatmap=True)


def build_multi_benchmark_chart(
    merged: pd.DataFrame,
    benchmark_names: list[str],
) -> go.Figure:
    """Portfel (gruba linia) + wiele benchmarków (cienkie linie)."""
    fig = go.Figure()
    if merged is None or merged.empty:
        fig.update_layout(title="Brak danych do porównania multi-benchmark")
        return style_figure(fig)

    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["portfolio"],
            mode="lines",
            name="Portfel (TWR)",
            line=dict(color=ACCENT, width=2.8),
        )
    )
    for i, name in enumerate(benchmark_names):
        col = f"bench_{name}"
        if col not in merged.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=merged["date"],
                y=merged[col],
                mode="lines",
                name=name,
                line=dict(
                    color=BENCH_COLORS[i % len(BENCH_COLORS)],
                    width=1.2,
                    dash=BENCH_DASHES[i % len(BENCH_DASHES)],
                ),
                opacity=0.85,
            )
        )
    fig.add_hline(y=100, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title="Portfel vs wiele benchmarków (100 = start)",
        height=460,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text="Indeks (100 = start)")
    return style_figure(fig)


def build_calendar_returns_heatmap(calendar_df: pd.DataFrame) -> go.Figure:
    """Kalendarz zwrotów dziennych (GitHub-style) — kolor = dzienny % zwrotu."""
    fig = go.Figure()
    if calendar_df is None or calendar_df.empty:
        fig.update_layout(title="Brak danych do kalendarza zwrotów")
        return style_figure(fig)

    df = calendar_df.copy()
    years = sorted(df["year"].unique())
    if not years:
        fig.update_layout(title="Brak danych do kalendarza zwrotów")
        return style_figure(fig)

    # Ostatnie 2 lata lub wszystkie, max 2
    plot_years = years[-2:] if len(years) > 2 else years
    df = df[df["year"].isin(plot_years)]

    weekday_labels = ["Pn", "Wt", "Śr", "Cz", "Pt", "Sb", "Nd"]
    traces_added = 0
    for year in plot_years:
        year_df = df[df["year"] == year]
        pivot = year_df.pivot_table(
            index="weekday", columns="week", values="return_pct", aggfunc="mean"
        )
        if pivot.empty:
            continue
        pivot = pivot.reindex(range(7)).sort_index()
        z = pivot.values
        fig.add_trace(
            go.Heatmap(
                z=z,
                x=[str(w) for w in pivot.columns],
                y=weekday_labels,
                colorscale=heatmap_color_scale(),
                zmid=0,
                name=str(year),
                visible=True if year == plot_years[-1] else "legendonly",
                text=[[f"{v:+.2f}%" if pd.notna(v) else "" for v in row] for row in z],
                hovertemplate="Tydzień %{x}, %{y}<br>Zwrot: %{text}<extra></extra>",
            )
        )
        traces_added += 1

    if traces_added == 0:
        fig.update_layout(title="Brak danych do kalendarza zwrotów")
        return style_figure(fig)

    fig.update_layout(
        title="Kalendarz dziennych zwrotów portfela (TWR)",
        height=320,
        margin=dict(t=56, b=40),
        xaxis_title="Tydzień roku",
        yaxis_title="Dzień tygodnia",
    )
    return style_figure(fig, heatmap=True)


def build_monte_carlo_fan_chart(mc_paths: pd.DataFrame, horizon_years: float) -> go.Figure:
    """Fan chart Monte Carlo — percentyle 10/50/90."""
    fig = go.Figure()
    if mc_paths is None or mc_paths.empty:
        fig.update_layout(title="Brak danych do symulacji Monte Carlo")
        return style_figure(fig)

    x = mc_paths["months"]
    fig.add_trace(
        go.Scatter(
            x=x, y=mc_paths["p90"], mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=mc_paths["p10"], mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(37, 99, 235, 0.15)",
            name="P10–P90", showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x, y=mc_paths["p50"], mode="lines",
            name="Mediana (P50)", line=dict(color=ACCENT, width=2.5),
        )
    )
    fig.add_hline(y=100, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title=f"Monte Carlo — rozkład wartości portfela ({horizon_years:.0f} lat, bootstrap)",
        height=420,
        hovermode="x unified",
        margin=dict(t=56),
        xaxis_title="Miesiące",
        yaxis_title="Indeks (start = 100)",
    )
    return style_figure(fig)
