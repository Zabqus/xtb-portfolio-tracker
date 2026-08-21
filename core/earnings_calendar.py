"""
Kalendarz wyników kwartalnych (earnings) dla otwartych pozycji.

Dane z yfinance `Ticker.calendar`:
- `Earnings Date` – data (lub okno dat) publikacji wyników,
- `Earnings Average` – konsensusowa prognoza EPS (gdy dostępna).

Cache 24h. Yahoo bywa niekompletne (ETF-y, część zagranicznych) — wtedy
ticker pomijamy / pokazujemy bez EPS.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st
import yfinance as yf


def _safe_float(value) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_earnings_date(raw) -> pd.Timestamp | None:
    """Yahoo zwraca date, datetime, Timestamp albo listę (okno dat) — bierzemy najwcześniejszą."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        parsed = [_parse_earnings_date(x) for x in raw]
        parsed = [p for p in parsed if p is not None]
        return min(parsed) if parsed else None
    if isinstance(raw, pd.Timestamp):
        return raw.normalize()
    if isinstance(raw, datetime):
        return pd.Timestamp(raw).normalize()
    if isinstance(raw, date):
        return pd.Timestamp(raw)
    try:
        ts = pd.to_datetime(raw, errors="coerce")
    except (ValueError, TypeError, OverflowError):
        return None
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_earnings_meta(tickers: tuple[str, ...]) -> dict[str, dict]:
    """Per ticker: earnings_date (Timestamp|None), eps_estimate (float|None)."""
    out: dict[str, dict] = {}
    for ticker in tickers:
        earnings_date = None
        eps_estimate = None
        try:
            cal = yf.Ticker(ticker).calendar or {}
        except Exception:
            cal = {}
        if isinstance(cal, pd.DataFrame):
            # Starsze yfinance: DataFrame z wierszami Earnings Date / Earnings Average.
            try:
                if "Earnings Date" in cal.index:
                    earnings_date = _parse_earnings_date(cal.loc["Earnings Date"].iloc[0])
                if "Earnings Average" in cal.index:
                    eps_estimate = _safe_float(cal.loc["Earnings Average"].iloc[0])
            except (KeyError, IndexError, TypeError, ValueError):
                pass
        elif isinstance(cal, dict):
            earnings_date = _parse_earnings_date(cal.get("Earnings Date"))
            eps_estimate = _safe_float(cal.get("Earnings Average"))
        out[ticker] = {
            "earnings_date": earnings_date,
            "eps_estimate": eps_estimate,
        }
    return out


def build_earnings_calendar(analyzed: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Nadchodzące wyniki dla otwartych pozycji.

    Zwraca (tabela, summary). Tabela: ticker, data, dni do raportu, EPS est., urgency.
    """
    summary = {
        "with_date": 0,
        "within_7d": 0,
        "within_14d": 0,
        "missing": 0,
    }
    if analyzed is None or analyzed.empty or "ticker_yahoo" not in analyzed.columns:
        return pd.DataFrame(), summary

    valid = analyzed.dropna(subset=["ticker_yahoo"]).copy()
    if valid.empty:
        return pd.DataFrame(), summary

    # Jedna pozycja per ticker Yahoo (waga / koszt niepotrzebne).
    by_yahoo = (
        valid.groupby("ticker_yahoo", as_index=False)
        .agg(ticker_xtb=("ticker_xtb", "first"))
        if "ticker_xtb" in valid.columns
        else valid[["ticker_yahoo"]].drop_duplicates().assign(
            ticker_xtb=lambda d: d["ticker_yahoo"]
        )
    )

    tickers = tuple(sorted(by_yahoo["ticker_yahoo"].astype(str).unique()))
    meta = fetch_earnings_meta(tickers)
    today = pd.Timestamp.now().normalize()

    rows: list[dict] = []
    missing = 0
    for _, row in by_yahoo.iterrows():
        yahoo = str(row["ticker_yahoo"])
        m = meta.get(yahoo, {})
        ed = m.get("earnings_date")
        if ed is None or pd.isna(ed):
            missing += 1
            continue
        ed = pd.Timestamp(ed).normalize()
        days = int((ed - today).days)
        # Tylko nadchodzące (lub dziś); przeszłe daty pomijamy bez liczenia jako „brak”.
        if days < 0:
            continue
        if days <= 7:
            urgency = "7d"
        elif days <= 14:
            urgency = "14d"
        else:
            urgency = "later"
        rows.append(
            {
                "ticker_xtb": row.get("ticker_xtb", yahoo),
                "ticker_yahoo": yahoo,
                "earnings_date": ed,
                "days_until": days,
                "eps_estimate": m.get("eps_estimate"),
                "urgency": urgency,
            }
        )

    summary.update(
        with_date=len(rows),
        within_7d=sum(1 for r in rows if r["urgency"] == "7d"),
        within_14d=sum(1 for r in rows if r["urgency"] in ("7d", "14d")),
        missing=missing,
    )

    if not rows:
        return pd.DataFrame(), summary

    table = (
        pd.DataFrame(rows)
        .sort_values(["days_until", "ticker_xtb"], ascending=[True, True])
        .reset_index(drop=True)
    )
    return table, summary
