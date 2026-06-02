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
from waluty import WALUTY_WSPIERANE

st.set_page_config(
    page_title="XTB Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

st.title("📈 XTB Portfolio Tracker")
st.caption("Lokalny dashboard do analizy portfela akcji i ETF-ów (wielowalutowo)")


def _format_currency(value: float, currency: str) -> str:
    """Formatuje kwotę do wyświetlenia w metrykach."""
    if pd.isna(value):
        return "—"
    return f"{value:,.2f} {currency}"


def _pnl_color(value: float) -> str:
    """Zwraca kolor Streamlit dla zysku (zielony) lub straty (czerwony)."""
    if pd.isna(value) or value == 0:
        return "off"
    return "normal" if value > 0 else "inverse"


def _build_pie_chart(df: pd.DataFrame, waluta: str) -> go.Figure:
    """Wykres kołowy – udział procentowy pozycji w wartości portfela."""
    chart_df = df.dropna(subset=["wartosc_rynkowa"]).copy()
    label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"

    fig = px.pie(
        chart_df,
        names=label_col,
        values="wartosc_rynkowa",
        title=f"Struktura portfela (% wartości, {waluta})",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(showlegend=True, height=450)
    return fig


def _build_pnl_bar_chart(df: pd.DataFrame, waluta: str) -> go.Figure:
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
        title=f"Zysk / strata na pozycjach ({waluta})",
        xaxis_title="Instrument",
        yaxis_title=f"Zysk / strata ({waluta})",
        height=450,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig


def _display_summary_table(df: pd.DataFrame, waluta: str) -> None:
    """Tabela podsumowująca wszystkie otwarte pozycje."""
    display = df.copy()
    rename = {
        "ticker_xtb": "Ticker XTB",
        "ticker_yahoo": "Ticker Yahoo",
        "waluta": "Waluta",
        "ilosc": "Ilość",
        "srednia_cena": "Śr. cena (waluta instr.)",
        "cena_rynkowa": "Cena rynkowa",
        "koszt_pozycji": f"Koszt ({waluta})",
        "wartosc_rynkowa": f"Wartość ({waluta})",
        "zysk_strata": f"Zysk / strata ({waluta})",
        "roi_pct": "ROI %",
    }
    display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})

    numeric_cols = [c for c in display.columns if c not in ("Ticker XTB", "Ticker Yahoo", "Waluta")]
    for col in numeric_cols:
        display[col] = display[col].map(lambda x: round(x, 2) if pd.notna(x) else None)

    st.dataframe(display, use_container_width=True, hide_index=True)


# --- Sidebar ---
with st.sidebar:
    st.header("Import z XTB")
    uploaded = st.file_uploader(
        "Wgraj eksport z XTB (Excel lub CSV)",
        type=["csv", "xlsx", "xls"],
    )
    st.markdown(
        """
        **Eksport XTB:** arkusz *Cash Operations* (konto PLN lub EUR).

        Program wykrywa **walutę konta** i **walutę każdej pozycji**,
        a sumy przelicza do wybranej waluty wyświetlania.
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

waluta_konta = portfolio.attrs.get("waluta_konta", "EUR")
numer_konta = portfolio.attrs.get("numer_konta")

with st.sidebar:
    st.divider()
    st.subheader("Waluta")
    if numer_konta:
        st.caption(f"Konto: {numer_konta}")
    st.info(f"Wykryta waluta konta: **{waluta_konta}**")
    waluta_wyswietlania = st.selectbox(
        "Przelicz sumy na walutę",
        WALUTY_WSPIERANE,
        index=WALUTY_WSPIERANE.index(waluta_konta)
        if waluta_konta in WALUTY_WSPIERANE
        else 0,
    )

with st.spinner("Pobieranie cen i kursów walut…"):
    try:
        analyzed = analyze_portfolio(portfolio, waluta_wyswietlania=waluta_wyswietlania)
        summary = portfolio_summary(analyzed)
    except ValueError as exc:
        st.error(f"Błąd analizy: {exc}")
        st.stop()

waluta = str(summary["waluta_wyswietlania"])

# Podgląd kursów FX
kursy = analyzed.attrs.get("kursy_fx", {})
if len(kursy) > 1:
    with st.expander("Kursy użyte do przeliczenia"):
        kursy_txt = ", ".join(
            f"1 {w} = {kursy[w]:.4f} {waluta}" for w in sorted(kursy) if w != waluta
        )
        st.caption(kursy_txt or "—")

st.subheader("Podsumowanie portfela")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Całkowita wartość", _format_currency(summary["wartosc_calkowita"], waluta))
with col2:
    st.metric("Łączny koszt", _format_currency(summary["koszt_calkowity"], waluta))
with col3:
    pnl = summary["zysk_strata_laczny"]
    st.metric(
        "Łączny zysk / strata",
        _format_currency(pnl, waluta),
        delta=f"{summary['roi_laczny_pct']:.2f}% ROI",
        delta_color=_pnl_color(pnl),
    )
with col4:
    st.metric("Waluta konta", waluta_konta)

missing_prices = analyzed["cena_rynkowa"].isna().sum()
if missing_prices > 0:
    tickers = analyzed.loc[analyzed["cena_rynkowa"].isna(), "ticker_yahoo"].tolist()
    st.warning(f"Brak ceny Yahoo dla: {', '.join(tickers)}. Sprawdź mapowanie w importer.py.")

st.subheader("Wizualizacje")
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(_build_pie_chart(analyzed, waluta), use_container_width=True)
with chart_col2:
    st.plotly_chart(_build_pnl_bar_chart(analyzed, waluta), use_container_width=True)

st.subheader("Otwarte pozycje")
_display_summary_table(analyzed, waluta)

# Propozycje rozwoju
with st.expander("💡 Pomysły na kolejne funkcje"):
    st.markdown(
        """
        | Priorytet | Funkcja | Opis |
        |-----------|---------|------|
        | Wysoki | **Łączenie kont PLN + EUR** | Wgranie dwóch plików i jeden widok całego majątku |
        | Wysoki | **Historia zamkniętych pozycji** | Arkusz *Closed Positions* – statystyki realizowanych zysków |
        | Średni | **Wykres wartości w czasie** | Saldo portfela po każdej transakcji z Cash Operations |
        | Średni | **Dywidendy i opłaty** | Osobna sekcja kosztów (spread, swap, prowizje) |
        | Średni | **Alokacja geograficzna** | % portfela: USA / Europa / Polska na podstawie tickera |
        | Średni | **Eksport do PDF/Excel** | Raport miesięczny jednym kliknięciem |
        | Niski | **Alerty cenowe** | Powiadomienie gdy pozycja +/- X% od zakupu |
        | Niski | **Porównanie z WIG/WIG20** | Benchmark polskiego rynku dla konta PLN |
        | Niski | **API zamiast pliku** | Automatyczny import (jeśli XTB udostępni) |
        """
    )
