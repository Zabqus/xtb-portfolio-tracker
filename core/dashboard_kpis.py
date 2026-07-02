"""
Zbiorcze KPI dashboardu: wartości + serie do sparkline (30 / 90 dni).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from core.alerts import compute_roi_alerts
from core.analyzer import analyze_portfolio, portfolio_summary
from core.dividends import dividends_summary, parse_dividends
from core.importer import XTBReport
from core.returns import compute_mwr, compute_twr
from core.risk_metrics import DEFAULT_RISK_FREE, compute_drawdown_series, compute_risk_metrics
from core.session import get_trade_analytics


@dataclass
class KpiMetric:
    label: str
    value: str
    delta: str | None = None
    delta_color: str = "off"
    sparkline: list[float] = field(default_factory=list)
    help_text: str | None = None


@dataclass
class DashboardKpis:
    metrics: list[KpiMetric]
    currency: str
    has_timeline: bool = False


def _tail_values(series: pd.Series, days: int) -> list[float]:
    if series is None or series.empty:
        return []
    clean = series.dropna()
    if clean.empty:
        return []
    return [float(v) for v in clean.tail(days).tolist()]


def _period_return(index_df: pd.DataFrame, start: pd.Timestamp) -> float | None:
    if index_df is None or index_df.empty:
        return None
    df = index_df.dropna(subset=["date", "twr_index"]).sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    end = df["date"].iloc[-1]
    start = pd.Timestamp(start).normalize()
    subset = df[df["date"] >= start]
    if subset.empty:
        return None
    v0 = float(subset["twr_index"].iloc[0])
    v1 = float(subset["twr_index"].iloc[-1])
    if v0 <= 0:
        return None
    return (v1 / v0 - 1.0) * 100.0


def _rolling_win_rate(round_trips: pd.DataFrame | None, days: int) -> list[float]:
    """Skumulowany win rate z round-tripów zamkniętych w ostatnich N dniach."""
    if round_trips is None or round_trips.empty or "close_time" not in round_trips.columns:
        return []
    rt = round_trips.dropna(subset=["close_time"]).copy()
    rt["close_time"] = pd.to_datetime(rt["close_time"])
    if rt.empty:
        return []
    end = rt["close_time"].max()
    start = end - pd.Timedelta(days=days)
    window = rt[rt["close_time"] >= start].sort_values("close_time")
    if window.empty:
        return []
    wins = window.get("is_win", window["realized_pnl"] > 0).astype(bool)
    cumulative = wins.expanding().mean() * 100.0
    return [float(v) for v in cumulative.tolist()]


def compute_dashboard_kpis(
    report: XTBReport,
    analyzed: pd.DataFrame,
    timeline: pd.DataFrame | None,
    *,
    currency: str,
    sparkline_days: int = 30,
    alert_threshold_pct: float = 10.0,
) -> DashboardKpis:
    """Liczy metryki ścianki KPI + sparkline dla wybranego okna (30 lub 90 dni)."""
    days = max(7, min(90, int(sparkline_days)))
    summary = portfolio_summary(analyzed)
    total_value = float(summary["total_value"])
    metrics: list[KpiMetric] = []

    # — wartość portfela —
    value_spark: list[float] = []
    if timeline is not None and not timeline.empty:
        tl = timeline.dropna(subset=["market_value"]).sort_values("date")
        value_spark = _tail_values(tl["market_value"], days)
    metrics.append(
        KpiMetric(
            label="Wartość portfela",
            value=f"{total_value:,.2f} {currency}",
            sparkline=value_spark,
            help_text="Bieżąca wartość rynkowa otwartych pozycji w walucie wyświetlania.",
        )
    )

    has_timeline = timeline is not None and not timeline.empty and report.cash_operations is not None
    twr = compute_twr(timeline, report.cash_operations) if has_timeline else None
    twr_index = twr.index if twr and twr.has_data else pd.DataFrame()

    # — TWR YTD / 1Y —
    twr_ytd: float | None = None
    twr_1y: float | None = None
    twr_spark: list[float] = []
    if not twr_index.empty:
        end = pd.Timestamp(twr_index["date"].iloc[-1]).normalize()
        twr_ytd = _period_return(twr_index, pd.Timestamp(end.year, 1, 1))
        twr_1y = _period_return(twr_index, end - pd.Timedelta(days=365))
        twr_spark = _tail_values(twr_index.set_index("date")["twr_index"], days)

    twr_main = f"{twr_ytd:+.2f}%" if twr_ytd is not None else "—"
    twr_delta = f"1Y: {twr_1y:+.2f}%" if twr_1y is not None else None
    metrics.append(
        KpiMetric(
            label="TWR YTD",
            value=twr_main,
            delta=twr_delta,
            delta_color="normal" if (twr_ytd or 0) >= 0 else "inverse",
            sparkline=twr_spark,
            help_text="Stopa zwrotu ważona czasem (bez wpływu momentu wpłat).",
        )
    )

    # — MWR —
    mwr_val = "—"
    mwr_delta = None
    mwr_color = "off"
    mwr_spark: list[float] = []
    if not report.is_merged and report.cash_operations is not None:
        acct_ccy = report.account_currency
        analyzed_acct = analyze_portfolio(report.open_positions, display_currency=acct_ccy)
        holdings = float(portfolio_summary(analyzed_acct)["total_value"])
        mwr = compute_mwr(report.cash_operations, holdings, currency=acct_ccy)
        if mwr.has_data:
            if mwr.xirr_pct is not None:
                mwr_val = f"{mwr.xirr_pct:+.2f}%"
                mwr_color = "normal" if mwr.xirr_pct >= 0 else "inverse"
            elif mwr.simple_return_pct is not None:
                mwr_val = f"{mwr.simple_return_pct:+.2f}%"
                mwr_color = "normal" if mwr.simple_return_pct >= 0 else "inverse"
                mwr_delta = "łącznie (okres < 90 dni)"
            if value_spark:
                mwr_spark = value_spark
    metrics.append(
        KpiMetric(
            label="MWR (XIRR)",
            value=mwr_val,
            delta=mwr_delta,
            delta_color=mwr_color,
            sparkline=mwr_spark,
            help_text="Zwrot ważony przepływami — Twoja roczna stopa na wpłaconym kapitale.",
        )
    )

    # — max drawdown + Sharpe —
    rf = DEFAULT_RISK_FREE.get(currency, 0.045)
    risk = compute_risk_metrics(timeline, risk_free=rf) if has_timeline else None
    dd_spark: list[float] = []
    if has_timeline:
        dd_df = compute_drawdown_series(timeline)
        if not dd_df.empty:
            dd_spark = _tail_values(dd_df["drawdown_pct"], days)

    dd_val = f"{risk.max_drawdown_pct:.1f}%" if risk and risk.has_data and risk.max_drawdown_pct is not None else "—"
    metrics.append(
        KpiMetric(
            label="Max drawdown",
            value=dd_val,
            delta_color="inverse",
            sparkline=dd_spark,
            help_text="Największy spadek od szczytu wartości portfela.",
        )
    )

    sharpe_val = "—"
    sharpe_color = "off"
    sharpe_spark: list[float] = []
    if risk and risk.has_data and risk.sharpe_ratio is not None:
        sharpe_val = f"{risk.sharpe_ratio:.2f}"
        sharpe_color = "normal" if risk.sharpe_ratio >= 0 else "inverse"
        if has_timeline and not twr_index.empty:
            rets = twr_index.set_index("date")["twr_index"].pct_change().dropna()
            if len(rets) >= 10:
                roll = rets.rolling(min(30, len(rets))).apply(
                    lambda x: (x.mean() * 252 - rf) / (x.std() * np.sqrt(252)) if x.std() > 0 else np.nan,
                    raw=False,
                )
                sharpe_spark = _tail_values(roll, days)

    metrics.append(
        KpiMetric(
            label="Sharpe",
            value=sharpe_val,
            delta_color=sharpe_color,
            sparkline=sharpe_spark,
            help_text="(Zwrot roczny − stopa wolna od ryzyka) / zmienność.",
        )
    )

    # — win rate —
    trade_summary, round_trips = get_trade_analytics()
    wr_val = "—"
    wr_color = "off"
    wr_spark = _rolling_win_rate(round_trips, days)
    if trade_summary and trade_summary.closed_trades > 0:
        wr_val = f"{trade_summary.win_rate_pct:.1f}%"
        wr_color = "normal" if trade_summary.win_rate_pct >= 50 else "inverse"
    metrics.append(
        KpiMetric(
            label="Win rate",
            value=wr_val,
            delta=f"{trade_summary.closed_trades} trans." if trade_summary else None,
            delta_color=wr_color,
            sparkline=wr_spark,
            help_text="Odsetek zyskownych zamkniętych round-tripów (FIFO).",
        )
    )

    # — dywidendy YTD —
    div_ytd = 0.0
    div_spark: list[float] = []
    if report.cash_operations is not None:
        div_df = parse_dividends(report.cash_operations)
        div_stats = dividends_summary(div_df, current_year=datetime.now().year)
        div_ytd = float(div_stats["current_year"])
        if not div_df.empty:
            cy = div_df[div_df["year"] == datetime.now().year].sort_values("date")
            if not cy.empty:
                div_spark = _tail_values(cy["amount"].cumsum(), days)

    metrics.append(
        KpiMetric(
            label="Dywidendy YTD",
            value=f"{div_ytd:,.2f} {report.account_currency}",
            sparkline=div_spark,
            help_text="Suma wypłat dywidend w bieżącym roku (waluta konta XTB).",
        )
    )

    # — aktywne alerty —
    alerts = compute_roi_alerts(analyzed, alert_threshold_pct)
    n_alerts = len(alerts)
    alert_spark: list[float] = []
    if not alerts.empty and "roi_pct" in alerts.columns:
        alert_spark = [float(v) for v in alerts["roi_pct"].abs().head(days).tolist()]

    metrics.append(
        KpiMetric(
            label="Aktywne alerty",
            value=str(n_alerts),
            delta=f"próg ±{alert_threshold_pct:.0f}% ROI",
            delta_color="inverse" if n_alerts > 0 else "off",
            sparkline=alert_spark,
            help_text="Pozycje przekraczające próg |ROI%| — patrz strona Alerty.",
        )
    )

    return DashboardKpis(metrics=metrics, currency=currency, has_timeline=has_timeline)
