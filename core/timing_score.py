"""
Ocena timingu wejścia – percentyl ceny zakupu względem zakresu ±3 miesiące.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.history import fetch_recent_window


@dataclass
class TimingScore:
    percentile: float
    range_low: float
    range_high: float
    entry_price: float
    window_months: int
    label: str
    hint: str


def compute_timing_score(
    ticker: str,
    entry_price: float,
    window_months: int = 3,
) -> TimingScore | None:
    """
    Wylicza percentyl średniej ceny zakupu vs zakres High/Low z ostatnich N miesięcy.

    0% = blisko dołka zakresu, 100% = blisko szczytu.
    """
    if entry_price <= 0 or pd.isna(entry_price):
        return None

    window = fetch_recent_window(ticker, months=window_months)
    if window.empty or "Close" not in window.columns:
        return None

    prices = window["Close"].dropna()
    if prices.empty:
        return None

    low = float(prices.min())
    high = float(prices.max())
    if high <= low:
        percentile = 50.0
    else:
        percentile = (float(entry_price) - low) / (high - low) * 100
        percentile = max(0.0, min(100.0, percentile))

    label, hint = _interpret_percentile(percentile)

    return TimingScore(
        percentile=percentile,
        range_low=low,
        range_high=high,
        entry_price=float(entry_price),
        window_months=window_months,
        label=label,
        hint=hint,
    )


def _interpret_percentile(pct: float) -> tuple[str, str]:
    if pct <= 25:
        return "Blisko dołka", "Kupiłeś w dolnej części zakresu 3M — dobry timing wejścia."
    if pct <= 50:
        return "Poniżej środka", "Cena zakupu jest niższa niż większość notowań z ostatnich 3 miesięcy."
    if pct <= 75:
        return "Powyżej środka", "Kupiłeś powyżej mediany zakresu — wejście raczej droższe."
    return "Blisko szczytu", "Kupiłeś w górnej części zakresu 3M — słabszy timing wejścia."
