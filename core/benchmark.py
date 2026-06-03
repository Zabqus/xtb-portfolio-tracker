"""
Porównanie zwrotu pozycji z indeksem referencyjnym (S&P 500 / WIG20).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.history import PERIOD_OPTIONS, fetch_price_history

BENCHMARK_SYMBOLS: dict[str, str] = {
    "S&P 500": "^GSPC",
    "WIG20": "^WIG20",
}

BENCHMARK_FALLBACKS: dict[str, list[str]] = {
    "WIG20": ["^WIG20", "WIG20.WA", "MWIG40.WA"],
    "S&P 500": ["^GSPC", "SPY"],
}


def resolve_benchmark(ticker_xtb: str, currency: str) -> tuple[str, str]:
    """
    Wybiera benchmark: PLN/GPW → WIG20, reszta → S&P 500.
    Zwraca (nazwa, symbol Yahoo).
    """
    normalized = ticker_xtb.upper()
    if currency == "PLN" or normalized.endswith((".PL", ".WA")):
        return "WIG20", BENCHMARK_SYMBOLS["WIG20"]
    return "S&P 500", BENCHMARK_SYMBOLS["S&P 500"]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_benchmark_history(
    benchmark_name: str,
    period_label: str,
) -> pd.DataFrame:
    """Pobiera historię indeksu z fallbackami symboli."""
    fallbacks = BENCHMARK_FALLBACKS.get(benchmark_name, [BENCHMARK_SYMBOLS.get(benchmark_name, "^GSPC")])

    for symbol in fallbacks:
        df = fetch_price_history(symbol, period_label)
        if not df.empty and "Close" in df.columns:
            out = df.copy()
            out.attrs["symbol"] = symbol
            return out
    return pd.DataFrame()


def normalize_to_index(close: pd.Series) -> pd.Series:
    """Indeksuje serię do 100 w pierwszym punkcie (porównanie performance)."""
    clean = close.dropna()
    if clean.empty:
        return clean
    base = float(clean.iloc[0])
    if base == 0:
        return clean
    return clean / base * 100


def build_performance_comparison(
    ticker: str,
    period_label: str,
    benchmark_name: str | None = None,
    benchmark_symbol: str | None = None,
    ticker_xtb: str = "",
    currency: str = "EUR",
) -> tuple[pd.DataFrame, str, str]:
    """
    Łączy znormalizowane performance instrumentu i benchmarku.

    Zwraca (merged_df, bench_name, bench_symbol_used).
    """
    stock_hist = fetch_price_history(ticker, period_label)
    if stock_hist.empty:
        return pd.DataFrame(), "", ""

    if benchmark_name is None or benchmark_symbol is None:
        benchmark_name, benchmark_symbol = resolve_benchmark(ticker_xtb, currency)

    bench_hist = fetch_benchmark_history(benchmark_name, period_label)
    if bench_hist.empty:
        return pd.DataFrame(), benchmark_name, ""

    symbol_used = bench_hist.attrs.get("symbol", benchmark_symbol)

    def _daily_close(hist: pd.DataFrame) -> pd.Series:
        df = hist.copy()
        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        return df.set_index("Date")["Close"].sort_index()

    stock = _daily_close(stock_hist)
    bench = _daily_close(bench_hist)

    stock_idx = normalize_to_index(stock)
    bench_idx = normalize_to_index(bench)

    # Tylko wspólne sesje (unika pustego wyniku po dropna przy kalendarzach US/EU).
    merged = pd.concat(
        [stock_idx.rename("instrument"), bench_idx.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna(how="any")

    if merged.empty:
        return pd.DataFrame(), benchmark_name, symbol_used

    merged = merged.reset_index()
    date_col = merged.columns[0]
    if date_col != "date":
        merged = merged.rename(columns={date_col: "date"})

    return merged, benchmark_name, symbol_used
