"""Globalne filtry portfela: konto, sektor, region, zyskowność."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from core.allocation import enrich_portfolio_allocation


@dataclass
class PortfolioFilters:
    pnl: str = "Wszystkie"
    account: str = "Wszystkie"
    sector: str = "Wszystkie"
    region: str = "Wszystkie"


def render_portfolio_filters(analyzed: pd.DataFrame, *, key_prefix: str = "pf") -> PortfolioFilters:
    """UI filtrów globalnych; zwraca wybrane wartości."""
    enriched = None
    try:
        enriched = enrich_portfolio_allocation(analyzed)
    except (ValueError, KeyError):
        enriched = pd.DataFrame()

    meta_map: dict[str, dict[str, str]] = {}
    if enriched is not None and not enriched.empty:
        for _, row in enriched.iterrows():
            yahoo = str(row["ticker_yahoo"])
            meta_map[yahoo] = {
                "sector": str(row.get("sector", "Brak sektora")),
                "region": str(row.get("region", "Inne")),
            }

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pnl = st.radio(
            "Pokaż",
            ["Wszystkie", "Tylko zyskowne", "Tylko stratne"],
            horizontal=True,
            key=f"{key_prefix}_pnl",
        )
    with c2:
        if "account_label" in analyzed.columns and analyzed["account_label"].nunique() > 1:
            accounts = ["Wszystkie"] + sorted(analyzed["account_label"].dropna().unique().tolist())
            account = st.selectbox("Konto", accounts, key=f"{key_prefix}_account")
        else:
            account = "Wszystkie"
    with c3:
        sectors = ["Wszystkie"]
        if meta_map:
            sectors += sorted({m["sector"] for m in meta_map.values()})
        sector = st.selectbox("Sektor", sectors, key=f"{key_prefix}_sector")
    with c4:
        regions = ["Wszystkie", "USA", "EU", "PL", "Inne"]
        region = st.selectbox("Region", regions, key=f"{key_prefix}_region")

    st.session_state["_portfolio_meta_map"] = meta_map
    return PortfolioFilters(pnl=pnl, account=account, sector=sector, region=region)


def apply_portfolio_filters(analyzed: pd.DataFrame, filters: PortfolioFilters) -> pd.DataFrame:
    """Filtruje ramkę pozycji według globalnych kryteriów."""
    if analyzed is None or analyzed.empty:
        return analyzed

    out = analyzed.copy()
    if filters.pnl == "Tylko zyskowne" and "roi_pct" in out.columns:
        out = out[out["roi_pct"] > 0]
    elif filters.pnl == "Tylko stratne" and "roi_pct" in out.columns:
        out = out[out["roi_pct"] < 0]

    if filters.account != "Wszystkie" and "account_label" in out.columns:
        out = out[out["account_label"] == filters.account]

    meta_map: dict = st.session_state.get("_portfolio_meta_map", {})
    if meta_map and (filters.sector != "Wszystkie" or filters.region != "Wszystkie"):
        if "ticker_yahoo" not in out.columns:
            return out

        def _match(row: pd.Series) -> bool:
            m = meta_map.get(str(row.get("ticker_yahoo", "")), {})
            if filters.sector != "Wszystkie" and m.get("sector") != filters.sector:
                return False
            if filters.region != "Wszystkie" and m.get("region") != filters.region:
                return False
            return True

        out = out[out.apply(_match, axis=1)]

    return out
