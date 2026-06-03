"""
Dane fundamentalne z yfinance Ticker.info.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st
import yfinance as yf


@dataclass
class FundamentalsSnapshot:
    """Ustandaryzowany zestaw metryk fundamentalnych."""

    pe_ratio: float | None
    forward_pe: float | None
    market_cap: float | None
    sector: str | None
    industry: str | None
    week_52_high: float | None
    week_52_low: float | None
    target_mean_price: float | None
    current_price: float | None
    dividend_yield: float | None
    name: str | None


def _safe_float(value) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fundamentals(ticker: str) -> FundamentalsSnapshot:
    """Pobiera i mapuje pole .info z Yahoo Finance."""
    info = yf.Ticker(ticker).info or {}

    div = info.get("dividendYield")
    if div is not None and div < 1:
        div = div * 100

    return FundamentalsSnapshot(
        pe_ratio=_safe_float(info.get("trailingPE")),
        forward_pe=_safe_float(info.get("forwardPE")),
        market_cap=_safe_float(info.get("marketCap")),
        sector=info.get("sector"),
        industry=info.get("industry"),
        week_52_high=_safe_float(info.get("fiftyTwoWeekHigh")),
        week_52_low=_safe_float(info.get("fiftyTwoWeekLow")),
        target_mean_price=_safe_float(info.get("targetMeanPrice")),
        current_price=_safe_float(info.get("currentPrice") or info.get("regularMarketPrice")),
        dividend_yield=_safe_float(div),
        name=info.get("shortName") or info.get("longName"),
    )


def format_market_cap(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1e12:
        return f"{value / 1e12:.2f} bln"
    if value >= 1e9:
        return f"{value / 1e9:.2f} mld"
    if value >= 1e6:
        return f"{value / 1e6:.2f} mln"
    return f"{value:,.0f}"
