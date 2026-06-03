"""
Podstrona: analiza techniczna (MA, RSI, MACD, Bollinger Bands).
"""

import streamlit as st

from core.history import PERIOD_OPTIONS
from core.session import get_analyzed_open, get_selected_ticker, set_selected_ticker
from core.technicals import engine_name, fetch_technicals, latest_indicator_snapshot
from ui.sidebar import render_import_sidebar
from ui.technical_charts import (
    build_bollinger_chart,
    build_macd_chart,
    build_price_ma_rsi_chart,
)

st.title("📉 Analiza techniczna")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

analyzed = get_analyzed_open()
if analyzed is None:
    st.stop()

tickers = analyzed["ticker_xtb"].tolist()
preselect = get_selected_ticker()
default_idx = tickers.index(preselect) if preselect in tickers else 0

selected = st.selectbox(
    "Wybierz instrument",
    tickers,
    index=default_idx,
    format_func=lambda t: f"{t}  →  {analyzed.loc[analyzed['ticker_xtb'] == t, 'ticker_yahoo'].iloc[0]}",
    key="technical_ticker",
)
set_selected_ticker(selected)

yahoo = analyzed.loc[analyzed["ticker_xtb"] == selected, "ticker_yahoo"].iloc[0]
avg_price = float(
    analyzed.loc[analyzed["ticker_xtb"] == selected, "avg_price"].iloc[0]
)

st.caption(
    f"Yahoo: **{yahoo}** · Silnik: **{engine_name()}** "
    "(MA20/50/200, RSI14, MACD, Bollinger)"
)
if engine_name() != "pandas_ta":
    st.info(
        "Biblioteka **pandas_ta** wymaga Pythona **3.12+**. "
        "Używasz fallbacku w czystym **pandas** (te same wskaźniki). "
        "Aby włączyć pandas_ta: zaktualizuj venv do Python 3.12 i `pip install pandas-ta`."
    )

period_label = st.radio(
    "Horyzont (min. ~200 sesji dla MA200)",
    list(PERIOD_OPTIONS.keys()),
    index=2,
    horizontal=True,
    key="technical_period",
)

with st.spinner("Pobieranie danych i liczenie wskaźników…"):
    tech_df = fetch_technicals(yahoo, period_label)

if tech_df.empty:
    st.error(f"Brak danych dla {yahoo}. Sprawdź symbol w core/importer_maps.py.")
    st.stop()

snap = latest_indicator_snapshot(tech_df)

# --- Metryki ---
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.metric("Cena", f"{snap.get('close', 0):,.2f}" if snap.get("close") else "—")
with c2:
    st.metric("MA20", f"{snap.get('ma20', 0):,.2f}" if snap.get("ma20") else "—")
with c3:
    st.metric("MA50", f"{snap.get('ma50', 0):,.2f}" if snap.get("ma50") else "—")
with c4:
    st.metric("MA200", f"{snap.get('ma200', 0):,.2f}" if snap.get("ma200") else "—")
with c5:
    rsi = snap.get("rsi")
    st.metric("RSI(14)", f"{rsi:.1f}" if rsi is not None else "—")
with c6:
    st.metric("Strefa RSI", snap.get("rsi_zone", "—"))

st.caption(f"Trend vs MA200: **{snap.get('trend_ma200', '—')}**")

# Linia średniej ceny zakupu (opcjonalna informacja)
st.caption(f"Twoja śr. cena zakupu (XTB): **{avg_price:,.4f}**")

st.subheader("Wykres techniczny")
st.plotly_chart(
    build_price_ma_rsi_chart(tech_df, selected, entry_price=avg_price),
    use_container_width=True,
)
st.caption(
    "Górny panel: cena + MA20/50/200 · Dolny panel: RSI(14) (30/70). "
    "Pomarańczowa linia — Twoja średnia cena zakupu."
)

tab_macd, tab_bb = st.tabs(["MACD", "Bollinger Bands"])

with tab_macd:
    st.plotly_chart(build_macd_chart(tech_df, selected), use_container_width=True)
    st.caption("MACD (12, 26, 9) — przecięcie z linią sygnału często oznacza zmianę momentum.")

with tab_bb:
    st.plotly_chart(build_bollinger_chart(tech_df, selected), use_container_width=True)
    st.caption(
        "Bollinger (20, 2σ) — cena przy górnej paśmie: silny ruch w górę; "
        "przy dolnej: osłabienie lub wyprzedanie."
    )
