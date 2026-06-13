"""
Podstrona: analiza techniczna (MA, RSI, MACD, Bollinger Bands).
"""

import pandas as pd
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

with st.expander("📊 Szybki przegląd — wszystkie pozycje", expanded=False):
    st.caption("MA200 trend, RSI i sygnał MACD dla każdego instrumentu w portfelu.")

    @st.cache_data(ttl=3600, show_spinner=False)
    def _all_technicals_snapshot(tickers_yahoo: tuple[str, ...]) -> list[dict]:
        results = []
        for yahoo_sym in tickers_yahoo:
            try:
                df = fetch_technicals(yahoo_sym, "1Y")
                if df.empty:
                    raise ValueError("empty")
                snap = latest_indicator_snapshot(df)
                macd_val = snap.get("macd")
                macd_sig = snap.get("macd_signal")
                results.append(
                    {
                        "ticker_yahoo": yahoo_sym,
                        "close": snap.get("close"),
                        "ma200": snap.get("ma200"),
                        "trend_ma200": snap.get("trend_ma200", "—"),
                        "rsi": snap.get("rsi"),
                        "rsi_zone": snap.get("rsi_zone", "—"),
                        "macd_signal": (
                            "↑ Bullish"
                            if macd_val is not None and macd_sig is not None and macd_val > macd_sig
                            else "↓ Bearish"
                        ),
                    }
                )
            except Exception:
                results.append(
                    {
                        "ticker_yahoo": yahoo_sym,
                        "close": None,
                        "ma200": None,
                        "trend_ma200": "błąd",
                        "rsi": None,
                        "rsi_zone": "—",
                        "macd_signal": "—",
                    }
                )
        return results

    tickers_yahoo = tuple(
        analyzed.dropna(subset=["ticker_yahoo"])["ticker_yahoo"].astype(str).tolist()
    )

    with st.spinner("Pobieranie wskaźników dla wszystkich pozycji…"):
        snapshot_rows = _all_technicals_snapshot(tickers_yahoo)

    snap_df = pd.DataFrame(snapshot_rows)
    # Dodaj ticker_xtb z analyzed
    ticker_map = dict(zip(analyzed["ticker_yahoo"], analyzed["ticker_xtb"]))
    snap_df["Ticker"] = snap_df["ticker_yahoo"].map(ticker_map)

    # Kolorowanie przez st.dataframe styler
    def color_trend(val) -> str:
        if not isinstance(val, str):
            return ""
        low = val.lower()
        if "powyżej" in low or "bullish" in low or "↑" in val:
            return "color: green"
        if "poniżej" in low or "bearish" in low or "↓" in val:
            return "color: red"
        return ""

    display_snap = snap_df[
        ["Ticker", "close", "ma200", "trend_ma200", "rsi", "rsi_zone", "macd_signal"]
    ].rename(
        columns={
            "close": "Cena",
            "ma200": "MA200",
            "trend_ma200": "Trend vs MA200",
            "rsi": "RSI(14)",
            "rsi_zone": "Strefa RSI",
            "macd_signal": "MACD",
        }
    )
    styler = display_snap.style
    style_map = getattr(styler, "map", None) or styler.applymap
    st.dataframe(
        style_map(color_trend, subset=["Trend vs MA200", "MACD"]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Dane wyliczone z ostatnich 252 sesji. "
        "Wybierz ticker w selectboxie poniżej, aby zobaczyć pełny wykres."
    )

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
if engine_name() == "pandas (fallback)":
    st.info(
        "Silnik: czysty **pandas**. Aby przyspieszyć obliczenia: "
        "**pandas-ta** (Python 3.12+: `pip install pandas-ta`) lub "
        "**TA-Lib** (najpierw biblioteka C, potem `pip install TA-Lib` — patrz README)."
    )
elif engine_name() == "TA-Lib":
    st.caption("Wskaźniki liczone przez **TA-Lib** (natywna biblioteka C).")

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
