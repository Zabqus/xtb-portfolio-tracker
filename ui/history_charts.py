"""Wykresy strony Historia."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui.plotly_theme import reference_line_color, style_figure


def build_portfolio_timeline_chart(
    timeline: pd.DataFrame,
    currency: str,
) -> go.Figure:
    """Wykres liniowy wartości portfela i bazy kosztowej w czasie."""
    df = timeline.dropna(subset=["date"]).copy()

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if "market_value" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["market_value"],
                name=f"Wartość rynkowa ({currency})",
                line=dict(color="#4a9eff", width=2),
                fill="tozeroy",
                fillcolor="rgba(74, 158, 255, 0.1)",
            ),
            secondary_y=False,
        )

    if "cost_basis" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["cost_basis"],
                name=f"Baza kosztowa ({currency})",
                line=dict(color="#f39c12", width=2, dash="dash"),
            ),
            secondary_y=False,
        )

    if "position_count" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["position_count"],
                name="Liczba pozycji",
                marker_color="rgba(108, 117, 125, 0.35)",
                opacity=0.6,
            ),
            secondary_y=True,
        )

    fig.update_layout(
        title=f"Timeline portfela ({currency})",
        height=480,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text=f"Wartość ({currency})", secondary_y=False)
    fig.update_yaxes(title_text="Pozycje", secondary_y=True, showgrid=False)
    return style_figure(fig)


def build_cumulative_realized_pnl(closed: pd.DataFrame, currency: str) -> go.Figure:
    """Skumulowany zrealizowany PnL z zamkniętych pozycji."""
    if closed is None or closed.empty or "close_time" not in closed.columns:
        fig = go.Figure()
        fig.update_layout(title="Brak danych zamkniętych pozycji")
        return style_figure(fig)

    df = closed.dropna(subset=["close_time", "pnl"]).sort_values("close_time").copy()
    df["cumulative_pnl"] = df["pnl"].cumsum()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["close_time"],
            y=df["cumulative_pnl"],
            mode="lines+markers",
            name="Skumulowany PnL",
            line=dict(color="#2ecc71", width=2),
            fill="tozeroy",
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title=f"Skumulowany zrealizowany PnL ({currency})",
        xaxis_title="Data zamknięcia",
        yaxis_title=f"PnL ({currency})",
        height=380,
    )
    return style_figure(fig)


def build_contributions_vs_value_chart(
    timeline: pd.DataFrame,
    cash_ops: pd.DataFrame,
    currency: str,
) -> go.Figure:
    """
    Area chart: skumulowane wpłaty gotówki vs wartość rynkowa portfela.
    Różnica między warstwami = zysk/strata rynkowa względem wpłaconych środków.
    """
    fig = go.Figure()

    if cash_ops is None or cash_ops.empty or "Type" not in cash_ops.columns:
        fig.update_layout(title="Brak danych Cash Operations do wykresu wpłat")
        return style_figure(fig)

    cash_in = cash_ops[
        cash_ops["Type"].astype(str).str.contains(
            "cash in|deposit|wpłata|wplata", case=False, na=False
        )
    ].copy()

    if cash_in.empty:
        fig.update_layout(title="Brak operacji wpłat (Cash in / Deposit) w eksporcie")
        return style_figure(fig)

    cash_in["date"] = pd.to_datetime(cash_in.get("Time"), errors="coerce")
    cash_in = cash_in.dropna(subset=["date"]).sort_values("date")
    cash_in["amount"] = pd.to_numeric(cash_in.get("Amount"), errors="coerce").abs()
    cash_in = cash_in.dropna(subset=["amount"])
    cash_in["cumulative_deposits"] = cash_in["amount"].cumsum()

    tl = timeline.dropna(subset=["date", "market_value"]).sort_values("date").copy()
    tl["date"] = pd.to_datetime(tl["date"])

    merged = pd.merge_asof(
        tl,
        cash_in[["date", "cumulative_deposits"]],
        on="date",
        direction="backward",
    )
    merged["cumulative_deposits"] = merged["cumulative_deposits"].ffill()

    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["market_value"],
            fill="tozeroy",
            name="Wartość portfela",
            line=dict(color="#2ecc71", width=2),
            fillcolor="rgba(46, 204, 113, 0.15)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=merged["date"],
            y=merged["cumulative_deposits"],
            fill="tozeroy",
            name="Skumulowane wpłaty",
            line=dict(color="#3498db", width=2, dash="dash"),
            fillcolor="rgba(52, 152, 219, 0.10)",
        )
    )
    fig.update_layout(
        title=f"Wpłaty vs wartość rynkowa ({currency})",
        height=400,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60),
    )
    fig.update_xaxes(title_text="Data")
    fig.update_yaxes(title_text=f"Wartość ({currency})")
    return style_figure(fig)


def build_dividends_per_year_chart(per_year: pd.DataFrame, currency: str) -> go.Figure:
    """Bar chart sumy dywidend per rok."""
    if per_year is None or per_year.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych o dywidendach")
        return style_figure(fig)

    fig = px.bar(
        per_year,
        x="year",
        y="amount",
        title=f"Dywidendy per rok ({currency})",
        text_auto=".2f",
    )
    fig.update_traces(marker_color="#9b59b6")
    fig.update_layout(height=360, xaxis_title="Rok", yaxis_title=f"Dywidendy ({currency})")
    fig.update_xaxes(type="category")
    return style_figure(fig)


def build_cumulative_dividends_chart(div: pd.DataFrame, currency: str) -> go.Figure:
    """Wykres kumulatywny otrzymanych dywidend w czasie."""
    if div is None or div.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych o dywidendach")
        return style_figure(fig)

    df = div.sort_values("date").copy()
    df["cumulative"] = df["amount"].cumsum()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cumulative"],
            mode="lines+markers",
            name="Skumulowane dywidendy",
            line=dict(color="#9b59b6", width=2),
            fill="tozeroy",
            fillcolor="rgba(155, 89, 182, 0.12)",
        )
    )
    fig.update_layout(
        title=f"Skumulowane dywidendy ({currency})",
        xaxis_title="Data",
        yaxis_title=f"Dywidendy ({currency})",
        height=360,
    )
    return style_figure(fig)


def build_dividend_yield_comparison_chart(yield_df: pd.DataFrame) -> go.Figure:
    """Słupki: yield on cost vs forward yield per ticker."""
    if yield_df is None or yield_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych yield on cost / forward")
        return style_figure(fig)

    df = yield_df.dropna(subset=["yield_on_cost_pct", "forward_yield_pct"]).copy()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak pozycji z danymi dywidendowymi")
        return style_figure(fig)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Yield on cost",
            x=df["ticker_xtb"],
            y=df["yield_on_cost_pct"],
            marker_color="#9b59b6",
            text=df["yield_on_cost_pct"].round(2),
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Forward yield",
            x=df["ticker_xtb"],
            y=df["forward_yield_pct"],
            marker_color="#3498db",
            text=df["forward_yield_pct"].round(2),
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Yield on cost vs forward yield (per ticker)",
        xaxis_title="Ticker",
        yaxis_title="Yield %",
        barmode="group",
        height=420,
        legend=dict(orientation="h", y=1.08),
    )
    return style_figure(fig)


def build_ex_dividend_calendar_chart(cal: pd.DataFrame, month: pd.Timestamp) -> go.Figure:
    """Widok miesiąca — Gantt z datami ex-dividend."""
    fig = go.Figure()
    if cal is None or cal.empty or "ex_date" not in cal.columns:
        fig.update_layout(title="Brak dat ex-dividend")
        return style_figure(fig)

    month_start = pd.Timestamp(month).replace(day=1).normalize()
    month_end = (month_start + pd.offsets.MonthEnd(0)).normalize()

    df = cal.dropna(subset=["ex_date"]).copy()
    df["ex_date"] = pd.to_datetime(df["ex_date"], errors="coerce").dt.normalize()
    df = df[(df["ex_date"] >= month_start) & (df["ex_date"] <= month_end)]
    if df.empty:
        fig.update_layout(
            title=f"Kalendarz ex-dividend — {month_start.strftime('%B %Y')} (brak wypłat w tym miesiącu)"
        )
        return style_figure(fig)

    df = df.sort_values("ex_date").reset_index(drop=True)
    colors = ["#2ecc71" if u else "#95a5a6" for u in df.get("ex_upcoming", [True] * len(df))]

    for idx, row in df.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["ex_date"], row["ex_date"] + pd.Timedelta(hours=20)],
                y=[row["ticker_xtb"], row["ticker_xtb"]],
                mode="lines",
                line=dict(color=colors[idx], width=14),
                hovertemplate=(
                    f"{row['ticker_xtb']}<br>Ex-date: {row['ex_date'].strftime('%Y-%m-%d')}"
                    f"<br>Yield: {row.get('yield_pct', 0):.2f}%<extra></extra>"
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        title=f"Kalendarz ex-dividend — {month_start.strftime('%B %Y')}",
        xaxis=dict(
            range=[month_start - pd.Timedelta(days=1), month_end + pd.Timedelta(days=1)],
            tickformat="%d %b",
            title="Data ex-dividend",
        ),
        yaxis=dict(title="", autorange="reversed"),
        height=max(280, 60 + len(df) * 36),
        margin=dict(l=80, r=20, t=60, b=40),
        hovermode="closest",
    )
    return style_figure(fig)


def build_projected_dividend_cashflow_chart(projected_12m: pd.DataFrame, currency: str) -> go.Figure:
    """Słupkowy projected dividend cashflow na 12 miesięcy."""
    if projected_12m is None or projected_12m.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych projekcji dywidend")
        return style_figure(fig)

    fig = go.Figure(
        data=[
            go.Bar(
                x=projected_12m["month_label"],
                y=projected_12m["projected_income"],
                marker_color="#9b59b6",
                text=projected_12m["projected_income"].round(2),
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=f"Projected dividend cashflow (12M) — {currency}",
        xaxis_title="Miesiąc",
        yaxis_title=f"Kwota ({currency})",
        height=360,
    )
    return style_figure(fig)


def build_dividend_growth_tracker_chart(growth_df: pd.DataFrame) -> go.Figure:
    """Status raise/flat/cut + % zmiany dywidendy per ticker."""
    if growth_df is None or growth_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych growth tracker")
        return style_figure(fig)

    color_map = {"raise": "#2ecc71", "flat": "#f39c12", "cut": "#e74c3c"}
    colors = [color_map.get(s, "#95a5a6") for s in growth_df["status"]]
    fig = go.Figure(
        data=[
            go.Bar(
                x=growth_df["ticker_yahoo"],
                y=growth_df["growth_pct"],
                marker_color=colors,
                text=growth_df["growth_pct"].round(2),
                textposition="outside",
                hovertemplate=(
                    "Ticker: %{x}<br>Zmiana: %{y:.2f}%<br>"
                    "Current: %{customdata[0]:.4f}<br>Previous: %{customdata[1]:.4f}<extra></extra>"
                ),
                customdata=growth_df[["current_rate", "previous_rate"]].to_numpy(),
            )
        ]
    )
    fig.add_hline(y=0, line_dash="dash", line_color=reference_line_color())
    fig.update_layout(
        title="Dividend growth tracker (current vs previous rate)",
        xaxis_title="Ticker",
        yaxis_title="Zmiana dywidendy %",
        height=360,
    )
    return style_figure(fig)
