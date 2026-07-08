"""
Parsowanie i agregacja dywidend z arkusza Cash Operations XTB.
"""

from __future__ import annotations

import pandas as pd

DIVIDEND_TYPE_RE = r"dividend|dywidend"
WITHHOLDING_TYPE_RE = r"withholding|podatek u źródła|tax"


def parse_dividends(cash_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Wyciąga dywidendy z Cash Operations.

    Kolumny wynikowe: date, year, ticker_xtb, amount, comment.
    """
    if cash_ops is None or cash_ops.empty or "Type" not in cash_ops.columns:
        return pd.DataFrame()

    mask = cash_ops["Type"].astype(str).str.contains(DIVIDEND_TYPE_RE, case=False, na=False)
    div = cash_ops[mask].copy()
    if div.empty:
        return pd.DataFrame()

    div["date"] = pd.to_datetime(div.get("Time"), errors="coerce")
    div = div.dropna(subset=["date"])
    if div.empty:
        return pd.DataFrame()

    div["year"] = div["date"].dt.year
    div["amount"] = pd.to_numeric(div.get("Amount"), errors="coerce")
    div = div.dropna(subset=["amount"])

    ticker = div["Ticker"] if "Ticker" in div.columns else pd.Series("—", index=div.index)
    comment = div["Comment"] if "Comment" in div.columns else pd.Series("", index=div.index)

    currency = (
        div["Currency"]
        if "Currency" in div.columns
        else (
            div["account_currency"]
            if "account_currency" in div.columns
            else pd.Series(pd.NA, index=div.index)
        )
    )

    result = pd.DataFrame(
        {
            "date": div["date"],
            "year": div["year"].astype(int),
            "ticker_xtb": ticker.fillna("—").astype(str).str.strip().str.upper(),
            "amount": div["amount"],
            "currency": currency.astype("string").str.upper(),
            "comment": comment.fillna("").astype(str),
        }
    )
    return result.sort_values("date").reset_index(drop=True)


def dividends_summary(div: pd.DataFrame, current_year: int | None = None) -> dict[str, float | int]:
    """Zbiorcze metryki dywidend (łącznie, w bieżącym roku, liczba, średnia)."""
    if div is None or div.empty:
        return {
            "total": 0.0,
            "current_year": 0.0,
            "count": 0,
            "avg": 0.0,
        }

    total = float(div["amount"].sum())
    count = int(len(div))
    avg = float(div["amount"].mean()) if count else 0.0

    cy_total = 0.0
    if current_year is not None:
        cy_total = float(div.loc[div["year"] == current_year, "amount"].sum())

    return {
        "total": total,
        "current_year": cy_total,
        "count": count,
        "avg": avg,
    }


def dividends_per_year(div: pd.DataFrame) -> pd.DataFrame:
    """Suma dywidend per rok (kolumny: year, amount)."""
    if div is None or div.empty:
        return pd.DataFrame()
    out = div.groupby("year", as_index=False)["amount"].sum()
    return out.sort_values("year").reset_index(drop=True)


def dividends_per_ticker(div: pd.DataFrame) -> pd.DataFrame:
    """Suma, liczba i ostatnia data dywidend per ticker."""
    if div is None or div.empty:
        return pd.DataFrame()
    out = div.groupby("ticker_xtb").agg(
        total=("amount", "sum"),
        payouts=("amount", "count"),
        last_date=("date", "max"),
    )
    return out.sort_values("total", ascending=False).reset_index()
