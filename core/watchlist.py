"""
Watchlist – symbole spoza portfela, zwroty okresowe i porównanie z portfelem.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

from core.benchmark import normalize_to_index
from core.history import PERIOD_OPTIONS, fetch_price_history
from core.importer_maps import map_ticker_to_yahoo
from core.market_data import fetch_last_prices

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = PROJECT_ROOT / "watchlist.json"

WATCHLIST_PERIOD_MAP: dict[str, str] = {
    "1M": "1mo",
    "3M": "3mo",
    "1Y": "1y",
}
COMPARE_PERIODS = tuple(WATCHLIST_PERIOD_MAP.keys())


@dataclass
class WatchlistEntry:
    """Pozycja zapisana przez użytkownika (symbol wejściowy + Yahoo)."""

    symbol: str
    yahoo: str
    added_at: str

    @classmethod
    def from_symbol(cls, raw: str) -> WatchlistEntry:
        symbol = str(raw).strip().upper()
        if not symbol:
            raise ValueError("Pusty symbol.")
        yahoo = map_ticker_to_yahoo(symbol)
        return cls(
            symbol=symbol,
            yahoo=yahoo,
            added_at=datetime.now(timezone.utc).isoformat(),
        )


def resolve_watchlist_symbol(raw: str) -> str:
    """Mapuje symbol XTB / Yahoo na ticker Yahoo."""
    return map_ticker_to_yahoo(str(raw).strip().upper())


def load_watchlist_file() -> list[WatchlistEntry]:
    if not WATCHLIST_PATH.exists():
        return []
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries: list[WatchlistEntry] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip().upper()
        yahoo = str(item.get("yahoo", "")).strip()
        if not symbol or not yahoo:
            continue
        entries.append(
            WatchlistEntry(
                symbol=symbol,
                yahoo=yahoo,
                added_at=str(item.get("added_at", "")),
            )
        )
    return entries


def save_watchlist_file(entries: list[WatchlistEntry]) -> None:
    payload = [asdict(e) for e in entries]
    WATCHLIST_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def portfolio_yahoo_set(open_positions: pd.DataFrame | None) -> set[str]:
    if open_positions is None or open_positions.empty:
        return set()
    if "ticker_yahoo" not in open_positions.columns:
        return set()
    return set(open_positions["ticker_yahoo"].dropna().astype(str).str.upper())


def portfolio_xtb_set(open_positions: pd.DataFrame | None) -> set[str]:
    if open_positions is None or open_positions.empty:
        return set()
    col = "ticker_xtb" if "ticker_xtb" in open_positions.columns else "ticker_yahoo"
    return set(open_positions[col].dropna().astype(str).str.upper())


def is_in_portfolio(entry: WatchlistEntry, open_positions: pd.DataFrame | None) -> bool:
    yahoo_set = portfolio_yahoo_set(open_positions)
    xtb_set = portfolio_xtb_set(open_positions)
    return entry.yahoo.upper() in yahoo_set or entry.symbol.upper() in xtb_set


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_watchlist_history(ticker: str, period_label: str) -> pd.DataFrame:
    period = WATCHLIST_PERIOD_MAP.get(period_label) or PERIOD_OPTIONS.get(period_label)
    if not period:
        return pd.DataFrame()
    hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if hist.empty:
        return pd.DataFrame()
    df = hist.reset_index()
    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], utc=True).dt.tz_localize(None)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def _period_return_pct(ticker: str, period_label: str) -> float | None:
    """Zwrot procentowy od pierwszego do ostatniego zamknięcia w okresie."""
    if period_label not in WATCHLIST_PERIOD_MAP and period_label not in PERIOD_OPTIONS:
        return None
    if period_label in WATCHLIST_PERIOD_MAP:
        hist = _fetch_watchlist_history(ticker, period_label)
    else:
        hist = fetch_price_history(ticker, period_label)
    if hist.empty or "Close" not in hist.columns:
        return None
    close = hist["Close"].dropna()
    if len(close) < 2:
        return None
    base = float(close.iloc[0])
    last = float(close.iloc[-1])
    if base == 0:
        return None
    return (last / base - 1.0) * 100.0


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_watchlist_returns(
    tickers: tuple[str, ...],
    period_label: str,
) -> dict[str, float | None]:
    return {t: _period_return_pct(t, period_label) for t in tickers}


def build_watchlist_table(
    entries: list[WatchlistEntry],
    analyzed: pd.DataFrame | None,
    period_label: str,
) -> pd.DataFrame:
    """Tabela watchlisty z ceną, zwrotem i różnicą vs średnia ważona portfela."""
    if not entries:
        return pd.DataFrame()

    open_positions = analyzed
    tickers = tuple(sorted({e.yahoo for e in entries}))
    prices = fetch_last_prices(tickers)
    returns = fetch_watchlist_returns(tickers, period_label)
    port_return = portfolio_weighted_return_from_analyzed(analyzed, period_label)

    rows: list[dict] = []
    for entry in entries:
        ret = returns.get(entry.yahoo)
        in_port = is_in_portfolio(entry, open_positions)
        vs_port = (ret - port_return) if ret is not None and port_return is not None else None
        rows.append(
            {
                "symbol": entry.symbol,
                "yahoo": entry.yahoo,
                "market_price": prices.get(entry.yahoo),
                f"return_{period_label}": ret,
                "vs_portfolio_pct": vs_port,
                "in_portfolio": in_port,
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def portfolio_weighted_return(
    tickers_tuple: tuple[str, ...],
    weights_tuple: tuple[float, ...],
    period_label: str,
) -> float | None:
    """Średnia ważona zwrotów otwartych pozycji (po symbolu Yahoo)."""
    if not tickers_tuple or sum(weights_tuple) <= 0:
        return None
    rets = fetch_watchlist_returns(tickers_tuple, period_label)
    total_w = 0.0
    acc = 0.0
    for t, w in zip(tickers_tuple, weights_tuple, strict=True):
        r = rets.get(t)
        if r is None or w <= 0:
            continue
        acc += w * r
        total_w += w
    if total_w <= 0:
        return None
    return acc / total_w


def portfolio_weighted_return_from_analyzed(
    analyzed: pd.DataFrame | None,
    period_label: str,
) -> float | None:
    if analyzed is None or analyzed.empty:
        return None
    valid = analyzed.dropna(subset=["ticker_yahoo", "market_value"])
    valid = valid[valid["market_value"] > 0]
    if valid.empty:
        return None
    tickers = tuple(valid["ticker_yahoo"].astype(str).tolist())
    weights = tuple(valid["market_value"].astype(float).tolist())
    return portfolio_weighted_return(tickers, weights, period_label)


@st.cache_data(ttl=3600, show_spinner=False)
def build_normalized_comparison(
    watchlist_yahoo: tuple[str, ...],
    portfolio_yahoo: tuple[str, ...],
    period_label: str,
) -> pd.DataFrame:
    """
    Wspólna oś czasu: znormalizowane performance (baza 100)
    dla watchlisty i średniej portfela (equal-weight blend pozycji).
    """
    symbols = tuple(sorted(set(watchlist_yahoo) | set(portfolio_yahoo)))
    valid_periods = set(WATCHLIST_PERIOD_MAP) | set(PERIOD_OPTIONS)
    if not symbols or period_label not in valid_periods:
        return pd.DataFrame()

    series_map: dict[str, pd.Series] = {}
    for sym in symbols:
        if period_label in WATCHLIST_PERIOD_MAP:
            hist = _fetch_watchlist_history(sym, period_label)
        else:
            hist = fetch_price_history(sym, period_label)
        if hist.empty:
            continue
        df = hist.copy()
        df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
        close = df.set_index("Date")["Close"].sort_index().dropna()
        if close.empty:
            continue
        series_map[sym] = normalize_to_index(close)

    if not series_map:
        return pd.DataFrame()

    merged = pd.concat(series_map, axis=1, join="inner").dropna(how="any")
    if merged.empty:
        return pd.DataFrame()

    out = merged.reset_index()
    date_col = out.columns[0]
    if date_col != "date":
        out = out.rename(columns={date_col: "date"})

    port_cols = [c for c in portfolio_yahoo if c in merged.columns]
    wl_cols = [c for c in watchlist_yahoo if c in merged.columns]

    if port_cols:
        out["portfel (śr.)"] = merged[port_cols].mean(axis=1).values
    if wl_cols:
        out["watchlista (śr.)"] = merged[wl_cols].mean(axis=1).values

    return out
