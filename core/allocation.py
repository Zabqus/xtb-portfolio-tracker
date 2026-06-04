"""
Alokacja portfela — sektor i region (USA / EU / PL) z yfinance .info.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.fundamentals import fetch_ticker_info

REGION_ORDER = ("USA", "EU", "PL", "Inne")

EU_COUNTRIES = frozenset(
    {
        "Germany",
        "France",
        "Netherlands",
        "Belgium",
        "Italy",
        "Spain",
        "Ireland",
        "Austria",
        "Finland",
        "Sweden",
        "Denmark",
        "Norway",
        "Switzerland",
        "United Kingdom",
        "Luxembourg",
        "Portugal",
        "Greece",
        "Czech Republic",
        "Hungary",
        "Romania",
        "Slovakia",
        "Slovenia",
        "Croatia",
        "Estonia",
        "Latvia",
        "Lithuania",
        "Cyprus",
        "Malta",
    }
)

USA_COUNTRIES = frozenset({"United States", "USA", "US"})
PL_COUNTRIES = frozenset({"Poland"})

YAHOO_EU_SUFFIXES = (
    ".DE",
    ".AS",
    ".PA",
    ".MI",
    ".L",
    ".SW",
    ".CO",
    ".HE",
    ".BR",
    ".VI",
    ".MC",
    ".LS",
    ".IR",
    ".BE",
    ".AT",
    ".ST",
)


def _normalize_country(raw: str | None) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    return text or None


def classify_region(
    country: str | None,
    ticker_yahoo: str,
    ticker_xtb: str = "",
) -> str:
    """
    Przypisuje region: USA | EU | PL | Inne.

    Kolejność: country z .info → sufiks Yahoo → sufiks XTB (.US / .PL).
    """
    c = _normalize_country(country)
    if c in PL_COUNTRIES:
        return "PL"
    if c in USA_COUNTRIES:
        return "USA"
    if c in EU_COUNTRIES:
        return "EU"

    yahoo = str(ticker_yahoo).upper()
    xtb = str(ticker_xtb).upper()

    if yahoo.endswith(".WA") or xtb.endswith(".PL"):
        return "PL"
    if xtb.endswith(".US"):
        return "USA"
    if any(yahoo.endswith(sfx) for sfx in YAHOO_EU_SUFFIXES):
        return "EU"
    if c is None and "." not in yahoo and yahoo.isalpha() and len(yahoo) <= 5:
        # Akcje US na Yahoo często bez sufiksu (AAPL, MSFT)
        return "USA"

    if c:
        return "Inne"
    return "Inne"


def classify_sector(info: dict) -> str:
    """Sektor z .info; ETF-y i brak danych — etykiety po polsku."""
    sector = info.get("sector")
    if sector and str(sector).strip():
        return str(sector).strip()

    quote_type = str(info.get("quoteType") or "").upper()
    category = info.get("category") or info.get("fundFamily")
    if quote_type in {"ETF", "MUTUALFUND"} or category:
        label = str(category).strip() if category else "ETF / fundusz"
        return f"ETF ({label})" if category else "ETF / fundusz"

    return "Brak sektora"


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_allocation_metadata(tickers: tuple[str, ...]) -> dict[str, dict[str, str | None]]:
    """Pobiera sector i country dla listy symboli Yahoo (cache 24h)."""
    result: dict[str, dict[str, str | None]] = {}
    for ticker in tickers:
        info = fetch_ticker_info(ticker)
        result[ticker] = {
            "sector": classify_sector(info),
            "country": _normalize_country(info.get("country")),
            "name": info.get("shortName") or info.get("longName"),
        }
    return result


def enrich_portfolio_allocation(analyzed: pd.DataFrame) -> pd.DataFrame:
    """Dodaje sector, country, region oraz udział % wartości portfela."""
    required = {"ticker_yahoo", "market_value"}
    if not required.issubset(analyzed.columns):
        raise ValueError(f"Brak kolumn: {required - set(analyzed.columns)}")

    valid = analyzed.dropna(subset=["market_value"]).copy()
    valid = valid[valid["market_value"] > 0]
    if valid.empty:
        return pd.DataFrame()

    tickers = tuple(sorted(valid["ticker_yahoo"].astype(str).unique()))
    meta = fetch_allocation_metadata(tickers)

    rows: list[dict] = []
    total = float(valid["market_value"].sum())

    for _, row in valid.iterrows():
        yahoo = str(row["ticker_yahoo"])
        m = meta.get(yahoo, {})
        country = m.get("country")
        xtb = str(row.get("ticker_xtb", ""))
        region = classify_region(country, yahoo, xtb)
        mv = float(row["market_value"])

        rows.append(
            {
                "ticker_xtb": row.get("ticker_xtb", yahoo),
                "ticker_yahoo": yahoo,
                "name": m.get("name"),
                "sector": m.get("sector", "Brak sektora"),
                "country": country or "—",
                "region": region,
                "market_value": mv,
                "weight_pct": (mv / total * 100) if total > 0 else 0.0,
            }
        )

    return pd.DataFrame(rows)


def aggregate_breakdown(
    enriched: pd.DataFrame,
    group_col: str,
    sort_order: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Sumuje market_value wg group_col i dodaje weight_pct."""
    if enriched.empty:
        return pd.DataFrame(columns=[group_col, "market_value", "weight_pct"])

    grouped = (
        enriched.groupby(group_col, as_index=False)["market_value"]
        .sum()
        .sort_values("market_value", ascending=False)
    )
    total = float(grouped["market_value"].sum())
    grouped["weight_pct"] = grouped["market_value"] / total * 100 if total > 0 else 0.0

    if sort_order:
        order_map = {label: idx for idx, label in enumerate(sort_order)}
        grouped["_order"] = grouped[group_col].map(lambda x: order_map.get(x, len(sort_order)))
        grouped = grouped.sort_values("_order").drop(columns="_order")

    return grouped
