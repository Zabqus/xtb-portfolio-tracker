"""
Moduł analityczny portfela – pobieranie cen rynkowych i wyliczanie wyników.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf


def _fetch_last_prices(tickers: list[str]) -> dict[str, float]:
    """
    Pobiera ostatnie dostępne ceny zamknięcia dla listy symboli Yahoo.
    Zwraca słownik {ticker: cena}; brak danych oznacza wartość NaN.
    """
    unique_tickers = sorted(set(tickers))
    if not unique_tickers:
        return {}

    # Pobranie wsadowe – szybsze niż pojedyncze zapytania
    data = yf.download(
        unique_tickers,
        period="5d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    prices: dict[str, float] = {}

    if len(unique_tickers) == 1:
        ticker = unique_tickers[0]
        if not data.empty and "Close" in data.columns:
            prices[ticker] = float(data["Close"].dropna().iloc[-1])
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


def analyze_portfolio(portfolio: pd.DataFrame) -> pd.DataFrame:
    """
    Wzbogaca portfel o ceny rynkowe oraz metryki zysku/straty.

    Wymagane kolumny wejściowe: ticker_yahoo, ilosc, srednia_cena
    (opcjonalnie ticker_xtb do wyświetlania).

    Dodaje kolumny:
        - cena_rynkowa
        - koszt_pozycji (ilość × średnia cena)
        - wartosc_rynkowa
        - zysk_strata (kwotowo)
        - roi_pct (zwrot procentowy)
    """
    required = {"ticker_yahoo", "ilosc", "srednia_cena"}
    if not required.issubset(portfolio.columns):
        raise ValueError(f"Brak wymaganych kolumn portfela: {required - set(portfolio.columns)}")

    result = portfolio.copy()
    price_map = _fetch_last_prices(result["ticker_yahoo"].tolist())
    result["cena_rynkowa"] = result["ticker_yahoo"].map(price_map)

    result["koszt_pozycji"] = result["ilosc"] * result["srednia_cena"]
    result["wartosc_rynkowa"] = result["ilosc"] * result["cena_rynkowa"]
    result["zysk_strata"] = result["wartosc_rynkowa"] - result["koszt_pozycji"]
    result["roi_pct"] = (
        (result["zysk_strata"] / result["koszt_pozycji"]) * 100
    ).where(result["koszt_pozycji"] > 0)

    return result


def portfolio_summary(analyzed: pd.DataFrame) -> dict[str, float]:
    """Zwraca zagregowane metryki całego portfela."""
    valid = analyzed.dropna(subset=["wartosc_rynkowa", "koszt_pozycji"])
    total_value = valid["wartosc_rynkowa"].sum()
    total_cost = valid["koszt_pozycji"].sum()
    total_pnl = total_value - total_cost
    total_roi = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "wartosc_calkowita": float(total_value),
        "koszt_calkowity": float(total_cost),
        "zysk_strata_laczny": float(total_pnl),
        "roi_laczny_pct": float(total_roi),
    }
