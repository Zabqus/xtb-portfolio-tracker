"""
Parsowanie historii transakcji z arkusza Cash Operations XTB.
"""

from __future__ import annotations

import re

import pandas as pd

from core.importer_maps import map_ticker_to_yahoo

XTB_TRADE_TYPES = ("Stock purchase", "Stock sell")

XTB_TRADE_COMMENT_RE = re.compile(
    r"^(OPEN|CLOSE)\s+BUY\s+([\d.]+)(?:/[\d.]+)?\s+@\s+([\d.]+)",
    re.IGNORECASE,
)

SIDE_MAP = {
    "Stock purchase": "OPEN",
    "Stock sell": "CLOSE",
}


def parse_trade_comment(comment: str) -> tuple[str, float, float] | None:
    if not isinstance(comment, str):
        return None
    match = XTB_TRADE_COMMENT_RE.match(comment.strip())
    if not match:
        return None
    return match.group(1).upper(), float(match.group(2)), float(match.group(3))


def parse_cash_operations_trades(cash_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Wyciąga wszystkie transakcje giełdowe z Cash Operations.

    Kolumny: trade_time, trade_date, ticker_xtb, ticker_yahoo, side, quantity,
             price, amount, operation_type, comment
    """
    required = {"Type", "Ticker", "Comment", "Time"}
    if not required.issubset(cash_ops.columns):
        raise ValueError(f"Cash Operations – missing columns: {required - set(cash_ops.columns)}")

    trades = cash_ops[cash_ops["Type"].isin(XTB_TRADE_TYPES)].copy()
    trades = trades.dropna(subset=["Ticker"])
    trades["trade_time"] = pd.to_datetime(trades["Time"], errors="coerce")
    trades = trades.dropna(subset=["trade_time"])
    trades = trades.sort_values("trade_time")

    rows: list[dict] = []
    for _, row in trades.iterrows():
        parsed = parse_trade_comment(row["Comment"])
        if parsed is None:
            continue

        side, quantity, price = parsed
        raw_ticker_xtb = str(row["Ticker"]).strip().upper()
        ticker_xtb = raw_ticker_xtb
        account_label = row.get("account_label") if "account_label" in row.index else None
        if account_label is not None and pd.notna(account_label):
            label = str(account_label)
            suffix = f" [{label}]"
            if not ticker_xtb.endswith(suffix):
                ticker_xtb = f"{ticker_xtb}{suffix}"
        op_type = str(row["Type"])

        row_data = {
                "trade_time": row["trade_time"],
                "trade_date": row["trade_time"].normalize(),
                "ticker_xtb": ticker_xtb,
                "ticker_yahoo": map_ticker_to_yahoo(raw_ticker_xtb),
                "side": side,
                "quantity": quantity,
                "price": price,
                "amount": pd.to_numeric(row.get("Amount"), errors="coerce"),
                "operation_type": op_type,
                "comment": row["Comment"],
        }
        if account_label is not None and pd.notna(account_label):
            row_data["account_label"] = str(account_label)
        rows.append(row_data)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).reset_index(drop=True)
