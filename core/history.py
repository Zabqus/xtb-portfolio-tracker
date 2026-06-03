"""
Historyczne notowania z Yahoo Finance (cena + wolumen).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

PERIOD_OPTIONS: dict[str, str] = {
    "1Y": "1y",
    "3Y": "3y",
    "5Y": "5y",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_history(ticker: str, period_label: str) -> pd.DataFrame:
    """
    Pobiera historię OHLCV dla tickera Yahoo.

    period_label: 1Y | 3Y | 5Y
    """
    if period_label not in PERIOD_OPTIONS:
        raise ValueError(f"Unsupported period: {period_label}")

    period = PERIOD_OPTIONS[period_label]
    hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)

    if hist.empty:
        return pd.DataFrame()

    df = hist.reset_index()
    if "Date" not in df.columns and "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_recent_window(ticker: str, months: int = 3) -> pd.DataFrame:
    """Okno ±N miesięcy (używane do timing score) – pobiera trochę więcej danych."""
    hist = yf.Ticker(ticker).history(period=f"{max(months, 6)}mo", auto_adjust=True)
    if hist.empty:
        return pd.DataFrame()

    df = hist.reset_index()
    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
    cutoff = df["Date"].max() - pd.DateOffset(months=months)
    return df[df["Date"] >= cutoff].copy()
