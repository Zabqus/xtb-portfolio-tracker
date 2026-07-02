"""
Podstrona: konsensusy analityków i syntetyczne sygnały kup / trzymaj / sprzedaj.
"""

import pandas as pd
import streamlit as st

from core.analyst_consensus import (
    fetch_analyst_consensus,
    format_recommendation,
    rating_bucket,
    rating_momentum_label,
)
from core.consensus_snapshots import (
    add_consensus_snapshot,
    consensus_snapshot_days_ago,
    latest_consensus_snapshot,
    rating_distribution_weights,
    snapshot_rating_distribution,
)
from core.fundamentals import fetch_fundamentals
from core.range_52w import range_position_52w
from core.session import get_analyzed_open, get_display_currency, get_report
from core.signals import (
    SIGNAL_BUY,
    SIGNAL_HOLD,
    SIGNAL_SELL,
    consensus_score,
    evaluate_signal,
    pl_score,
    technical_score,
)
from core.technicals import fetch_technicals, latest_indicator_snapshot
from ui.chart_navigation import render_navigable_chart
from ui.consensus_charts import (
    build_consensus_bullet_chart,
    build_pnl_vs_consensus_scatter,
    build_rating_distribution_chart,
    build_signal_radar,
    build_target_price_fan,
    build_tech_vs_consensus_bubble,
    build_upside_ladder,
)
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page

bootstrap_page()
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
        "target_low_price": consensus.target_low_price,
        "target_high_price": consensus.target_high_price,
        "recommendation_key": consensus.recommendation_key,
        "number_of_analyst_opinions": consensus.number_of_analyst_opinions,
        "pe_ratio": fundamentals.pe_ratio,
        "week_52_low": fundamentals.week_52_low,
        "week_52_high": fundamentals.week_52_high,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_technical_scores(ticker_yahoo: str) -> tuple[float, float]:
    """Wyniki techniki i konsensusu (0–4) do mapy analityk vs technika."""
    snapshot: dict = {}
    try:
        tech_df = fetch_technicals(ticker_yahoo, "1Y")
        snapshot = latest_indicator_snapshot(tech_df)
    except Exception:
        pass

    consensus = None
    upside = None
    try:
        consensus = fetch_analyst_consensus(ticker_yahoo)
        if consensus.target_mean_price and consensus.current_price:
            upside = (consensus.target_mean_price / consensus.current_price - 1) * 100
    except Exception:
        pass

    tech, _, _, _ = technical_score(snapshot)
    cons, _ = consensus_score(consensus, upside)
    return tech, cons


def _upside(target: float | None, price: float | None) -> float | None:
    if target is None or price is None or pd.isna(price) or price == 0:
        return None
    return (target - price) / price * 100


