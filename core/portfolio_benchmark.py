"""
Porównanie całego portfela (indeks TWR) z benchmarkiem rynkowym.

TWR portfela (zwrot ważony czasem, bez wpływu timingu wpłat) jest jedyną
poprawną podstawą do zestawienia z indeksem — dlatego nie używamy tu surowej
wartości rynkowej (zaburzanej dopłatami), lecz indeks wzrostu z core.returns.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

# Nazwa benchmarku → lista symboli Yahoo (kolejne to fallbacki).
PORTFOLIO_BENCHMARKS: dict[str, list[str]] = {
    "S&P 500": ["^GSPC", "SPY"],
    "MSCI World": ["URTH", "IWDA.L", "SWDA.L"],
    "NASDAQ 100": ["^NDX", "QQQ"],
    "WIG20": ["^WIG20", "WIG20.WA"],
    "STOXX Europe 600": ["^STOXX", "EXSA.DE"],
}

DEFAULT_BENCHMARK = "MSCI World"


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_close_range(
    benchmark_name: str,
    start_date: str,
    end_date: str,
) -> pd.Series:
    """Zwraca serię cen zamknięcia indeksu (indeks = data) z fallbackami symboli."""
    symbols = PORTFOLIO_BENCHMARKS.get(benchmark_name, ["^GSPC"])
    for symbol in symbols:
        try:
            hist = yf.Ticker(symbol).history(
                start=start_date,
                end=end_date,
                auto_adjust=True,
            )
        except Exception:
            continue
        if hist.empty or "Close" not in hist.columns:
            continue
        series = hist["Close"].copy()
        series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
        series.name = symbol
        return series
    return pd.Series(dtype=float)


def build_portfolio_vs_benchmark(
    twr_index: pd.DataFrame,
    benchmark_name: str,
) -> pd.DataFrame:
    """
    Łączy indeks TWR portfela z indeksem benchmarku (oba rebazowane do 100).

    twr_index: DataFrame z kolumnami date, twr_index (start = 100).
    Zwraca DataFrame: date, portfolio, benchmark (None gdy brak danych).
    """
    if twr_index is None or twr_index.empty:
        return pd.DataFrame()

    port = twr_index.dropna(subset=["date", "twr_index"]).copy()
    port["date"] = pd.to_datetime(port["date"]).dt.normalize()
    port = port.sort_values("date")
    if port.empty:
        return pd.DataFrame()

    start = port["date"].iloc[0]
    end = port["date"].iloc[-1]

    bench = fetch_index_close_range(
        benchmark_name,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=(end + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
    )

    merged = port.rename(columns={"twr_index": "portfolio"})[["date", "portfolio"]]

    if not bench.empty:
        # Reindeks na daty portfela (kalendarz dzienny), ffill weekendy/święta.
        bench_on_dates = bench.reindex(
            pd.DatetimeIndex(port["date"])
        ).ffill()
        first_valid = bench_on_dates.dropna()
        if not first_valid.empty:
            base = float(first_valid.iloc[0])
            if base > 0:
                bench_idx = bench_on_dates / base * 100.0
                merged["benchmark"] = bench_idx.values

    return merged.reset_index(drop=True)


def relative_performance(merged: pd.DataFrame) -> dict[str, float] | None:
    """Końcowe wartości indeksów i różnica portfel − benchmark (w punktach %)."""
    if merged is None or merged.empty or "benchmark" not in merged.columns:
        return None
    valid = merged.dropna(subset=["portfolio", "benchmark"])
    if valid.empty:
        return None
    port_end = float(valid["portfolio"].iloc[-1])
    bench_end = float(valid["benchmark"].iloc[-1])
    return {
        "portfolio_pct": port_end - 100.0,
        "benchmark_pct": bench_end - 100.0,
        "alpha_pct": port_end - bench_end,
    }
