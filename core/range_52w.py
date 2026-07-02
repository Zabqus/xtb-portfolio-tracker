"""Pozycja ceny w zakresie 52-tygodniowym (Yahoo Finance)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.fundamentals import fetch_ticker_info


def range_position_52w(
    price: float | None,
    low: float | None,
    high: float | None,
) -> float | None:
    """0 = przy dołku 52W, 1 = przy szczycie 52W."""
    if price is None or low is None or high is None or pd.isna(price):
        return None
    if high <= low:
        return None
    return max(0.0, min(1.0, (float(price) - float(low)) / (float(high) - float(low))))


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_52w_bounds(tickers: tuple[str, ...]) -> dict[str, tuple[float | None, float | None]]:
    """Mapa ticker_yahoo → (week_52_low, week_52_high)."""
    result: dict[str, tuple[float | None, float | None]] = {}
    for ticker in tickers:
        info = fetch_ticker_info(ticker)
        low = info.get("fiftyTwoWeekLow")
        high = info.get("fiftyTwoWeekHigh")
        try:
            low_f = float(low) if low is not None else None
        except (TypeError, ValueError):
            low_f = None
        try:
            high_f = float(high) if high is not None else None
        except (TypeError, ValueError):
            high_f = None
        result[ticker] = (low_f, high_f)
    return result


def enrich_52w_range(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje kolumnę range_52w (0–1) do ramki z ticker_yahoo i market_price."""
    if df is None or df.empty or "ticker_yahoo" not in df.columns:
        return df

    out = df.copy()
    tickers = tuple(sorted(out["ticker_yahoo"].dropna().astype(str).unique()))
    bounds = fetch_52w_bounds(tickers)

    positions: list[float | None] = []
    for _, row in out.iterrows():
        yahoo = str(row.get("ticker_yahoo", ""))
        low, high = bounds.get(yahoo, (None, None))
        price = row.get("market_price")
        positions.append(range_position_52w(price, low, high))

    out["range_52w"] = positions
    return out
