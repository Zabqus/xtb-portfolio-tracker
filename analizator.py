"""
Moduł analityczny portfela – pobieranie cen rynkowych i wyliczanie wyników.
Obsługuje wielowalutowy portfel z przeliczeniem na wybraną walutę wyświetlania.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from waluty import pobierz_kursy_do_waluty, przelicz_kwote


def _fetch_last_prices(tickers: list[str]) -> dict[str, float]:
    """
    Pobiera ostatnie dostępne ceny zamknięcia dla listy symboli Yahoo.
    Zwraca słownik {ticker: cena}; brak danych oznacza wartość NaN.
    """
    unique_tickers = sorted(set(tickers))
    if not unique_tickers:
        return {}

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


def analyze_portfolio(
    portfolio: pd.DataFrame,
    waluta_wyswietlania: str | None = None,
) -> pd.DataFrame:
    """
    Wzbogaca portfel o ceny rynkowe oraz metryki zysku/straty.

    Wartości w walucie instrumentu trafiają do kolumn *_waluta.
    Po przeliczeniu FX – kolumny koszt_pozycji, wartosc_rynkowa, zysk_strata (w walucie wyświetlania).
    """
    required = {"ticker_yahoo", "ilosc", "srednia_cena"}
    if not required.issubset(portfolio.columns):
        raise ValueError(f"Brak wymaganych kolumn portfela: {required - set(portfolio.columns)}")

    waluta_konta = portfolio.attrs.get("waluta_konta", "EUR")
    docelowa = (waluta_wyswietlania or waluta_konta).upper()

    result = portfolio.copy()
    if "waluta" not in result.columns:
        result["waluta"] = waluta_konta

    price_map = _fetch_last_prices(result["ticker_yahoo"].tolist())
    result["cena_rynkowa"] = result["ticker_yahoo"].map(price_map)

    # Wartości w oryginalnej walucie notowań instrumentu
    result["koszt_waluta"] = result["ilosc"] * result["srednia_cena"]
    result["wartosc_waluta"] = result["ilosc"] * result["cena_rynkowa"]
    result["zysk_waluta"] = result["wartosc_waluta"] - result["koszt_waluta"]

    waluty = set(result["waluta"].dropna().unique()) | {docelowa}
    kursy = pobierz_kursy_do_waluty(waluty, docelowa)

    result["koszt_pozycji"] = result.apply(
        lambda r: przelicz_kwote(r["koszt_waluta"], r["waluta"], docelowa, kursy),
        axis=1,
    )
    result["wartosc_rynkowa"] = result.apply(
        lambda r: przelicz_kwote(r["wartosc_waluta"], r["waluta"], docelowa, kursy),
        axis=1,
    )
    result["zysk_strata"] = result["wartosc_rynkowa"] - result["koszt_pozycji"]
    result["roi_pct"] = (
        (result["zysk_strata"] / result["koszt_pozycji"]) * 100
    ).where(result["koszt_pozycji"] > 0)

    result.attrs["waluta_konta"] = waluta_konta
    result.attrs["waluta_wyswietlania"] = docelowa
    result.attrs["kursy_fx"] = kursy
    return result


def portfolio_summary(analyzed: pd.DataFrame) -> dict[str, float | str]:
    """Zwraca zagregowane metryki całego portfela w walucie wyświetlania."""
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
        "waluta_wyswietlania": analyzed.attrs.get("waluta_wyswietlania", "PLN"),
        "waluta_konta": analyzed.attrs.get("waluta_konta", "PLN"),
    }
