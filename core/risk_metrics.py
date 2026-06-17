"""
Metryki ryzyka portfela: zmienność, max drawdown, Sharpe, Calmar
oraz macierz korelacji dziennych zwrotów pozycji.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

from core.history import PERIOD_OPTIONS, fetch_price_history

TRADING_DAYS = 252

# Domyślne stopy wolne od ryzyka (roczne) — orientacyjne, konfigurowalne w UI.
DEFAULT_RISK_FREE: dict[str, float] = {
    "PLN": 0.0525,
    "EUR": 0.045,
    "USD": 0.0450,
    "GBP": 0.0500,
}


@dataclass
class RiskMetrics:
    volatility_pct: float | None
    max_drawdown_pct: float | None
    sharpe_ratio: float | None
    calmar_ratio: float | None
    annual_return_pct: float | None
    best_day_pct: float | None
    worst_day_pct: float | None
    best_day_date: pd.Timestamp | None
    worst_day_date: pd.Timestamp | None
    has_data: bool


def _empty_metrics() -> RiskMetrics:
    return RiskMetrics(
        volatility_pct=None,
        max_drawdown_pct=None,
        sharpe_ratio=None,
        calmar_ratio=None,
        annual_return_pct=None,
        best_day_pct=None,
        worst_day_pct=None,
        best_day_date=None,
        worst_day_date=None,
        has_data=False,
    )


def compute_risk_metrics(
    timeline: pd.DataFrame,
    risk_free: float = 0.0525,
) -> RiskMetrics:
    """
    Wylicza metryki ryzyka z timeline portfela (kolumny: date, market_value).

    risk_free: roczna stopa wolna od ryzyka (np. 0.0525 dla 5.25%).
    """
    if timeline is None or timeline.empty or "market_value" not in timeline.columns:
        return _empty_metrics()

    df = timeline.dropna(subset=["market_value"]).copy()
    df = df[df["market_value"] > 0]
    if "date" in df.columns:
        df = df.sort_values("date")
    if len(df) < 3:
        return _empty_metrics()

    market_value = df["market_value"].reset_index(drop=True)
    returns = market_value.pct_change().dropna()
    if returns.empty or returns.std() == 0:
        return _empty_metrics()

    vol = float(returns.std() * np.sqrt(TRADING_DAYS) * 100)

    rolling_max = market_value.cummax()
    drawdown = (market_value - rolling_max) / rolling_max * 100
    max_drawdown = float(drawdown.min())

    n = len(market_value)
    annual_return = (market_value.iloc[-1] / market_value.iloc[0]) ** (TRADING_DAYS / n) - 1

    ann_vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = float((annual_return - risk_free) / ann_vol) if ann_vol else None

    calmar = (
        float(annual_return / abs(max_drawdown / 100))
        if max_drawdown != 0
        else None
    )

    dates = df["date"].reset_index(drop=True) if "date" in df.columns else None
    best_idx = returns.idxmax()
    worst_idx = returns.idxmin()
    best_day = float(returns.loc[best_idx] * 100)
    worst_day = float(returns.loc[worst_idx] * 100)
    best_date = dates.loc[best_idx] if dates is not None else None
    worst_date = dates.loc[worst_idx] if dates is not None else None

    return RiskMetrics(
        volatility_pct=vol,
        max_drawdown_pct=max_drawdown,
        sharpe_ratio=sharpe,
        calmar_ratio=calmar,
        annual_return_pct=float(annual_return * 100),
        best_day_pct=best_day,
        worst_day_pct=worst_day,
        best_day_date=best_date,
        worst_day_date=worst_date,
        has_data=True,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def build_correlation_matrix(tickers_yahoo: tuple[str, ...], period: str) -> pd.DataFrame:
    """Macierz korelacji dziennych zwrotów dla podanych tickerów Yahoo."""
    if not tickers_yahoo or period not in PERIOD_OPTIONS:
        return pd.DataFrame()

    prices: dict[str, pd.Series] = {}
    for ticker in tickers_yahoo:
        try:
            hist = fetch_price_history(ticker, period)
        except Exception:
            continue
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        series = hist.set_index("Date")["Close"] if "Date" in hist.columns else hist["Close"]
        prices[ticker] = series

    if len(prices) < 2:
        return pd.DataFrame()

    df = pd.DataFrame(prices).dropna()
    if df.empty or len(df) < 3:
        return pd.DataFrame()
    return df.pct_change().dropna().corr()


def high_correlation_pairs(
    corr: pd.DataFrame,
    threshold: float = 0.9,
) -> list[tuple[str, str, float]]:
    """Zwraca pary tickerów z korelacją powyżej progu (bez duplikatów)."""
    if corr is None or corr.empty:
        return []
    pairs: list[tuple[str, str, float]] = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            value = corr.iloc[i, j]
            if pd.notna(value) and value >= threshold:
                pairs.append((cols[i], cols[j], float(value)))
    return sorted(pairs, key=lambda x: x[2], reverse=True)
