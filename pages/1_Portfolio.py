"""
Podstrona: otwarte pozycje i analiza bieżącego portfela.
"""

import streamlit as st

from core.analyzer import portfolio_summary
from core.session import get_analyzed_open, get_display_currency, get_report
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

st.subheader("Otwarte pozycje")
render_open_positions_table(analyzed, currency)
