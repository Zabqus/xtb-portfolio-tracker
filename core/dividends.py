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

    if "Currency" in div.columns:
        currency = div["Currency"].astype("string").str.upper()
    else:
        currency = pd.Series(pd.NA, index=div.index, dtype="string")
    # Multi-account / braki w eksporcie: Amount jest w walucie konta.
    if "account_currency" in div.columns:
        account_ccy = div["account_currency"].astype("string").str.upper()
        currency = currency.fillna(account_ccy)

    result = pd.DataFrame(
        {
            "date": div["date"],
            "year": div["year"].astype(int),
            "ticker_xtb": ticker.fillna("—").astype(str).str.strip().str.upper(),
            "amount": div["amount"],
            "currency": currency,
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


def _cash_ops_type_slice(cash_ops: pd.DataFrame, type_re: str) -> pd.DataFrame:
    if cash_ops is None or cash_ops.empty or "Type" not in cash_ops.columns:
        return pd.DataFrame()
    mask = cash_ops["Type"].astype(str).str.contains(type_re, case=False, na=False)
    # Odfiltruj czyste dywidendy z WHT (Type bywa "Withholding tax" vs "Dividend")
    sliced = cash_ops[mask].copy()
    if sliced.empty:
        return pd.DataFrame()
    sliced["date"] = pd.to_datetime(sliced.get("Time"), errors="coerce")
    sliced = sliced.dropna(subset=["date"])
    if sliced.empty:
        return pd.DataFrame()
    sliced["year"] = sliced["date"].dt.year.astype(int)
    sliced["amount"] = pd.to_numeric(sliced.get("Amount"), errors="coerce")
    sliced = sliced.dropna(subset=["amount"])
    if sliced.empty:
        return pd.DataFrame()

    ticker = sliced["Ticker"] if "Ticker" in sliced.columns else pd.Series("—", index=sliced.index)
    comment = sliced["Comment"] if "Comment" in sliced.columns else pd.Series("", index=sliced.index)
    if "Currency" in sliced.columns:
        currency = sliced["Currency"].astype("string").str.upper()
    else:
        currency = pd.Series(pd.NA, index=sliced.index, dtype="string")
    if "account_currency" in sliced.columns:
        account_ccy = sliced["account_currency"].astype("string").str.upper()
        currency = currency.fillna(account_ccy)

    return pd.DataFrame(
        {
            "date": sliced["date"],
            "year": sliced["year"],
            "ticker_xtb": ticker.fillna("—").astype(str).str.strip().str.upper(),
            "amount": sliced["amount"],
            "currency": currency,
            "comment": comment.fillna("").astype(str),
            "type": sliced["Type"].astype(str),
        }
    ).sort_values("date").reset_index(drop=True)


def parse_withholding_tax(cash_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Podatek u źródła (WHT) z Cash Operations.

    Kolumny: date, year, ticker_xtb, amount, currency, comment, type.
    Amount zwykle ujemny (obciążenie).
    """
    wht = _cash_ops_type_slice(cash_ops, WITHHOLDING_TYPE_RE)
    if wht.empty:
        return wht
    # Nie myl dywidend zawierających słowo „tax” w komentarzu — Type już filtruje.
    # Dodatkowo wyklucz wiersze typowo dywidendowe.
    div_mask = wht["type"].str.contains(DIVIDEND_TYPE_RE, case=False, na=False)
    # Zostaw wiersze, które są WHT nawet jeśli Type ma też „dividend” (rzadkie).
    pure_div = div_mask & ~wht["type"].str.contains(WITHHOLDING_TYPE_RE, case=False, na=False)
    return wht.loc[~pure_div].reset_index(drop=True)


def withholding_by_year(wht: pd.DataFrame) -> pd.DataFrame:
    """Suma |WHT| per rok (kolumny: year, amount — amount dodatnie)."""
    if wht is None or wht.empty:
        return pd.DataFrame(columns=["year", "amount"])
    out = wht.copy()
    out["amount"] = out["amount"].abs()
    return (
        out.groupby("year", as_index=False)["amount"]
        .sum()
        .sort_values("year")
        .reset_index(drop=True)
    )


def withholding_summary(wht: pd.DataFrame, current_year: int | None = None) -> dict[str, float | int]:
    """Zbiorcze metryki WHT (kwoty jako wartość bezwzględna)."""
    if wht is None or wht.empty:
        return {"total": 0.0, "current_year": 0.0, "count": 0}
    abs_amt = wht["amount"].abs()
    total = float(abs_amt.sum())
    cy = 0.0
    if current_year is not None:
        cy = float(abs_amt.loc[wht["year"] == current_year].sum())
    return {"total": total, "current_year": cy, "count": int(len(wht))}
