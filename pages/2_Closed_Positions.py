"""
Podstrona: zamknięte pozycje z arkusza Closed Positions.
"""

import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from core.analyzer import closed_positions_summary
from core.session import get_display_currency, get_report
from ui.charts import build_closed_pnl_chart
from ui.formatters import format_currency, pnl_delta_color
from ui.sidebar import render_import_sidebar
from ui.tables import render_closed_positions_table

st.title("📋 Zamknięte pozycje")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

report = get_report()
if report is None:
    st.stop()

closed = report.closed_positions
account_currency = report.account_currency

if closed is None or closed.empty:
    st.warning(
        "Brak danych zamkniętych pozycji w załadowanym pliku. "
        "Upewnij się, że eksport XTB zawiera arkusz **Closed Positions**."
    )
    st.stop()

stats = closed_positions_summary(closed)

st.subheader("Podsumowanie realizacji")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Liczba pozycji", stats["count"])
with col2:
    st.metric(
        "Łączny PnL",
        format_currency(stats["total_pnl"], account_currency),
        delta_color=pnl_delta_color(stats["total_pnl"]),
    )
with col3:
    st.metric("Zyskowne", stats["winners"])
with col4:
    st.metric("Stratne", stats["losers"])

st.caption(f"Win rate: **{stats['win_rate_pct']:.1f}%** · Waluta rozliczenia: **{account_currency}**")

try:
    style_metric_cards(
        background_color="#1e1e2e",
        border_left_color="#4a9eff",
        border_color="#2d2d3f",
        box_shadow="rgba(0,0,0,0.2)",
    )
except Exception:
    pass

st.subheader("Wykres PnL")
st.plotly_chart(
    build_closed_pnl_chart(closed, account_currency),
    use_container_width=True,
)

st.subheader("Szczegóły transakcji")
render_closed_positions_table(closed)

display_currency = get_display_currency()
if display_currency != account_currency:
    st.caption(
        f"Uwaga: PnL w arkuszu XTB jest w walucie konta ({account_currency}). "
        f"Na stronie Portfolio sumy są przeliczane na {display_currency}."
    )
