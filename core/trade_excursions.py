"""
MAE/MFE (Maximum Adverse/Favorable Excursion) dla zamkniętych round-tripów.

Dla każdej pozycji pobiera dzienne High/Low z Yahoo Finance w oknie
open_time → close_time i mierzy maksymalne odchylenie od ceny wejścia.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_ohlc_matrix(
    tickers: tuple[str, ...],
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Zwraca (high_matrix, low_matrix) — indeks = data, kolumny = tickery."""
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()

    highs: list[pd.Series] = []
    lows: list[pd.Series] = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(
                start=start_date,
                end=end_date,
                auto_adjust=True,
            )
            if hist.empty:
                continue
            hi = hist["High"].copy()
            lo = hist["Low"].copy()
            hi.name = ticker
            lo.name = ticker
            idx = pd.to_datetime(hi.index).tz_localize(None).normalize()
            hi.index = idx
            lo.index = idx
            highs.append(hi)
            lows.append(lo)
        except Exception:
            continue

    if not highs:
        return pd.DataFrame(), pd.DataFrame()

    high_matrix = pd.concat(highs, axis=1).sort_index().ffill()
    low_matrix = pd.concat(lows, axis=1).sort_index().ffill()
    return high_matrix, low_matrix


def _excursion_pct(
    high_matrix: pd.DataFrame,
    low_matrix: pd.DataFrame,
    ticker: str,
    open_time: pd.Timestamp,
    close_time: pd.Timestamp,
    entry_price: float,
) -> tuple[float | None, float | None]:
    """MAE % i MFE % względem ceny wejścia."""
    if entry_price <= 0 or ticker not in high_matrix.columns:
        return None, None

    start = pd.Timestamp(open_time).normalize()
    end = pd.Timestamp(close_time).normalize()
    if end < start:
        end = start

    hi = high_matrix.loc[start:end, ticker].dropna()
    lo = low_matrix.loc[start:end, ticker].dropna()
    if hi.empty or lo.empty:
        return None, None

    mfe_pct = (float(hi.max()) - entry_price) / entry_price * 100
    mae_pct = (float(lo.min()) - entry_price) / entry_price * 100
    return mae_pct, mfe_pct


def compute_mae_mfe(round_trips: pd.DataFrame) -> pd.DataFrame:
    """
    Wzbogaca round-tripy o kolumny mae_pct i mfe_pct.

    MAE — najgłębszy spadek względem wejścia (%).
    MFE — najwyższy zysk niezrealizowany w trakcie trzymania (%).
    """
    if round_trips is None or round_trips.empty:
        return pd.DataFrame()

    required = {"ticker_yahoo", "open_time", "close_time", "open_price"}
    if not required.issubset(round_trips.columns):
        return round_trips.copy()

    df = round_trips.copy()
    df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
    df["close_time"] = pd.to_datetime(df["close_time"], errors="coerce")
    valid = df.dropna(subset=["open_time", "close_time", "open_price", "ticker_yahoo"])
    if valid.empty:
        df["mae_pct"] = pd.NA
        df["mfe_pct"] = pd.NA
        return df

    tickers = tuple(sorted(valid["ticker_yahoo"].astype(str).unique()))
    start = valid["open_time"].min().strftime("%Y-%m-%d")
    end = (valid["close_time"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    high_matrix, low_matrix = _fetch_ohlc_matrix(tickers, start, end)
    if high_matrix.empty:
        df["mae_pct"] = pd.NA
        df["mfe_pct"] = pd.NA
        return df

    mae_vals: list[float | None] = []
    mfe_vals: list[float | None] = []
    for _, row in df.iterrows():
        if pd.isna(row["open_time"]) or pd.isna(row["close_time"]):
            mae_vals.append(None)
            mfe_vals.append(None)
            continue
        mae, mfe = _excursion_pct(
            high_matrix,
            low_matrix,
            str(row["ticker_yahoo"]),
            row["open_time"],
            row["close_time"],
            float(row["open_price"]),
        )
        mae_vals.append(mae)
        mfe_vals.append(mfe)

    df["mae_pct"] = mae_vals
    df["mfe_pct"] = mfe_vals
    return df
