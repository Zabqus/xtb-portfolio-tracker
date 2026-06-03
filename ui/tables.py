"""Tabele Streamlit z polskimi nagłówkami."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_open_positions_table(df: pd.DataFrame, currency: str) -> None:
    display = df.copy()
    rename = {
        "ticker_xtb": "Ticker XTB",
        "ticker_yahoo": "Ticker Yahoo",
        "currency": "Waluta",
        "quantity": "Ilość",
        "avg_price": "Śr. cena (waluta instr.)",
        "market_price": "Cena rynkowa",
        "position_cost": f"Koszt ({currency})",
        "market_value": f"Wartość ({currency})",
        "pnl": f"Zysk / strata ({currency})",
        "roi_pct": "ROI %",
    }
    display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})

    skip = ("Ticker XTB", "Ticker Yahoo", "Waluta")
    for col in display.columns:
        if col not in skip:
            display[col] = display[col].map(lambda x: round(x, 2) if pd.notna(x) else None)

    st.dataframe(display, use_container_width=True, hide_index=True)


def render_closed_positions_table(closed: pd.DataFrame) -> None:
    display = closed.copy()
    rename = {
        "ticker_xtb": "Ticker XTB",
        "ticker_yahoo": "Ticker Yahoo",
        "currency": "Waluta",
        "instrument": "Instrument",
        "category": "Kategoria",
        "position_type": "Typ",
        "quantity": "Wolumen",
        "open_price": "Cena otwarcia",
        "close_price": "Cena zamknięcia",
        "open_time": "Otwarcie (UTC)",
        "close_time": "Zamknięcie (UTC)",
        "pnl": "Profit/Loss",
        "gross_pnl": "Gross Profit",
        "purchase_value": "Wartość zakupu",
        "sale_value": "Wartość sprzedaży",
        "commission": "Prowizja",
    }
    display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})

    for col in display.columns:
        if display[col].dtype in ("float64", "float32"):
            display[col] = display[col].map(lambda x: round(x, 2) if pd.notna(x) else None)

    st.dataframe(display, use_container_width=True, hide_index=True)
