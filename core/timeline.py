"""
Rekonstrukcja wartości portfela w czasie na podstawie Cash Operations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from core.transactions import parse_cash_operations_trades

MIN_POSITION_QTY = 1e-6


def _apply_trade(holdings: dict[str, float], costs: dict[str, float], row: pd.Series) -> None:
    """Aktualizuje stan pozycji po transakcji (średnia ważona kosztu)."""
    ticker = row["ticker_yahoo"]
    qty = float(row["quantity"])
    price = float(row["price"])
    side = row["side"]

    if ticker not in holdings:
        holdings[ticker] = 0.0
        costs[ticker] = 0.0

    if side == "OPEN":
        holdings[ticker] += qty
        costs[ticker] += qty * price
    else:
        if holdings[ticker] <= MIN_POSITION_QTY:
            return
        avg = costs[ticker] / holdings[ticker]
        close_qty = min(qty, holdings[ticker])
        holdings[ticker] -= close_qty
        costs[ticker] -= close_qty * avg
        if holdings[ticker] <= MIN_POSITION_QTY:
            holdings[ticker] = 0.0
            costs[ticker] = 0.0


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_close_matrix(
    tickers: tuple[str, ...],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Macierz cen zamknięcia: indeks = data, kolumny = tickery Yahoo.
    Pobiera tickery pojedynczo (stabilniejsze przy mieszanych rynkach).
    """
    if not tickers:
        return pd.DataFrame()

    closes: list[pd.Series] = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(
                start=start_date,
                end=end_date,
                auto_adjust=True,
            )
            if hist.empty or "Close" not in hist.columns:
                continue
            series = hist["Close"].copy()
            series.name = ticker
            series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
            closes.append(series)
        except Exception:
            continue

    if not closes:
        return pd.DataFrame()

    matrix = pd.concat(closes, axis=1).sort_index()
    return matrix.ffill()


def build_portfolio_timeline(cash_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Buduje dzienny timeline: market_value, cost_basis, position_count.

    Wartość rynkowa = suma (ilość × cena zamknięcia) dla otwartych pozycji.
    """
    trades = parse_cash_operations_trades(cash_ops)
    if trades.empty:
        return pd.DataFrame()

    start = trades["trade_date"].min()
    end = trades["trade_date"].max()
    calendar = pd.date_range(start, end, freq="D")

    holdings: dict[str, float] = {}
    costs: dict[str, float] = {}
    last_prices: dict[str, float] = {}
    snapshots: list[dict] = []

    trade_by_date = trades.groupby("trade_date", sort=True)
    for day in calendar:
        if day in trade_by_date.groups:
            for _, row in trade_by_date.get_group(day).iterrows():
                _apply_trade(holdings, costs, row)
                last_prices[row["ticker_yahoo"]] = float(row["price"])

        active = {t: q for t, q in holdings.items() if q > MIN_POSITION_QTY}
        if not active:
            snapshots.append(
                {
                    "date": day,
                    "market_value": 0.0,
                    "cost_basis": 0.0,
                    "position_count": 0,
                }
            )
            continue

        cost_basis = sum(costs.get(t, 0.0) for t in active)
        avg_costs = {t: costs[t] / active[t] for t in active if active[t] > 0}
        snapshots.append(
            {
                "date": day,
                "market_value": np.nan,
                "cost_basis": cost_basis,
                "position_count": len(active),
                "holdings": active.copy(),
                "last_prices": last_prices.copy(),
                "avg_costs": avg_costs,
            }
        )

    timeline = pd.DataFrame(snapshots)
    days_with_holdings = timeline[timeline["position_count"] > 0]
    if days_with_holdings.empty:
        return timeline.drop(columns=["holdings"], errors="ignore")

    all_tickers = set()
    for h in days_with_holdings["holdings"]:
        if isinstance(h, dict):
            all_tickers.update(h.keys())

    tickers_tuple = tuple(sorted(all_tickers))
    price_matrix = fetch_close_matrix(
        tickers_tuple,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
    )

    market_values: list[float] = []
    for _, row in timeline.iterrows():
        h = row.get("holdings")
        if not isinstance(h, dict) or not h:
            market_values.append(float(row.get("market_value") or 0.0))
            continue

        day = row["date"]
        total = 0.0
        valid = 0
        last_px = row.get("last_prices") if isinstance(row.get("last_prices"), dict) else {}
        avg_costs = row.get("avg_costs") if isinstance(row.get("avg_costs"), dict) else {}

        for ticker, qty in h.items():
            px = None
            if not price_matrix.empty and ticker in price_matrix.columns:
                prices = price_matrix[ticker]
                available = prices.loc[:day].dropna()
                if not available.empty:
                    px = float(available.iloc[-1])
            if px is None and ticker in last_px:
                px = float(last_px[ticker])
            if px is None and ticker in avg_costs:
                px = float(avg_costs[ticker])

            if px is not None:
                total += qty * px
                valid += 1

        if valid == 0:
            market_values.append(np.nan)
        else:
            market_values.append(total)

    timeline["market_value"] = market_values
    timeline["unrealized_pnl"] = timeline["market_value"] - timeline["cost_basis"]

    return timeline.drop(columns=["holdings", "last_prices", "avg_costs"], errors="ignore")
