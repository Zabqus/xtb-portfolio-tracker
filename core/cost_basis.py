"""
Śledzenie średniej ceny zakupu (cost basis) przy kolejnych dokupieniach.
"""

from __future__ import annotations

import pandas as pd

MIN_QTY = 1e-9


def build_cost_basis_history(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Buduje chronologię zmian średniej ceny i bazy kosztowej per ticker.

    Po każdej transakcji OPEN/CLOSE:
        quantity_after, avg_price_after, cost_basis_after
    """
    if trades.empty:
        return pd.DataFrame()

    required = {"trade_time", "ticker_xtb", "ticker_yahoo", "side", "quantity", "price"}
    if not required.issubset(trades.columns):
        raise ValueError(f"Trades missing columns: {required - set(trades.columns)}")

    sorted_trades = trades.sort_values("trade_time")
    holdings: dict[str, dict[str, float]] = {}
    events: list[dict] = []

    for _, row in sorted_trades.iterrows():
        ticker = row["ticker_yahoo"]
        side = row["side"]
        qty = float(row["quantity"])
        price = float(row["price"])

        if ticker not in holdings:
            holdings[ticker] = {"qty": 0.0, "cost": 0.0}

        h = holdings[ticker]
        qty_before = h["qty"]
        avg_before = h["cost"] / h["qty"] if h["qty"] > MIN_QTY else 0.0

        if side == "OPEN":
            h["cost"] += qty * price
            h["qty"] += qty
            event = "BUY"
        else:
            if h["qty"] <= MIN_QTY:
                continue
            avg = h["cost"] / h["qty"]
            close_qty = min(qty, h["qty"])
            h["cost"] -= close_qty * avg
            h["qty"] -= close_qty
            event = "SELL"
            if h["qty"] <= MIN_QTY:
                h["qty"] = 0.0
                h["cost"] = 0.0

        qty_after = h["qty"]
        avg_after = h["cost"] / h["qty"] if h["qty"] > MIN_QTY else 0.0
        cost_after = h["cost"]

        events.append(
            {
                "trade_time": row["trade_time"],
                "ticker_xtb": row["ticker_xtb"],
                "ticker_yahoo": ticker,
                "event": event,
                "side": side,
                "trade_qty": qty,
                "trade_price": price,
                "quantity_before": qty_before,
                "avg_price_before": avg_before,
                "quantity_after": qty_after,
                "avg_price_after": avg_after,
                "cost_basis_after": cost_after,
            }
        )

    return pd.DataFrame(events)


def get_current_cost_basis(cost_history: pd.DataFrame) -> pd.DataFrame:
    """Ostatni znany stan cost basis dla każdego tickera (otwarte pozycje)."""
    if cost_history.empty:
        return pd.DataFrame()

    latest = (
        cost_history.sort_values("trade_time")
        .groupby("ticker_xtb", as_index=False)
        .last()
    )
    open_only = latest[latest["quantity_after"] > MIN_QTY].copy()
    return open_only[
        [
            "ticker_xtb",
            "ticker_yahoo",
            "quantity_after",
            "avg_price_after",
            "cost_basis_after",
            "trade_time",
        ]
    ].rename(
        columns={
            "quantity_after": "quantity",
            "avg_price_after": "avg_price",
            "cost_basis_after": "cost_basis",
            "trade_time": "last_trade_time",
        }
    )
