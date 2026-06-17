"""
Podstrona: konsensusy analityków i syntetyczne sygnały kup / trzymaj / sprzedaj.
"""

import pandas as pd
import streamlit as st

from core.analyst_consensus import fetch_analyst_consensus, format_recommendation
from core.fundamentals import fetch_fundamentals
from core.session import get_analyzed_open, get_display_currency, get_report
from core.signals import (
    SIGNAL_BUY,
    SIGNAL_HOLD,
    SIGNAL_SELL,
    evaluate_signal,
)
from core.technicals import fetch_technicals, latest_indicator_snapshot
from ui.sidebar import render_import_sidebar

st.title("🎯 Konsensusy i sygnały")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

report = get_report()
if report is None:
    st.stop()

analyzed = get_analyzed_open()
if analyzed is None or analyzed.empty:
    st.warning("Brak otwartych pozycji do analizy.")
    st.stop()

currency = get_display_currency()

BUY_RATINGS = {"strong_buy", "buy"}


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_consensus_bundle(ticker_yahoo: str) -> dict:
    """Pobiera konsensus + fundamenty dla jednego tickera (cache 1h)."""
    consensus = fetch_analyst_consensus(ticker_yahoo)
    fundamentals = fetch_fundamentals(ticker_yahoo)
    return {
        "target_mean_price": consensus.target_mean_price,
        "recommendation_key": consensus.recommendation_key,
        "number_of_analyst_opinions": consensus.number_of_analyst_opinions,
        "pe_ratio": fundamentals.pe_ratio,
        "week_52_low": fundamentals.week_52_low,
        "week_52_high": fundamentals.week_52_high,
    }


def _upside(target: float | None, price: float | None) -> float | None:
    if target is None or price is None or pd.isna(price) or price == 0:
        return None
    return (target - price) / price * 100


def _range_position(price: float | None, low: float | None, high: float | None) -> float | None:
    if price is None or low is None or high is None or pd.isna(price):
        return None
    if high <= low:
        return None
    return max(0.0, min(1.0, (price - low) / (high - low)))


tab_consensus, tab_signals = st.tabs(
    ["📈 Konsensusy analityków", "🎯 Sygnały — kup / trzymaj / sprzedaj"]
)

# --- Zakładka 1: Konsensusy analityków ---
with tab_consensus:
    st.subheader("Konsensus analityków dla otwartych pozycji")
    st.caption(
        "Cele i rekomendacje z Yahoo Finance (`Ticker.info`). "
        "Dla ETF-ów i małych spółek dane bywają niedostępne (—)."
    )

    rows: list[dict] = []
    progress = st.progress(0.0, text="Pobieranie konsensusów…")
    total = len(analyzed)
    for i, (_, pos) in enumerate(analyzed.iterrows(), start=1):
        ticker_yahoo = pos["ticker_yahoo"]
        ticker_xtb = pos["ticker_xtb"]
        market_price = pos.get("market_price")
        roi_pct = pos.get("roi_pct")

        bundle = {
            "target_mean_price": None,
            "recommendation_key": None,
            "number_of_analyst_opinions": None,
            "pe_ratio": None,
            "week_52_low": None,
            "week_52_high": None,
        }
        try:
            bundle = _fetch_consensus_bundle(ticker_yahoo)
        except Exception:
            st.warning(f"Nie udało się pobrać konsensusu dla {ticker_xtb} ({ticker_yahoo}).")

        upside = _upside(bundle["target_mean_price"], market_price)
        rows.append(
            {
                "Ticker": ticker_xtb,
                "Cena": market_price,
                "Cel": bundle["target_mean_price"],
                "Upside %": round(upside, 1) if upside is not None else None,
                "Rating": format_recommendation(bundle["recommendation_key"]),
                "Analitycy": bundle["number_of_analyst_opinions"],
                "P/E": round(bundle["pe_ratio"], 1) if bundle["pe_ratio"] is not None else None,
                "Pozycja 52W": _range_position(
                    market_price, bundle["week_52_low"], bundle["week_52_high"]
                ),
                "Twój P&L %": round(roi_pct, 1) if roi_pct is not None and not pd.isna(roi_pct) else None,
                "_rating_key": (bundle["recommendation_key"] or "").strip().lower().replace(" ", "_"),
            }
        )
        progress.progress(i / total, text=f"Pobieranie konsensusów… ({i}/{total})")
    progress.empty()

    table = pd.DataFrame(rows)

    with_data = table[table["Upside %"].notna()]
    n_buy = int(table["_rating_key"].isin(BUY_RATINGS).sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Pozycje z ratingiem ≥ Kupno", n_buy)
    with c2:
        avg_up = with_data["Upside %"].mean() if not with_data.empty else None
        st.metric("Średni upside %", f"{avg_up:+.1f}%" if avg_up is not None else "—")
    with c3:
        if not with_data.empty:
            top = with_data.loc[with_data["Upside %"].idxmax()]
            st.metric("Najwyższy upside", top["Ticker"], delta=f"{top['Upside %']:+.1f}%")
        else:
            st.metric("Najwyższy upside", "—")
    with c4:
        if not with_data.empty:
            low = with_data.loc[with_data["Upside %"].idxmin()]
            st.metric(
                "Najniższy upside",
                low["Ticker"],
                delta=f"{low['Upside %']:+.1f}%",
                delta_color="inverse",
            )
        else:
            st.metric("Najniższy upside", "—")

    display = table.drop(columns=["_rating_key"])
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cena": st.column_config.NumberColumn(f"Cena ({currency})", format="%.2f"),
            "Cel": st.column_config.NumberColumn("Cel analityków", format="%.2f"),
            "Upside %": st.column_config.NumberColumn("Upside %", format="%.1f%%"),
            "P/E": st.column_config.NumberColumn("P/E", format="%.1f"),
            "Pozycja 52W": st.column_config.ProgressColumn(
                "52W Low → High",
                help="Pozycja aktualnej ceny w zakresie 52-tygodniowym (0 = przy minimum, 1 = przy maksimum).",
                min_value=0.0,
                max_value=1.0,
                format="%.2f",
            ),
            "Twój P&L %": st.column_config.NumberColumn("Twój P&L %", format="%.1f%%"),
        },
    )

