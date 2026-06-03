"""Formatowanie wartości wyświetlanych w UI (teksty po polsku)."""

from __future__ import annotations

import pandas as pd


def format_currency(value: float, currency: str) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.2f} {currency}"


def pnl_delta_color(value: float) -> str:
    """Kolor metryki Streamlit: zysk = normal, strata = inverse."""
    if pd.isna(value) or value == 0:
        return "off"
    return "normal" if value > 0 else "inverse"
