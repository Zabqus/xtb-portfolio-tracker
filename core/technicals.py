"""
Wskaźniki techniczne — MA, RSI, MACD, Bollinger Bands.

Kolejność silników: pandas_ta → TA-Lib (opcjonalnie) → czysty pandas.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.history import PERIOD_OPTIONS, fetch_price_history

COL_MA20 = "MA20"
COL_MA50 = "MA50"
COL_MA200 = "MA200"
COL_RSI = "RSI14"
COL_MACD = "MACD"
COL_MACD_SIGNAL = "MACD_signal"
COL_MACD_HIST = "MACD_hist"
COL_BB_LOWER = "BB_lower"
COL_BB_MID = "BB_mid"
COL_BB_UPPER = "BB_upper"

try:
    import pandas_ta as ta

    HAS_PANDAS_TA = True
except ImportError:
    ta = None
    HAS_PANDAS_TA = False

try:
    import talib

    HAS_TALIB = True
except ImportError:
    talib = None
    HAS_TALIB = False


def engine_name() -> str:
    if HAS_PANDAS_TA:
        return "pandas_ta"
    if HAS_TALIB:
        return "TA-Lib"
    return "pandas (fallback)"


def _ohlcv_frame(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()

    df = history.copy()
    if "Date" in df.columns:
        df = df.set_index("Date")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.sort_index()


def _apply_pandas_ta(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"]

    df[COL_MA20] = ta.sma(close, length=20)
    df[COL_MA50] = ta.sma(close, length=50)
    df[COL_MA200] = ta.sma(close, length=200)
    df[COL_RSI] = ta.rsi(close, length=14)

    macd = ta.macd(close, fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        macd_cols = list(macd.columns)
        df[COL_MACD] = macd[macd_cols[0]]
        df[COL_MACD_HIST] = macd[macd_cols[1]] if len(macd_cols) > 1 else None
        df[COL_MACD_SIGNAL] = macd[macd_cols[2]] if len(macd_cols) > 2 else None

    bb = ta.bbands(close, length=20, std=2)
    if bb is not None and not bb.empty:
        bb_cols = list(bb.columns)
        df[COL_BB_LOWER] = bb[bb_cols[0]]
        df[COL_BB_MID] = bb[bb_cols[1]] if len(bb_cols) > 1 else ta.sma(close, length=20)
        df[COL_BB_UPPER] = bb[bb_cols[2]] if len(bb_cols) > 2 else None

    return df


def _apply_pandas_native(df: pd.DataFrame) -> pd.DataFrame:
    """Czysty pandas — te same wskaźniki bez pandas_ta."""
    close = df["Close"]

    df[COL_MA20] = close.rolling(20, min_periods=1).mean()
    df[COL_MA50] = close.rolling(50, min_periods=1).mean()
    df[COL_MA200] = close.rolling(200, min_periods=1).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=1).mean()
    rs = gain / loss.replace(0, pd.NA)
    df[COL_RSI] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    df[COL_MACD] = macd_line
    df[COL_MACD_SIGNAL] = signal
    df[COL_MACD_HIST] = macd_line - signal

    mid = close.rolling(20, min_periods=1).mean()
    std = close.rolling(20, min_periods=1).std()
    df[COL_BB_MID] = mid
    df[COL_BB_LOWER] = mid - 2 * std
    df[COL_BB_UPPER] = mid + 2 * std

    return df


def _apply_talib(df: pd.DataFrame) -> pd.DataFrame:
    close = df["Close"].astype(float).values

    df[COL_MA20] = talib.SMA(close, timeperiod=20)
    df[COL_MA50] = talib.SMA(close, timeperiod=50)
    df[COL_MA200] = talib.SMA(close, timeperiod=200)
    df[COL_RSI] = talib.RSI(close, timeperiod=14)

    macd, signal, hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    df[COL_MACD] = macd
    df[COL_MACD_SIGNAL] = signal
    df[COL_MACD_HIST] = hist

    upper, mid, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    df[COL_BB_UPPER] = upper
    df[COL_BB_MID] = mid
    df[COL_BB_LOWER] = lower

    return df


def enrich_with_technicals(history: pd.DataFrame) -> pd.DataFrame:
    df = _ohlcv_frame(history)
    if df.empty or "Close" not in df.columns:
        return pd.DataFrame()

    if HAS_PANDAS_TA:
        df = _apply_pandas_ta(df)
    elif HAS_TALIB:
        df = _apply_talib(df)
    else:
        df = _apply_pandas_native(df)

    return df.reset_index().rename(columns={"index": "Date"})


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_technicals(ticker: str, period_label: str) -> pd.DataFrame:
    if period_label not in PERIOD_OPTIONS:
        raise ValueError(f"Unsupported period: {period_label}")
    history = fetch_price_history(ticker, period_label)
    return enrich_with_technicals(history)


def latest_indicator_snapshot(df: pd.DataFrame) -> dict[str, float | str | None]:
    if df.empty:
        return {}

    last = df.dropna(subset=["Close"]).iloc[-1] if "Close" in df.columns else df.iloc[-1]
    close = float(last["Close"]) if pd.notna(last.get("Close")) else None

    def _f(col: str) -> float | None:
        if col not in last.index or pd.isna(last[col]):
            return None
        return float(last[col])

    ma200 = _f(COL_MA200)
    trend = "—"
    if close is not None and ma200 is not None:
        trend = "Powyżej MA200 ▲" if close > ma200 else "Poniżej MA200 ▼"

    rsi = _f(COL_RSI)
    rsi_zone = "—"
    if rsi is not None:
        if rsi >= 70:
            rsi_zone = "Wykupienie (≥70)"
        elif rsi <= 30:
            rsi_zone = "Wyprzedanie (≤30)"
        else:
            rsi_zone = "Neutralnie"

    return {
        "close": close,
        "ma20": _f(COL_MA20),
        "ma50": _f(COL_MA50),
        "ma200": ma200,
        "trend_ma200": trend,
        "rsi": rsi,
        "rsi_zone": rsi_zone,
        "macd": _f(COL_MACD),
        "macd_signal": _f(COL_MACD_SIGNAL),
        "bb_lower": _f(COL_BB_LOWER),
        "bb_upper": _f(COL_BB_UPPER),
        "engine": engine_name(),
    }