# --- Zakładka 2: Sygnały ---
with tab_signals:
    st.subheader("Sygnały syntetyczne (technika + konsensus + P&L)")
    st.caption(
        "Wynik 0–10: technika (40%) + konsensus analityków (40%) + bieżący P&L (20%). "
        "Dane techniczne z okresu 1Y."
    )

    signal_rows: list[dict] = []
    progress2 = st.progress(0.0, text="Liczenie sygnałów…")
    for i, (_, pos) in enumerate(analyzed.iterrows(), start=1):
        ticker_yahoo = pos["ticker_yahoo"]
        ticker_xtb = pos["ticker_xtb"]
        market_price = pos.get("market_price")
        roi_pct = pos.get("roi_pct")
        roi_val = float(roi_pct) if roi_pct is not None and not pd.isna(roi_pct) else None

        snapshot: dict = {}
        try:
            tech_df = fetch_technicals(ticker_yahoo, "1Y")
            snapshot = latest_indicator_snapshot(tech_df)
        except Exception:
            st.warning(f"Brak danych technicznych dla {ticker_xtb} — użyto wartości neutralnych.")

        consensus = None
        bundle_target = None
        try:
            consensus = fetch_analyst_consensus(ticker_yahoo)
            bundle_target = consensus.target_mean_price
        except Exception:
            st.warning(f"Brak konsensusu dla {ticker_xtb} — użyto wartości neutralnych.")

        upside = _upside(bundle_target, market_price)
        result = evaluate_signal(
            ticker_xtb=ticker_xtb,
            snapshot=snapshot,
            consensus=consensus,
            upside_pct=upside,
            roi_pct=roi_val,
        )

        tech_desc = f"{result.trend_ma200}"
        if result.rsi is not None:
            tech_desc += f" · RSI {result.rsi:.0f}"
        cons_desc = result.rating
        if upside is not None:
            cons_desc += f" ({upside:+.1f}%)"

        signal_rows.append(
            {
                "Ticker": ticker_xtb,
                "P&L %": result.roi_pct,
                "Technika": tech_desc,
                "Konsensus": cons_desc,
                "Wynik": result.signal_score,
                "Sygnał": result.signal,
                "Komentarz": result.comment,
            }
        )
        progress2.progress(i / total, text=f"Liczenie sygnałów… ({i}/{total})")
    progress2.empty()

    signals = pd.DataFrame(signal_rows)

    n_buy = int((signals["Sygnał"] == SIGNAL_BUY).sum())
    n_hold = int((signals["Sygnał"] == SIGNAL_HOLD).sum())
    n_sell = int((signals["Sygnał"] == SIGNAL_SELL).sum())
    avg_score = signals["Wynik"].mean() if not signals.empty else 0.0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("🟢 Kup więcej", n_buy)
    with m2:
        st.metric("🟡 Trzymaj", n_hold)
    with m3:
        st.metric("🔴 Rozważ sprzedaż", n_sell)
    with m4:
        st.metric("Średni wynik portfela", f"{avg_score:.1f}/10")

    def _highlight_signal(val: str) -> str:
        colors = {
            SIGNAL_BUY: "background-color: rgba(46, 204, 113, 0.25)",
            SIGNAL_HOLD: "background-color: rgba(243, 156, 18, 0.25)",
            SIGNAL_SELL: "background-color: rgba(231, 76, 60, 0.25)",
        }
        return colors.get(val, "")

    styled = signals.style.map(_highlight_signal, subset=["Sygnał"])

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config={
            "P&L %": st.column_config.NumberColumn("P&L %", format="%.1f%%"),
            "Wynik": st.column_config.ProgressColumn(
                "Wynik (0–10)",
                min_value=0.0,
                max_value=10.0,
                format="%.1f",
            ),
        },
    )

    st.info(
        "ℹ️ Sygnały są heurystykami pomocniczymi, nie stanowią porady inwestycyjnej."
    )
