"""
Konsensus analityków z yfinance Ticker.info:
targetMeanPrice, recommendationKey, numberOfAnalystOpinions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from core.fundamentals import fetch_ticker_info

RECOMMENDATION_LABELS_PL: dict[str, str] = {
    "strong_buy": "Silne kupno",
    "buy": "Kupno",
    "hold": "Trzymaj",
    "underperform": "Słabo",
    "sell": "Sprzedaj",
    "strong_sell": "Silna sprzedaż",
    "none": "Brak rekomendacji",
}


@dataclass
class AnalystConsensus:
    target_mean_price: float | None
    recommendation_key: str | None
    number_of_analyst_opinions: int | None
    current_price: float | None

    @property
    def upside_pct(self) -> float | None:
        if self.target_mean_price is None or self.current_price is None:
            return None
        if self.current_price == 0:
            return None
        return (self.target_mean_price / self.current_price - 1) * 100

    @property
    def has_data(self) -> bool:
        return any(
            v is not None
            for v in (
                self.target_mean_price,
                self.recommendation_key,
                self.number_of_analyst_opinions,
            )
        )


def _safe_float(value) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def format_recommendation(key: str | None) -> str:
    if not key:
        return "—"
    normalized = key.strip().lower().replace(" ", "_")
    return RECOMMENDATION_LABELS_PL.get(normalized, key.replace("_", " ").title())


def recommendation_tone(key: str | None) -> str:
    """Streamlit: normal | off | inverse."""
    if not key:
        return "off"
    k = key.strip().lower()
    if k in ("strong_buy", "buy"):
        return "normal"
    if k in ("sell", "strong_sell", "underperform"):
        return "inverse"
    return "off"


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_analyst_consensus(ticker: str) -> AnalystConsensus:
    info = fetch_ticker_info(ticker)
    return AnalystConsensus(
        target_mean_price=_safe_float(info.get("targetMeanPrice")),
        recommendation_key=info.get("recommendationKey"),
        number_of_analyst_opinions=_safe_int(info.get("numberOfAnalystOpinions")),
        current_price=_safe_float(
            info.get("currentPrice") or info.get("regularMarketPrice")
        ),
    )
