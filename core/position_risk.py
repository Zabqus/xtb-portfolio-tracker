"""
Dane do mapy ryzyka pozycji: waga, ROI, zmienność 90d, sektor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from core.allocation import enrich_portfolio_allocation
from core.history import fetch_price_history

VOL_WINDOW_DAYS = 90


@st.cache_data(ttl=3600, show_spinner=False)
def _position_volatility_90d(tickers: tuple[str, ...]) -> dict[str, float]:
    """Roczna zmienność (%) z ostatnich ~90 dni handlowych."""
    result: dict[str, float] = {}
    for ticker in tickers:
        try:
            hist = fetch_price_history(ticker, "1Y")
        except Exception:
            continue
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        close = hist["Close"].dropna()
        if len(close) < 20:
            continue
        tail = close.tail(VOL_WINDOW_DAYS)
        daily_ret = tail.pct_change().dropna()
        if daily_ret.empty or daily_ret.std() == 0:
            continue
        result[ticker] = float(daily_ret.std() * np.sqrt(252) * 100)
    return result


def build_position_risk_data(analyzed: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame: ticker, weight_pct, roi_pct, vol_90d_pct, sector, market_value.
    """
    enriched = enrich_portfolio_allocation(analyzed)
    if enriched.empty:
        return pd.DataFrame()

    tickers = tuple(sorted(enriched["ticker_yahoo"].astype(str).unique()))
    vol_map = _position_volatility_90d(tickers)

    rows: list[dict] = []
    for _, row in enriched.iterrows():
        yahoo = str(row["ticker_yahoo"])
        analyzed_row = analyzed[analyzed["ticker_yahoo"] == yahoo]
        roi = float(analyzed_row["roi_pct"].iloc[0]) if not analyzed_row.empty else 0.0
        vol = vol_map.get(yahoo)
        rows.append(
            {
                "ticker": row.get("ticker_xtb", yahoo),
                "ticker_yahoo": yahoo,
                "weight_pct": float(row["weight_pct"]),
                "roi_pct": roi,
                "vol_90d_pct": vol,
                "sector": row.get("sector", "Brak sektora"),
                "market_value": float(row["market_value"]),
            }
        )

    return pd.DataFrame(rows)
