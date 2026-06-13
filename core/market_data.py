"""
Pobieranie danych rynkowych z Yahoo Finance (cache Streamlit).
"""

from __future__ import annotations

import time

import streamlit as st
import yfinance as yf

# Pary Yahoo: ile PLN za 1 jednostkę waluty
YAHOO_PLN_PAIR: dict[str, str] = {
    "EUR": "EURPLN=X",
    "USD": "USDPLN=X",
    "GBP": "GBPPLN=X",
    "CHF": "CHFPLN=X",
}

# Czas ostatniego realnego pobrania danych (nie z cache)
_last_fetch_ts: dict[str, float] = {}


def record_fetch_time(key: str = "prices") -> None:
    _last_fetch_ts[key] = time.time()


def get_fetch_age_seconds(key: str = "prices") -> float | None:
    ts = _last_fetch_ts.get(key)
    return (time.time() - ts) if ts else None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_last_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    """
    Pobiera ostatnie ceny zamknięcia dla listy symboli Yahoo.
    Tuple w sygnaturze – wymagane przez @st.cache_data (hashable).
    """
    unique_tickers = sorted(set(tickers))
    if not unique_tickers:
        return {}

    data = yf.download(
        list(unique_tickers),
        period="5d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    record_fetch_time("prices")

    prices: dict[str, float] = {}

    if len(unique_tickers) == 1:
        ticker = unique_tickers[0]
        if not data.empty and "Close" in data.columns:
            close = data["Close"].dropna()
            prices[ticker] = float(close.iloc[-1]) if len(close) else float("nan")
        else:
            prices[ticker] = float("nan")
        return prices

    for ticker in unique_tickers:
        try:
            ticker_data = data[ticker]
            close_series = ticker_data["Close"].dropna()
            prices[ticker] = float(close_series.iloc[-1]) if not close_series.empty else float("nan")
        except (KeyError, TypeError):
            prices[ticker] = float("nan")

    return prices


def fetch_fx_rate_to_pln_cached(currency: str, pln_cache: dict[str, float]) -> float:
    """Wrapper z lokalnym cache w ramach jednego żądania analizy."""
    if currency in pln_cache:
        return pln_cache[currency]
    if currency == "PLN":
        pln_cache["PLN"] = 1.0
        return 1.0
    rate = _fetch_single_fx_to_pln(currency)
    pln_cache[currency] = rate
    return rate


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_single_fx_to_pln(currency: str) -> float:
    """Pojedynczy kurs waluty do PLN (cache Streamlit)."""
    symbol = YAHOO_PLN_PAIR.get(currency)
    if not symbol:
        raise ValueError(f"Brak pary kursowej do PLN dla waluty: {currency}")
    hist = yf.Ticker(symbol).history(period="5d")
    if hist.empty:
        raise ValueError(f"Brak kursu FX: {symbol}")
    return float(hist["Close"].iloc[-1])