_range_position = range_position_52w


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

    total_value = float(analyzed["market_value"].sum()) if "market_value" in analyzed.columns else 0.0
    prev_snapshot = latest_consensus_snapshot()
    prev_positions = (prev_snapshot or {}).get("positions") or {}

    rows: list[dict] = []
    progress = st.progress(0.0, text="Pobieranie konsensusów…")
    total = len(analyzed)
    for i, (_, pos) in enumerate(analyzed.iterrows(), start=1):
        ticker_yahoo = pos["ticker_yahoo"]
        ticker_xtb = pos["ticker_xtb"]
        market_price = pos.get("market_price")
        roi_pct = pos.get("roi_pct")
        avg_price = pos.get("avg_price")
        market_value = pos.get("market_value")
        weight_pct = (
            float(market_value) / total_value * 100
            if total_value > 0 and market_value is not None and not pd.isna(market_value)
            else None
        )

        bundle = {
            "target_mean_price": None,
            "target_low_price": None,
            "target_high_price": None,
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

        rating_key = (bundle["recommendation_key"] or "").strip().lower().replace(" ", "_")
        prev_rating = (prev_positions.get(ticker_xtb) or {}).get("rating_key")
        momentum = rating_momentum_label(prev_rating, rating_key)

        tech_sc, cons_sc = 2.0, 2.0
        try:
            tech_sc, cons_sc = _fetch_technical_scores(ticker_yahoo)
        except Exception:
            pass

        upside = _upside(bundle["target_mean_price"], market_price)
        rows.append(
            {
                "Ticker": ticker_xtb,
                "Cena": market_price,
                "avg_price": avg_price,
                "Cel": bundle["target_mean_price"],
                "target_low": bundle["target_low_price"],
                "target_high": bundle["target_high_price"],
                "week_52_low": bundle["week_52_low"],
                "week_52_high": bundle["week_52_high"],
                "Upside %": round(upside, 1) if upside is not None else None,
                "Rating": format_recommendation(bundle["recommendation_key"]),
                "Δ Rating": momentum,
                "Analitycy": bundle["number_of_analyst_opinions"],
                "P/E": round(bundle["pe_ratio"], 1) if bundle["pe_ratio"] is not None else None,
                "Pozycja 52W": _range_position(
                    market_price, bundle["week_52_low"], bundle["week_52_high"]
                ),
                "Twój P&L %": round(roi_pct, 1) if roi_pct is not None and not pd.isna(roi_pct) else None,
                "weight_pct": round(weight_pct, 2) if weight_pct is not None else None,
                "technical_score": round(tech_sc, 2),
                "consensus_score": round(cons_sc, 2),
                "_rating_key": rating_key,
                "rating_bucket": rating_bucket(rating_key),
            }
        )
        progress.progress(i / total, text=f"Pobieranie konsensusów… ({i}/{total})")
    progress.empty()

    table = pd.DataFrame(rows)
    if not table.empty and "weight_pct" in table.columns:
        table["weighted_upside"] = table.apply(
            lambda r: (r["Upside %"] * r["weight_pct"] / 100)
            if pd.notna(r.get("Upside %")) and pd.notna(r.get("weight_pct"))
            else None,
            axis=1,
        )

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

    snap_col1, snap_col2 = st.columns([3, 1])
    with snap_col1:
        if prev_snapshot:
            st.caption(
                f"Ostatni snapshot konsensusu: **{prev_snapshot.get('date', '—')}** "
                "— kolumna Δ Rating porównuje z tym stanem."
            )
        else:
            st.caption(
                "Zapisz snapshot konsensusu, aby śledzić zmiany ratingów (↑ poprawa, ↓ pogorszenie)."
            )
    with snap_col2:
        if st.button("Zapisz snapshot konsensusu", use_container_width=True):
            _, msg = add_consensus_snapshot(table)
            st.success(msg)
            st.rerun()

    hidden_cols = [
        "_rating_key",
        "rating_bucket",
        "avg_price",
        "target_low",
        "target_high",
        "week_52_low",
        "week_52_high",
        "weight_pct",
        "weighted_upside",
        "technical_score",
        "consensus_score",
    ]
    display = table.drop(columns=[c for c in hidden_cols if c in table.columns])
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cena": st.column_config.NumberColumn(f"Cena ({currency})", format="%.2f"),
            "Cel": st.column_config.NumberColumn("Cel analityków", format="%.2f"),
            "Upside %": st.column_config.NumberColumn("Upside %", format="%.1f%%"),
            "Δ Rating": st.column_config.TextColumn(
                "Δ Rating",
                help="Zmiana rekomendacji od ostatniego zapisanego snapshotu (↑ / ↓ / →).",
            ),
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

    st.divider()
    st.subheader("Wizualizacje konsensusu")

    chart_left, chart_right = st.columns(2)
    with chart_left:
        render_navigable_chart(
            build_upside_ladder(table, currency),
            "consensus_upside_ladder",
            tickers=table["Ticker"].tolist(),
        )
    with chart_right:
        render_navigable_chart(
            build_pnl_vs_consensus_scatter(table, currency),
            "consensus_pnl_scatter",
            tickers=table["Ticker"].tolist(),
        )

    dist_left, dist_right = st.columns(2)
    with dist_left:
        current_dist = rating_distribution_weights(table)
        month_ago = consensus_snapshot_days_ago(30)
        compare_snapshot = month_ago
        if compare_snapshot is None and prev_snapshot:
            compare_snapshot = prev_snapshot
        prev_dist = snapshot_rating_distribution(compare_snapshot) if compare_snapshot else None
        st.plotly_chart(
            build_rating_distribution_chart(current_dist, prev_dist or None),
            use_container_width=True,
            key="consensus_rating_dist",
        )
        if compare_snapshot and compare_snapshot.get("date"):
            st.caption(f"Porównanie ze snapshotem z {compare_snapshot['date']}.")
        elif not prev_snapshot:
            st.caption("Zapisz snapshot, aby porównać rozkład rekomendacji w czasie.")
    with dist_right:
        render_navigable_chart(
            build_tech_vs_consensus_bubble(table, currency),
            "consensus_tech_bubble",
            tickers=table["Ticker"].tolist(),
        )

    with st.expander("Target price fan i składniki sygnału", expanded=False):
        fan_tickers = table["Ticker"].dropna().tolist()
        if fan_tickers:
            selected = st.selectbox("Wybierz pozycję", fan_tickers, key="consensus_fan_ticker")
            row = table.loc[table["Ticker"] == selected].iloc[0]
            fan_col, radar_col = st.columns(2)
            with fan_col:
                st.plotly_chart(
                    build_target_price_fan(
                        ticker=selected,
                        current_price=row.get("Cena"),
                        avg_price=row.get("avg_price"),
                        target_mean=row.get("Cel"),
                        target_low=row.get("target_low"),
                        target_high=row.get("target_high"),
                        currency=currency,
                    ),
                    use_container_width=True,
                    key="consensus_target_fan",
                )
            with radar_col:
                st.plotly_chart(
                    build_signal_radar(
                        ticker=selected,
                        technical_score=float(row.get("technical_score") or 2.0),
                        consensus_score=float(row.get("consensus_score") or 2.0),
                        pl_score=pl_score(row.get("Twój P&L %")),
                    ),
                    use_container_width=True,
                    key="consensus_signal_radar",
                )
        else:
            st.info("Brak pozycji do wyświetlenia target price fan.")

    with st.expander("Ranking z bullet chart (cel vs zakup vs rynek)", expanded=False):
        render_navigable_chart(
            build_consensus_bullet_chart(table, currency),
            "consensus_bullet",
            tickers=table["Ticker"].tolist(),
        )
        st.caption(
            "Na osi: szary pas = zakres 52W, niebieski = cena rynkowa, "
            "pomarańczowy = śr. cena zakupu, zielony = cel analityków."
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
