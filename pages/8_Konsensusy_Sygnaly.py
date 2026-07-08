"""
Podstrona: konsensusy analityków i syntetyczne sygnały kup / trzymaj / sprzedaj.
"""

import pandas as pd
import plotly.graph_objects as go
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
    SIGNAL_PROFILES,
    build_signal_matrix,
    build_stacked_components,
    build_action_ranking,
    build_sanity_checks,
    compute_confidence_score,
    compute_signal_momentum,
    consensus_score,
    evaluate_signal,
    evaluate_signal_profiled,
    interval_agreement_table,
    pl_score,
    technical_score,
)
from core.signal_snapshots import (
    add_signal_snapshot,
    detect_signal_alerts,
    latest_signal_snapshot,
    signal_snapshot_days_ago,
)
from core.technicals import fetch_technicals, latest_indicator_snapshot
from core.trade_analytics import backtest_score_series, backtest_threshold_heuristic
from core.risk_metrics import compute_position_risk_contribution
from ui.chart_navigation import render_navigable_chart
from ui.consensus_charts import (
    build_consensus_bullet_chart,
    build_pnl_vs_consensus_scatter,
    build_rating_distribution_chart,
    build_signal_components_stacked,
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


@st.cache_data(ttl=3600, show_spinner=False)
def _build_historical_score_series(ticker_yahoo: str, interval_label: str = "1Y") -> pd.Series:
    """
    Przybliżony historyczny score (0–10) z samej techniki:
    score = technical(0–4) przeskalowane do 0–10.
    """
    tech_df = fetch_technicals(ticker_yahoo, interval_label)
    if tech_df is None or tech_df.empty or "Date" not in tech_df.columns:
        return pd.Series(dtype=float)
    rows: list[tuple[pd.Timestamp, float]] = []
    for _, r in tech_df.iterrows():
        snapshot = {
            "close": r.get("Close"),
            "ma50": r.get("MA50"),
            "ma200": r.get("MA200"),
            "rsi": r.get("RSI14"),
        }
        tech, _, _, _ = technical_score(snapshot)
        rows.append((pd.to_datetime(r.get("Date")), float(tech / 4.0 * 10.0)))
    if not rows:
        return pd.Series(dtype=float)
    series = pd.Series(data=[v for _, v in rows], index=[d for d, _ in rows], name="score")
    return series.dropna()


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
    profile_name = st.selectbox(
        "Profil decyzyjny",
        options=list(SIGNAL_PROFILES.keys()),
        index=1,
        key="signals_profile_name",
    )
    profile = SIGNAL_PROFILES[profile_name]
    whatif_col1, whatif_col2 = st.columns(2)
    with whatif_col1:
        buy_threshold = st.slider(
            "What-if: próg BUY",
            min_value=6.5,
            max_value=8.0,
            value=float(profile.buy_threshold),
            step=0.1,
            key="signals_buy_threshold_slider",
        )
    with whatif_col2:
        sell_threshold = st.slider(
            "What-if: próg SELL",
            min_value=3.0,
            max_value=5.0,
            value=float(profile.sell_threshold),
            step=0.1,
            key="signals_sell_threshold_slider",
        )
    interval_selected = st.segmented_control(
        "Interwał techniki dla bieżącego sygnału",
        options=["3M", "6M", "1Y"],
        default="1Y",
        key="signals_interval_selected",
    )
    interval_selected = interval_selected or "1Y"
    st.caption(
        "Wynik 0–10: technika (40%) + konsensus analityków (40%) + bieżący P&L (20%). "
        f"Bieżący sygnał liczony dla interwału: **{interval_selected}**; profil: **{profile_name}**."
    )

    signal_rows: list[dict] = []
    signal_results = []
    signal_meta: dict[str, dict] = {}
    interval_scores: dict[str, dict[str, float]] = {"3M": {}, "6M": {}, "1Y": {}}
    progress2 = st.progress(0.0, text="Liczenie sygnałów…")
    for i, (_, pos) in enumerate(analyzed.iterrows(), start=1):
        ticker_yahoo = pos["ticker_yahoo"]
        ticker_xtb = pos["ticker_xtb"]
        market_price = pos.get("market_price")
        roi_pct = pos.get("roi_pct")
        roi_val = float(roi_pct) if roi_pct is not None and not pd.isna(roi_pct) else None

        snapshot: dict = {}
        try:
            tech_df = fetch_technicals(ticker_yahoo, interval_selected)
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
        result = evaluate_signal_profiled(
            ticker_xtb=ticker_xtb,
            snapshot=snapshot,
            consensus=consensus,
            upside_pct=upside,
            roi_pct=roi_val,
            profile=profile,
        )
        signal_results.append(result)
        signal_meta[ticker_xtb] = {
            "analyst_opinions": (
                int(consensus.number_of_analyst_opinions)
                if consensus and consensus.number_of_analyst_opinions is not None
                else 0
            ),
            "has_rsi": snapshot.get("rsi") is not None,
            "has_ma50": snapshot.get("ma50") is not None,
            "has_ma200": snapshot.get("ma200") is not None,
            "ticker_yahoo": ticker_yahoo,
        }

        for interval_label in ("3M", "6M", "1Y"):
            try:
                interval_df = fetch_technicals(ticker_yahoo, interval_label)
                interval_snapshot = latest_indicator_snapshot(interval_df)
                interval_result = evaluate_signal_profiled(
                    ticker_xtb=ticker_xtb,
                    snapshot=interval_snapshot,
                    consensus=consensus,
                    upside_pct=upside,
                    roi_pct=roi_val,
                    profile=profile,
                )
                interval_scores[interval_label][ticker_xtb] = float(interval_result.signal_score)
            except Exception:
                continue

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

    if signal_results:
        score_values = pd.Series([r.signal_score for r in signal_results], dtype=float)
        whatif_buy = int((score_values >= buy_threshold).sum())
        whatif_sell = int((score_values <= sell_threshold).sum())
        whatif_hold = int(len(score_values) - whatif_buy - whatif_sell)
        st.caption(
            f"What-if progi BUY>{buy_threshold:.1f} / SELL<={sell_threshold:.1f}: "
            f"BUY={whatif_buy}, HOLD={whatif_hold}, SELL={whatif_sell}."
        )

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

    st.divider()
    st.subheader("Macierz sygnałów i składowe wyniku")

    matrix_df = build_signal_matrix(signal_results)
    if not matrix_df.empty:
        heatmap_df = matrix_df.rename(
            columns={
                "ticker_xtb": "Ticker",
                "trend_MA200": "Trend MA",
                "konsensus": "Konsensus",
                "score_tech": "Technika",
                "score_consensus": "Konsensus pkt",
                "score_pl": "P&L pkt",
                "score_total": "Wynik końcowy",
                "signal": "Sygnał",
            }
        )[["Ticker", "RSI", "Trend MA", "Konsensus", "P&L_%", "Technika", "Konsensus pkt", "P&L pkt", "Wynik końcowy", "Sygnał"]]

        def _score_color(v: float) -> str:
            if pd.isna(v):
                return ""
            if float(v) >= 7.0:
                return "background-color: rgba(46, 204, 113, 0.25)"
            if float(v) >= 4.5:
                return "background-color: rgba(243, 156, 18, 0.25)"
            return "background-color: rgba(231, 76, 60, 0.25)"

        def _component_color(v: float) -> str:
            if pd.isna(v):
                return ""
            ratio = max(0.0, min(1.0, float(v) / 4.0))
            if ratio >= 0.66:
                return "background-color: rgba(46, 204, 113, 0.18)"
            if ratio >= 0.4:
                return "background-color: rgba(243, 156, 18, 0.18)"
            return "background-color: rgba(231, 76, 60, 0.18)"

        heatmap_styled = (
            heatmap_df.style.map(_score_color, subset=["Wynik końcowy"])
            .map(_component_color, subset=["Technika", "Konsensus pkt"])
            .format(
                {
                    "RSI": "{:.1f}",
                    "P&L_%": "{:.1f}%",
                    "Technika": "{:.2f}",
                    "Konsensus pkt": "{:.2f}",
                    "P&L pkt": "{:.2f}",
                    "Wynik końcowy": "{:.1f}",
                },
                na_rep="—",
            )
        )
        st.dataframe(heatmap_styled, use_container_width=True, hide_index=True)

    components_df = build_stacked_components(signal_results)
    if not components_df.empty:
        st.plotly_chart(
            build_signal_components_stacked(components_df),
            use_container_width=True,
            key="signals_components_stacked",
        )

    st.divider()
    st.subheader("Zgoda interwałów techniki (3M / 6M / 1Y)")
    agreement_df = interval_agreement_table(interval_scores)
    if not agreement_df.empty:
        agreement_view = agreement_df.rename(
            columns={
                "ticker_xtb": "Ticker",
                "score_3M": "Wynik 3M",
                "score_6M": "Wynik 6M",
                "score_1Y": "Wynik 1Y",
                "zgoda_interwałów": "Zgoda interwałów",
            }
        )
        st.dataframe(
            agreement_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Wynik 3M": st.column_config.NumberColumn("Wynik 3M", format="%.1f"),
                "Wynik 6M": st.column_config.NumberColumn("Wynik 6M", format="%.1f"),
                "Wynik 1Y": st.column_config.NumberColumn("Wynik 1Y", format="%.1f"),
            },
        )

    agreement_map = (
        dict(zip(agreement_df["ticker_xtb"], agreement_df["zgoda_interwałów"]))
        if not agreement_df.empty
        else {}
    )
    signal_matrix_raw = build_signal_matrix(signal_results)
    current_signal_state = signal_matrix_raw.copy()
    if not current_signal_state.empty:
        total_mv = float(analyzed["market_value"].sum()) if "market_value" in analyzed.columns else 0.0
        weight_map = (
            dict(zip(analyzed["ticker_xtb"], analyzed["market_value"] / total_mv * 100))
            if total_mv > 0
            else {}
        )
        current_signal_state["interval_agreement"] = current_signal_state["ticker_xtb"].map(agreement_map)
        current_signal_state["weight_pct"] = current_signal_state["ticker_xtb"].map(weight_map)
        current_signal_state["delta_7d"] = None
        current_signal_state["delta_30d"] = None
        current_signal_state["trend_arrow"] = "→"
        current_signal_state["confidence"] = 0.0

        snap_7d = signal_snapshot_days_ago(7)
        snap_30d = signal_snapshot_days_ago(30)
        for idx, row in current_signal_state.iterrows():
            ticker = str(row["ticker_xtb"])
            mom = compute_signal_momentum(
                ticker_xtb=ticker,
                current_score=float(row.get("score_total") or 0),
                snapshot_7d=snap_7d,
                snapshot_30d=snap_30d,
            )
            current_signal_state.at[idx, "delta_7d"] = mom["delta_7d"]
            current_signal_state.at[idx, "delta_30d"] = mom["delta_30d"]
            current_signal_state.at[idx, "trend_arrow"] = mom["trend_arrow"]

            meta = signal_meta.get(ticker, {})
            conf = compute_confidence_score(
                analyst_opinions=meta.get("analyst_opinions"),
                has_rsi=bool(meta.get("has_rsi")),
                has_ma50=bool(meta.get("has_ma50")),
                has_ma200=bool(meta.get("has_ma200")),
                interval_agreement=current_signal_state.at[idx, "interval_agreement"],
            )
            current_signal_state.at[idx, "confidence"] = conf

    st.divider()
    st.subheader("Pewność sygnału i momentum (7d / 30d)")
    if not current_signal_state.empty:
        confidence_view = current_signal_state[
            [
                "ticker_xtb",
                "score_total",
                "confidence",
                "delta_7d",
                "delta_30d",
                "trend_arrow",
                "interval_agreement",
            ]
        ].rename(
            columns={
                "ticker_xtb": "Ticker",
                "score_total": "Wynik",
                "confidence": "Pewność",
                "delta_7d": "Δ 7d",
                "delta_30d": "Δ 30d",
                "trend_arrow": "Trend",
                "interval_agreement": "Zgoda interwałów",
            }
        )
        st.dataframe(
            confidence_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Wynik": st.column_config.NumberColumn("Wynik", format="%.1f"),
                "Pewność": st.column_config.ProgressColumn("Pewność", min_value=0, max_value=100, format="%.0f"),
                "Δ 7d": st.column_config.NumberColumn("Δ 7d", format="%+.2f"),
                "Δ 30d": st.column_config.NumberColumn("Δ 30d", format="%+.2f"),
            },
        )

    snap_col1, snap_col2 = st.columns([3, 1])
    previous_signal_snapshot = latest_signal_snapshot()
    with snap_col1:
        if previous_signal_snapshot:
            st.caption(f"Ostatni snapshot sygnałów: **{previous_signal_snapshot.get('date', '—')}**")
        else:
            st.caption("Zapisz snapshot sygnałów, aby uruchomić pełne alerty i momentum.")
    with snap_col2:
        if st.button("Zapisz snapshot sygnałów", use_container_width=True):
            _, msg = add_signal_snapshot(current_signal_state)
            st.success(msg)
            st.rerun()

    st.divider()
    st.subheader("Alerty sygnałowe")
    signal_alerts = detect_signal_alerts(current_signal_state, previous_signal_snapshot)
    if signal_alerts is not None and not signal_alerts.empty:
        st.dataframe(signal_alerts, use_container_width=True, hide_index=True)
    else:
        st.info("Brak nowych alertów sygnałowych względem ostatniego snapshotu.")

    st.divider()
    st.subheader("Ranking: co zrobić dziś (Top 5)")
    ranking_df = build_action_ranking(current_signal_state, top_n=5)
    if ranking_df is not None and not ranking_df.empty:
        ranking_view = ranking_df[
            ["ticker_xtb", "signal", "score_total", "delta_7d", "weight_pct", "interval_agreement", "urgency"]
        ].rename(
            columns={
                "ticker_xtb": "Ticker",
                "signal": "Sygnał",
                "score_total": "Wynik",
                "delta_7d": "Δ 7d",
                "weight_pct": "Waga %",
                "interval_agreement": "Zgoda interwałów",
                "urgency": "Priorytet",
            }
        )
        st.dataframe(
            ranking_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Wynik": st.column_config.NumberColumn("Wynik", format="%.1f"),
                "Δ 7d": st.column_config.NumberColumn("Δ 7d", format="%+.2f"),
                "Waga %": st.column_config.NumberColumn("Waga %", format="%.2f"),
                "Priorytet": st.column_config.ProgressColumn("Priorytet", min_value=0, max_value=20, format="%.1f"),
            },
        )

    st.divider()
    st.subheader("Kontrybucja do ryzyka portfela")
    risk_df = compute_position_risk_contribution(analyzed, period="1Y")
    if risk_df is not None and not risk_df.empty:
        st.dataframe(
            risk_df.rename(
                columns={
                    "ticker_xtb": "Ticker",
                    "weight_pct": "Waga %",
                    "volatility_pct": "Zmienność %",
                    "avg_corr": "Śr. korelacja",
                    "risk_contribution_pct": "Udział ryzyka %",
                }
            )[["Ticker", "Waga %", "Zmienność %", "Śr. korelacja", "Udział ryzyka %"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Waga %": st.column_config.NumberColumn("Waga %", format="%.2f"),
                "Zmienność %": st.column_config.NumberColumn("Zmienność %", format="%.2f"),
                "Śr. korelacja": st.column_config.NumberColumn("Śr. korelacja", format="%.2f"),
                "Udział ryzyka %": st.column_config.ProgressColumn("Udział ryzyka %", min_value=0, max_value=100, format="%.1f"),
            },
        )
    else:
        st.info("Za mało danych cenowych, aby policzyć kontrybucję ryzyka.")

    st.divider()
    st.subheader("Sanity checks / anty-sygnały")
    sanity_df = build_sanity_checks(current_signal_state)
    if sanity_df is not None and not sanity_df.empty:
        st.dataframe(sanity_df, use_container_width=True, hide_index=True)
    else:
        st.success("Brak wykrytych konfliktów anty-sygnałowych.")

    st.divider()
    st.subheader("Backtest heurystyki sygnału")
    st.caption(
        "What-if progów BUY/SELL działa zarówno dla backtestu uproszczonego (zamknięte pozycje), "
        "jak i rekonstrukcji dziennej (equity curve) dla pojedynczego tickera."
    )
    closed = report.closed_positions if report is not None else None
    if closed is not None and not closed.empty and "ticker_xtb" in closed.columns:
        score_map = {r.ticker_xtb: r.signal_score for r in signal_results}
        close_scores = closed["ticker_xtb"].map(score_map)
        bt = backtest_threshold_heuristic(
            closed,
            close_scores,
            buy_threshold=float(buy_threshold),
            sell_threshold=float(sell_threshold),
        )

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.metric("Transakcje (historia)", int(bt["trades_total"]))
        with b2:
            st.metric("Wzięte przez strategię", int(bt["trades_taken"]))
        with b3:
            st.metric("Win rate: benchmark", f"{bt['hit_rate_baseline']:.1f}%")
        with b4:
            st.metric("Win rate: strategia", f"{bt['hit_rate_strategy']:.1f}%")

        c1, c2 = st.columns(2)
        with c1:
            st.metric(f"P&L benchmark ({currency})", f"{bt['pnl_baseline']:+.2f}")
        with c2:
            st.metric(f"P&L strategia ({currency})", f"{bt['pnl_strategy']:+.2f}")
    else:
        st.info("Brak danych `Closed Positions` — backtest uproszczony wymaga zamkniętych transakcji.")

    st.markdown("**Backtest krok 2: rekonstrukcja dzienna score i equity curve**")
    ticker_options = analyzed["ticker_xtb"].dropna().tolist()
    if ticker_options:
        selected_ticker = st.selectbox("Drill-down ticker", ticker_options, key="signals_drilldown_ticker")
        ticker_row = analyzed.loc[analyzed["ticker_xtb"] == selected_ticker].iloc[0]
        ticker_yahoo = ticker_row["ticker_yahoo"]
        hist_df = fetch_technicals(ticker_yahoo, "1Y")
        score_series = _build_historical_score_series(ticker_yahoo, "1Y")
        bt_daily = backtest_score_series(
            hist_df,
            score_series,
            buy_threshold=float(buy_threshold),
            sell_threshold=float(sell_threshold),
        )
        if bt_daily is not None and not bt_daily.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=bt_daily["Date"],
                    y=bt_daily["equity_buy_hold"],
                    mode="lines",
                    name="Buy & Hold",
                    line=dict(color="#64748B"),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=bt_daily["Date"],
                    y=bt_daily["equity_strategy"],
                    mode="lines",
                    name="Strategia sygnałowa",
                    line=dict(color="#2563EB"),
                )
            )
            fig.update_layout(
                title=f"Equity curve — {selected_ticker} (1Y)",
                xaxis_title="Data",
                yaxis_title="Kapitał (start=1.0)",
                height=360,
                margin=dict(t=56),
            )
            st.plotly_chart(fig, use_container_width=True, key="signals_bt_daily_curve")
        else:
            st.info("Brak wystarczających danych do rekonstrukcji dziennej dla wybranego tickera.")

        st.markdown("**Drill-down: szczegóły tickera**")
        ticker_state = current_signal_state[current_signal_state["ticker_xtb"] == selected_ticker]
        if not ticker_state.empty:
            row = ticker_state.iloc[0]
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.metric("Wynik", f"{float(row.get('score_total') or 0):.1f}/10")
            with d2:
                st.metric("Pewność", f"{float(row.get('confidence') or 0):.0f}/100")
            with d3:
                st.metric("Δ 7d", "—" if pd.isna(row.get("delta_7d")) else f"{float(row.get('delta_7d')):+.2f}")
            with d4:
                st.metric("Zgoda interwałów", str(row.get("interval_agreement") or "—"))

            irow = agreement_df[agreement_df["ticker_xtb"] == selected_ticker]
            if not irow.empty:
                iv = irow.iloc[0]
                s3 = iv.get("score_3M")
                s6 = iv.get("score_6M")
                s1 = iv.get("score_1Y")
                st.caption(
                    "Interwały: "
                    f"3M={f'{float(s3):.1f}' if s3 is not None and not pd.isna(s3) else '—'} / "
                    f"6M={f'{float(s6):.1f}' if s6 is not None and not pd.isna(s6) else '—'} / "
                    f"1Y={f'{float(s1):.1f}' if s1 is not None and not pd.isna(s1) else '—'}"
                )

    st.info(
        "ℹ️ Sygnały są heurystykami pomocniczymi, nie stanowią porady inwestycyjnej."
    )
