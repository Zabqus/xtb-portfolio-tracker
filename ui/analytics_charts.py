"""Wykresy trade analytics i cost basis."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui.plotly_theme import reference_line_color, style_figure


def build_trader_equity_curve(
    round_trips: pd.DataFrame,
    trades: pd.DataFrame,
    currency: str,
) -> go.Figure:
    """Kumulatywny zrealizowany P&L + markery kupna/sprzedaży na osi czasu."""
    fig = go.Figure()
    if round_trips is None or round_trips.empty:
        fig.update_layout(title="Brak round-tripów do krzywej equity")
        return style_figure(fig)

    trips = round_trips.dropna(subset=["close_time", "realized_pnl"]).sort_values("close_time").copy()
    trips["cumulative_pnl"] = trips["realized_pnl"].cumsum()

    fig.add_trace(
        go.Scatter(
            x=trips["close_time"],
            y=trips["cumulative_pnl"],
            mode="lines+markers",
            name="Skumulowany P&L",
            line=dict(color="#4a9eff", width=2),
            fill="tozeroy",
            fillcolor="rgba(74, 158, 255, 0.12)",
            hovertemplate="%{x|%Y-%m-%d}<br>P&L: %{y:,.2f}<extra></extra>",
        )
    )

    if trades is not None and not trades.empty and "trade_time" in trades.columns:
        trade_times = pd.to_datetime(trades["trade_time"], errors="coerce")
        cum_at_trade: list[float] = []
        for t in trade_times:
            if pd.isna(t):
                cum_at_trade.append(0.0)
                continue
            mask = trips["close_time"] <= t
            cum_at_trade.append(float(trips.loc[mask, "realized_pnl"].sum()) if mask.any() else 0.0)

        marker_df = trades.copy()
        marker_df["trade_time"] = trade_times
        marker_df["equity_y"] = cum_at_trade
        marker_df = marker_df.dropna(subset=["trade_time"])

        opens = marker_df[marker_df["side"] == "OPEN"]
        closes = marker_df[marker_df["side"] == "CLOSE"]

        if not opens.empty:
            fig.add_trace(
                go.Scatter(
                    x=opens["trade_time"],
                    y=opens["equity_y"],
                    mode="markers",
                    name="Kupno (OPEN)",
                    marker=dict(symbol="triangle-up", size=10, color="#2ecc71", line=dict(width=1, color="white")),
                    text=opens["ticker_xtb"],
                    hovertemplate="Kupno %{text}<br>%{x|%Y-%m-%d}<extra></extra>",
                )
            )
        if not closes.empty:
            fig.add_trace(
                go.Scatter(
                    x=closes["trade_time"],
                    y=closes["equity_y"],
                    mode="markers",
                    name="Sprzedaż (CLOSE)",
                    marker=dict(symbol="triangle-down", size=10, color="#e74c3c", line=dict(width=1, color="white")),
                    text=closes["ticker_xtb"],
                    hovertemplate="Sprzedaż %{text}<br>%{x|%Y-%m-%d}<extra></extra>",
                )
            )

    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title=f"Krzywa equity tradera — skumulowany P&L ({currency})",
        xaxis_title="Data",
        yaxis_title=f"P&L ({currency})",
        height=420,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
    )
    return style_figure(fig)


def build_mae_mfe_chart(round_trips: pd.DataFrame) -> go.Figure:
    """Scatter MAE vs MFE per zamknięty round-trip."""
    if round_trips is None or round_trips.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych MAE/MFE")
        return style_figure(fig)

    df = round_trips.dropna(subset=["mae_pct", "mfe_pct"]).copy()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych cenowych do MAE/MFE (Yahoo)")
        return style_figure(fig)

    colors = ["#2ecc71" if w else "#e74c3c" for w in df["is_win"]]
    fig = go.Figure(
        data=[
            go.Scatter(
                x=df["mae_pct"],
                y=df["mfe_pct"],
                mode="markers",
                marker=dict(color=colors, size=10, opacity=0.75),
                text=df["ticker_xtb"] + " (" + df["close_time"].dt.strftime("%Y-%m-%d") + ")",
                hovertemplate="%{text}<br>MAE: %{x:.1f}%<br>MFE: %{y:.1f}%<extra></extra>",
            )
        ]
    )
    fig.add_hline(y=0, line_dash="dot", line_color=reference_line_color())
    fig.add_vline(x=0, line_dash="dot", line_color=reference_line_color())
    fig.update_layout(
        title="MAE vs MFE — ekscurcje w trakcie trzymania pozycji",
        xaxis_title="MAE % (max. strata niezrealizowana)",
        yaxis_title="MFE % (max. zysk niezrealizowany)",
        height=400,
    )
    return style_figure(fig)


def build_holding_vs_outcome_chart(round_trips: pd.DataFrame) -> go.Figure:
    """Scatter: długość trzymania vs wynik % — win rate w podziale na przedziały."""
    if round_trips is None or round_trips.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych")
        return style_figure(fig)

    df = round_trips.dropna(subset=["holding_days", "pnl_pct"]).copy()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych o czasie trzymania")
        return style_figure(fig)

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Wynik % vs czas trzymania", "Win rate wg przedziału (dni)"),
        column_widths=[0.55, 0.45],
    )

    colors = ["#2ecc71" if w else "#e74c3c" for w in df["is_win"]]
    fig.add_trace(
        go.Scatter(
            x=df["holding_days"],
            y=df["pnl_pct"],
            mode="markers",
            marker=dict(color=colors, size=9, opacity=0.7),
            text=df["ticker_xtb"],
            hovertemplate="%{text}<br>%{x:.0f} dni · %{y:.1f}%<extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color(), row=1, col=1)

    bins = [0, 7, 30, 90, 180, float("inf")]
    labels = ["0–7", "8–30", "31–90", "91–180", "180+"]
    df["holding_bucket"] = pd.cut(
        df["holding_days"], bins=bins, labels=labels, right=True, include_lowest=True
    )
    bucket_stats = (
        df.groupby("holding_bucket", observed=True)["is_win"]
        .agg(win_rate="mean", count="count")
        .reset_index()
    )
    bucket_stats["win_rate_pct"] = bucket_stats["win_rate"] * 100

    fig.add_trace(
        go.Bar(
            x=bucket_stats["holding_bucket"].astype(str),
            y=bucket_stats["win_rate_pct"],
            marker_color="#4a9eff",
            text=[f"{v:.0f}% (n={int(c)})" for v, c in zip(bucket_stats["win_rate_pct"], bucket_stats["count"])],
            textposition="outside",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    fig.update_xaxes(title_text="Dni trzymania", row=1, col=1)
    fig.update_yaxes(title_text="Wynik %", row=1, col=1)
    fig.update_xaxes(title_text="Przedział (dni)", row=1, col=2)
    fig.update_yaxes(title_text="Win rate %", range=[0, 100], row=1, col=2)
    fig.update_layout(
        title="Czas trzymania vs wynik transakcji",
        height=400,
        margin=dict(t=80),
    )
    return style_figure(fig)


def build_streak_chart(round_trips: pd.DataFrame, streak_events: pd.DataFrame) -> go.Figure:
    """Wizualizacja serii wygranych/przegranych w czasie."""
    if round_trips is None or round_trips.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych o seriach")
        return style_figure(fig)

    df = round_trips.sort_values("close_time").copy()
    colors = ["#2ecc71" if w else "#e74c3c" for w in df["is_win"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=df["close_time"],
                y=[1] * len(df),
                marker_color=colors,
                text=df["realized_pnl"].round(2),
                hovertemplate="%{x|%Y-%m-%d}<br>PnL: %{text}<extra></extra>",
                showlegend=False,
            )
        ]
    )

    if streak_events is not None and not streak_events.empty:
        for _, streak in streak_events.iterrows():
            color = "rgba(46, 204, 113, 0.15)" if streak["is_win"] else "rgba(231, 76, 60, 0.15)"
            fig.add_vrect(
                x0=streak["start_time"],
                x1=streak["end_time"],
                fillcolor=color,
                layer="below",
                line_width=0,
            )

    fig.update_layout(
        title="Sekwencja wygranych / przegranych (każdy słupek = jeden round-trip)",
        xaxis_title="Data zamknięcia",
        yaxis=dict(showticklabels=False, showgrid=False),
        height=320,
        bargap=0.1,
    )
    return style_figure(fig)


def build_exit_strategy_chart(round_trips: pd.DataFrame) -> go.Figure:
    """Histogram P&L z podziałem na strategie wyjścia."""
    if round_trips is None or round_trips.empty or "exit_category" not in round_trips.columns:
        fig = go.Figure()
        fig.update_layout(title="Brak danych o strategiach wyjścia")
        return style_figure(fig)

    labels = {
        "profit_target": "Zysk >20%",
        "stop_loss": "Stop-loss (≤-5%)",
        "time_based": "Time-based (≥90 dni)",
        "other": "Inne",
    }
    colors = {
        "profit_target": "#2ecc71",
        "stop_loss": "#e74c3c",
        "time_based": "#f39c12",
        "other": "#95a5a6",
    }

    df = round_trips.copy()
    df["category_label"] = df["exit_category"].map(labels).fillna("Inne")

    fig = go.Figure()
    for cat, label in labels.items():
        subset = df[df["exit_category"] == cat]
        if subset.empty:
            continue
        fig.add_trace(
            go.Histogram(
                x=subset["realized_pnl"],
                name=label,
                marker_color=colors.get(cat, "#95a5a6"),
                opacity=0.75,
                nbinsx=15,
            )
        )

    fig.add_vline(x=0, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title="Rozkład P&L wg typu wyjścia",
        xaxis_title="Zrealizowany P&L",
        yaxis_title="Liczba transakcji",
        barmode="overlay",
        height=400,
        legend=dict(orientation="h", y=1.08),
    )
    return style_figure(fig)



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
