"""Tabele Streamlit z polskimi nagłówkami."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.range_52w import enrich_52w_range


def render_round_trips_table(round_trips: pd.DataFrame) -> None:
    """Jedna tabela round-tripów FIFO (Cash Operations)."""
    if round_trips is None or round_trips.empty:
        st.caption("Brak zamkniętych round-tripów w tym okresie.")
        return

    display = round_trips.copy().rename(
        columns={
            "ticker_xtb": "Ticker",
            "open_time": "Otwarcie",
            "close_time": "Zamknięcie",
            "quantity": "Ilość",
            "open_price": "Cena wejścia",
            "close_price": "Cena wyjścia",
            "holding_days": "Dni",
            "realized_pnl": "PnL",
            "pnl_pct": "ROI %",
            "is_win": "Trafiona",
        }
    )
    for col in ("PnL", "ROI %", "Dni", "Cena wejścia", "Cena wyjścia", "Ilość"):
        if col in display.columns:
            display[col] = display[col].map(lambda x: round(x, 2) if pd.notna(x) else None)

    st.dataframe(display, use_container_width=True, hide_index=True)


def render_open_positions_table(
    df: pd.DataFrame,
    currency: str,
    *,
    total_value: float | None = None,
    show_52w: bool = True,
) -> None:
    """Tabela otwartych pozycji z wagą w portfelu, PnL % i zakresem 52W."""
    display = df.copy()

    if total_value is None and "market_value" in display.columns:
        total_value = float(display["market_value"].sum())

    if total_value and total_value > 0:
        if "market_value" in display.columns:
            display["weight_pct"] = display["market_value"] / total_value * 100.0
        if "pnl" in display.columns:
            display["pnl_portfolio_pct"] = display["pnl"] / total_value * 100.0

    if show_52w and "ticker_yahoo" in display.columns:
        display = enrich_52w_range(display)

    rename = {
        "ticker_xtb": "Ticker XTB",
        "ticker_yahoo": "Ticker Yahoo",
        "account_label": "Konto",
        "currency": "Waluta",
        "quantity": "Ilość",
        "avg_price": "Śr. cena (waluta instr.)",
        "market_price": "Cena rynkowa",
        "position_cost": f"Koszt ({currency})",
        "market_value": f"Wartość ({currency})",
        "pnl": f"Zysk / strata ({currency})",
        "roi_pct": "ROI %",
        "weight_pct": "% portfela",
        "pnl_portfolio_pct": "% PnL / portfel",
        "range_52w": "52W Low → High",
    }
    display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})

    pnl_col = f"Zysk / strata ({currency})"
    pnl_pct_col = "% PnL / portfel"
    if pnl_col in display.columns and pnl_pct_col in display.columns:
        display[pnl_col] = [
            f"{pnl:,.2f} ({pct:+.2f}%)" if pd.notna(pnl) and pd.notna(pct) else (f"{pnl:,.2f}" if pd.notna(pnl) else None)
            for pnl, pct in zip(display[pnl_col], display[pnl_pct_col])
        ]
        display = display.drop(columns=[pnl_pct_col])

    weight_col = "% portfela"
    if weight_col in display.columns:
        display = display.drop(columns=[weight_col])

    skip = ("Ticker XTB", "Ticker Yahoo", "Konto", "Waluta", "52W Low → High")
    for col in display.columns:
        if col not in skip:
            display[col] = display[col].map(lambda x: round(x, 2) if pd.notna(x) and isinstance(x, (int, float)) else x)

    col_config: dict = {}
    if "52W Low → High" in display.columns:
        col_config["52W Low → High"] = st.column_config.ProgressColumn(
            "52W Low → High",
            min_value=0.0,
            max_value=1.0,
            format="%.0f%%",
            help="Pozycja ceny w zakresie 52 tygodni (0 = dołek, 100% = szczyt).",
        )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config=col_config or None,
    )


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
