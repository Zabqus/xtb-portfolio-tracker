"""
Podstrona: otwarte pozycje i analiza bieżącego portfela.
"""

import streamlit as st

from core.analyzer import portfolio_summary
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_report,
    set_selected_ticker,
)
from ui.charts import build_allocation_pie, build_pnl_bar_chart
from ui.formatters import format_currency, pnl_delta_color
from ui.sidebar import render_import_sidebar
from ui.tables import render_open_positions_table

st.title("📊 Portfolio – otwarte pozycje")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym (strona główna lub tutaj).")
    st.stop()

report = get_report()
if report is None:
    st.stop()

with st.spinner("Pobieranie cen i kursów walut…"):
    analyzed = get_analyzed_open()

if analyzed is None:
    st.error("Nie udało się przeanalizować portfela.")
    st.stop()

summary = portfolio_summary(analyzed)
currency = str(summary["display_currency"])

fx_rates = analyzed.attrs.get("fx_rates", {})
if len(fx_rates) > 1:
    with st.expander("Kursy użyte do przeliczenia"):
        rates_txt = ", ".join(
            f"1 {c} = {fx_rates[c]:.4f} {currency}"
            for c in sorted(fx_rates)
            if c != currency
        )
        st.caption(rates_txt or "—")

st.subheader("Podsumowanie portfela")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Całkowita wartość", format_currency(summary["total_value"], currency))
with col2:
    st.metric("Łączny koszt", format_currency(summary["total_cost"], currency))
with col3:
    pnl = summary["total_pnl"]
    st.metric(
        "Łączny zysk / strata",
        format_currency(pnl, currency),
        delta=f"{summary['total_roi_pct']:.2f}% ROI",
        delta_color=pnl_delta_color(pnl),
    )
with col4:
    st.metric("Waluta konta", summary["account_currency"])

missing = analyzed["market_price"].isna().sum()
if missing > 0:
    tickers = analyzed.loc[analyzed["market_price"].isna(), "ticker_yahoo"].tolist()
    st.warning(f"Brak ceny Yahoo dla: {', '.join(tickers)}. Sprawdź core/importer_maps.py.")

st.subheader("Wizualizacje")
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(build_allocation_pie(analyzed, currency), use_container_width=True)
with c2:
    st.plotly_chart(build_pnl_bar_chart(analyzed, currency), use_container_width=True)

if st.button("Sektor i region (USA / EU / PL) →", key="portfolio_to_allocation"):
    st.switch_page("pages/6_Alokacja.py")

st.subheader("Otwarte pozycje")
render_open_positions_table(analyzed, currency)

st.divider()
st.subheader("Analiza pojedynczej pozycji")
tickers = analyzed["ticker_xtb"].tolist()
pick = st.selectbox(
    "Wybierz ticker do szczegółowej analizy",
    tickers,
    key="portfolio_pick_ticker",
)
col_a, col_b = st.columns(2)
with col_a:
    if st.button("Analiza pozycji →", type="primary"):
        set_selected_ticker(pick)
        st.switch_page("pages/2_Pozycja.py")
with col_b:
    if st.button("Analiza techniczna →"):
        set_selected_ticker(pick)
        st.switch_page("pages/4_Analiza.py")
