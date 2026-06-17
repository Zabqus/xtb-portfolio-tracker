"""
Kalendarz dywidend i forward yield dla otwartych pozycji.

Dane z yfinance `.info`:
- `dividendYield` – stopa dywidendy (forward),
- `dividendRate` – roczna dywidenda na akcję (waluta instrumentu),
- `exDividendDate` – data odcięcia dywidendy (unix timestamp).

Szacowany roczny przychód z dywidend liczymy jako wartość_pozycji × stopa,
co jest niezależne od waluty (pozostaje w walucie wyświetlania).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.fundamentals import fetch_ticker_info


def _normalize_yield(raw) -> float | None:
    """Stopa dywidendy jako ułamek (0.025 = 2,5%). Yahoo bywa w % lub w ułamku."""
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    # Wartości > 1 traktujemy jako procenty (np. 2.5 → 0.025).
    return val / 100.0 if val > 1 else val


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_dividend_meta(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Per ticker: yield (ułamek), rate (na akcję), ex_date (Timestamp|None)."""
    out: dict[str, dict] = {}
    for ticker in tickers:
        info = fetch_ticker_info(ticker)
        ex_ts = info.get("exDividendDate")
        ex_date = None
        if ex_ts:
            try:
                ex_date = pd.to_datetime(ex_ts, unit="s")
            except (ValueError, TypeError, OverflowError):
                ex_date = None
        rate = info.get("dividendRate")
        try:
            rate = float(rate) if rate is not None else None
        except (TypeError, ValueError):
            rate = None
        out[ticker] = {
            "yield": _normalize_yield(info.get("dividendYield")),
            "rate": rate,
            "ex_date": ex_date,
        }
    return out


def build_dividend_calendar(
    analyzed: pd.DataFrame,
    currency: str,
) -> tuple[pd.DataFrame, dict]:
    """
    Kalendarz dywidend + podsumowanie forward yield całego portfela.

    Zwraca (tabela, summary). Tabela: ticker, yield %, ex-date, szac. roczny przychód.
    """
    summary = {
        "annual_income": 0.0,
        "portfolio_yield_pct": 0.0,
        "paying_positions": 0,
        "currency": currency,
    }
    if analyzed is None or analyzed.empty or "ticker_yahoo" not in analyzed.columns:
        return pd.DataFrame(), summary

    valid = analyzed.dropna(subset=["ticker_yahoo", "market_value"]).copy()
    valid = valid[valid["market_value"] > 0]
    if valid.empty:
        return pd.DataFrame(), summary

    tickers = tuple(sorted(valid["ticker_yahoo"].astype(str).unique()))
    meta = fetch_dividend_meta(tickers)

    today = pd.Timestamp.now().normalize()
    rows: list[dict] = []
    total_value = float(valid["market_value"].sum())
    total_income = 0.0

    for _, row in valid.iterrows():
        yahoo = str(row["ticker_yahoo"])
        m = meta.get(yahoo, {})
        dy = m.get("yield")
        if not dy:
            continue
        mv = float(row["market_value"])
        income = mv * dy
        total_income += income
        ex_date = m.get("ex_date")
        upcoming = bool(ex_date is not None and ex_date.normalize() >= today)
        rows.append(
            {
                "ticker_xtb": row.get("ticker_xtb", yahoo),
                "ticker_yahoo": yahoo,
                "yield_pct": dy * 100,
                "ex_date": ex_date,
                "ex_upcoming": upcoming,
                "annual_income": income,
                "rate_per_share": m.get("rate"),
            }
        )

    if not rows:
        summary["currency"] = currency
        return pd.DataFrame(), summary

    table = pd.DataFrame(rows)
    # Sort: najpierw nadchodzące ex-date rosnąco, potem reszta.
    table["_sort_date"] = table["ex_date"].fillna(pd.Timestamp.max)
    table = table.sort_values(["ex_upcoming", "_sort_date"], ascending=[False, True])
    table = table.drop(columns="_sort_date").reset_index(drop=True)

    summary.update(
        annual_income=total_income,
        portfolio_yield_pct=(total_income / total_value * 100) if total_value > 0 else 0.0,
        paying_positions=len(rows),
        currency=currency,
    )
    return table, summary
