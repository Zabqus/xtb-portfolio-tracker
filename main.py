"""
Dashboard Streamlit – monitorowanie portfela akcji i ETF-ów z XTB.
Uruchomienie: streamlit run main.py
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analizator import analyze_portfolio, portfolio_summary
from importer import parse_xtb_report

# Konfiguracja strony
st.set_page_config(
    page_title="XTB Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

st.title("📈 XTB Portfolio Tracker")
st.caption("Lokalny dashboard do analizy portfela akcji i ETF-ów")


def _format_currency(value: float, currency: str = "PLN") -> str:
    """Formatuje kwotę do wyświetlenia w metrykach."""
    if pd.isna(value):
        return "—"
    return f"{value:,.2f} {currency}"


def _pnl_color(value: float) -> str:
    """Zwraca kolor Streamlit dla zysku (zielony) lub straty (czerwony)."""
    if pd.isna(value) or value == 0:
        return "off"
    return "normal" if value > 0 else "inverse"


def _build_pie_chart(df: pd.DataFrame) -> go.Figure:
    """Wykres kołowy – udział procentowy pozycji w wartości portfela."""
    chart_df = df.dropna(subset=["wartosc_rynkowa"]).copy()
    chart_df["udzial_pct"] = (
        chart_df["wartosc_rynkowa"] / chart_df["wartosc_rynkowa"].sum() * 100
    )
    label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"

    fig = px.pie(
        chart_df,
        names=label_col,
        values="wartosc_rynkowa",
        title="Struktura portfela (% wartości)",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(showlegend=True, height=450)
    return fig


def _build_pnl_bar_chart(df: pd.DataFrame) -> go.Figure:
    """Wykres słupkowy – zysk/strata na poszczególnych aktywach."""
    chart_df = df.dropna(subset=["zysk_strata"]).copy()
    label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in chart_df["zysk_strata"]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=chart_df[label_col],
                y=chart_df["zysk_strata"],
                marker_color=colors,
                text=chart_df["zysk_strata"].round(2),
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title="Zysk / strata na pozycjach",
        xaxis_title="Instrument",
        yaxis_title="Zysk / strata",
        height=450,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig


def _display_summary_table(df: pd.DataFrame) -> None:
    """Tabela podsumowująca wszystkie otwarte pozycje."""
    display = df.copy()
    rename = {
        "ticker_xtb": "Ticker XTB",
        "ticker_yahoo": "Ticker Yahoo",
        "ilosc": "Ilość",
        "srednia_cena": "Śr. cena zakupu",
        "cena_rynkowa": "Cena rynkowa",
        "koszt_pozycji": "Koszt pozycji",
        "wartosc_rynkowa": "Wartość rynkowa",
        "zysk_strata": "Zysk / strata",
        "roi_pct": "ROI %",
    }
    display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})

    numeric_cols = [
        "Ilość",
        "Śr. cena zakupu",
        "Cena rynkowa",
        "Koszt pozycji",
        "Wartość rynkowa",
        "Zysk / strata",
        "ROI %",
    ]
    for col in numeric_cols:
        if col in display.columns:
            display[col] = display[col].map(lambda x: round(x, 2) if pd.notna(x) else None)

    st.dataframe(display, use_container_width=True, hide_index=True)


# --- Sidebar: wgrywanie pliku ---
with st.sidebar:
    st.header("Import z XTB")
    uploaded = st.file_uploader(
        "Wgraj eksport z XTB (Excel lub CSV)",
        type=["csv", "xlsx", "xls"],
        help=(
            "Natywny Excel z platformy XTB (arkusz „Cash Operations”) "
            "lub uproszczony plik z kolumnami: Ticker, Ilość, Średnia cena zakupu"
        ),
    )
    st.markdown(
        """
        **Eksport XTB:** w platformie pobierz raport Excel
        (np. *Cash Operations* + *Closed Positions*).

        Aplikacja sama wyliczy **otwarte pozycje** z historii zakupów i sprzedaży.

        **Wskazówka:** jeśli Yahoo nie znajdzie ceny,
        sprawdź mapowanie w `importer.py` → `TICKER_MAP`.
        """
    )

if uploaded is None:
    st.info("Wgraj plik raportu w panelu bocznym, aby rozpocząć analizę.")
    st.stop()

try:
    portfolio = parse_xtb_report(uploaded, uploaded.name)
except (ValueError, pd.errors.ParserError) as exc:
    st.error(f"Błąd importu pliku: {exc}")
    st.stop()

with st.spinner("Pobieranie aktualnych cen z Yahoo Finance…"):
    analyzed = analyze_portfolio(portfolio)
    summary = portfolio_summary(analyzed)

# --- Metryki główne ---
st.subheader("Podsumowanie portfela")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Całkowita wartość",
        value=_format_currency(summary["wartosc_calkowita"]),
    )
with col2:
    st.metric(
        label="Łączny koszt (baza)",
        value=_format_currency(summary["koszt_calkowity"]),
    )
with col3:
    pnl = summary["zysk_strata_laczny"]
    st.metric(
        label="Łączny zysk / strata",
        value=_format_currency(pnl),
        delta=f"{summary['roi_laczny_pct']:.2f}% ROI",
        delta_color=_pnl_color(pnl),
    )

# Ostrzeżenie o brakujących cenach
missing_prices = analyzed["cena_rynkowa"].isna().sum()
if missing_prices > 0:
    tickers = analyzed.loc[analyzed["cena_rynkowa"].isna(), "ticker_yahoo"].tolist()
    st.warning(
        f"Nie udało się pobrać ceny dla {missing_prices} pozycji: "
        f"{', '.join(tickers)}. Sprawdź mapowanie w importer.py."
    )

# --- Wykresy ---
st.subheader("Wizualizacje")
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.plotly_chart(_build_pie_chart(analyzed), use_container_width=True)

with chart_col2:
    st.plotly_chart(_build_pnl_bar_chart(analyzed), use_container_width=True)

# --- Tabela pozycji ---
st.subheader("Otwarte pozycje")
_display_summary_table(analyzed)
