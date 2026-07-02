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

RATING_SCORES: dict[str, int] = {
    "strong_buy": 5,
    "buy": 4,
    "hold": 3,
    "underperform": 2,
    "sell": 1,
    "strong_sell": 0,
}

RATING_COLORS: dict[str, str] = {
    "strong_buy": "#1a9850",
    "buy": "#66bd63",
    "hold": "#fdae61",
    "underperform": "#f46d43",
    "sell": "#d73027",
    "strong_sell": "#a50026",
}

RATING_BUCKETS: dict[str, str] = {
    "strong_buy": "Kupno",
    "buy": "Kupno",
    "hold": "Trzymaj",
    "underperform": "Sprzedaj",
    "sell": "Sprzedaj",
    "strong_sell": "Sprzedaj",
}


@dataclass
class AnalystConsensus:
    target_mean_price: float | None
    target_low_price: float | None
    target_high_price: float | None
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


def normalize_rating_key(key: str | None) -> str:
    if not key:
        return ""
    return key.strip().lower().replace(" ", "_")


def format_recommendation(key: str | None) -> str:
    if not key:
        return "—"
    normalized = normalize_rating_key(key)
    return RECOMMENDATION_LABELS_PL.get(normalized, key.replace("_", " ").title())


def rating_score(key: str | None) -> int | None:
    normalized = normalize_rating_key(key)
    if not normalized:
        return None
    return RATING_SCORES.get(normalized)


def rating_bucket(key: str | None) -> str | None:
    normalized = normalize_rating_key(key)
    if not normalized:
        return None
    return RATING_BUCKETS.get(normalized, "Trzymaj")


def rating_color(key: str | None) -> str:
    normalized = normalize_rating_key(key)
    return RATING_COLORS.get(normalized, "#94a3b8")


def rating_momentum_label(prev_key: str | None, curr_key: str | None) -> str:
    """Strzałka zmiany ratingu od ostatniego snapshotu."""
    prev = rating_score(prev_key)
    curr = rating_score(curr_key)
    if prev is None or curr is None:
        return "—"
    if curr > prev:
        return "↑"
    if curr < prev:
        return "↓"
    return "→"


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
        target_low_price=_safe_float(info.get("targetLowPrice")),
        target_high_price=_safe_float(info.get("targetHighPrice")),
        recommendation_key=info.get("recommendationKey"),
        number_of_analyst_opinions=_safe_int(info.get("numberOfAnalystOpinions")),
        current_price=_safe_float(
            info.get("currentPrice") or info.get("regularMarketPrice")
        ),
    )
