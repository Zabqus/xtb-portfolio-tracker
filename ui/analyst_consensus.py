"""UI: konsensus analityków (Yahoo Finance)."""

from __future__ import annotations

import streamlit as st

from core.analyst_consensus import (
    AnalystConsensus,
    format_recommendation,
    recommendation_tone,
)


def render_analyst_consensus(consensus: AnalystConsensus, currency_hint: str = "") -> None:
    st.markdown("### Konsensus analityków")
    suffix = f" {currency_hint}" if currency_hint else ""

    if not consensus.has_data:
        st.caption(
            "Yahoo Finance nie zwróciło danych analitycznych dla tego symbolu "
            "(częste dla małych spółek PL lub ETF)."
        )
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "Rekomendacja",
            format_recommendation(consensus.recommendation_key),
            help="Pole recommendationKey z yfinance",
        )
    with c2:
        n = consensus.number_of_analyst_opinions
        st.metric("Liczba analityków", str(n) if n is not None else "—")
    with c3:
        t = consensus.target_mean_price
        st.metric(
            "Śr. cena docelowa",
            f"{t:,.2f}{suffix}" if t is not None else "—",
        )
    with c4:
        p = consensus.current_price
        st.metric(
            "Cena rynkowa",
            f"{p:,.2f}{suffix}" if p is not None else "—",
        )

    upside = consensus.upside_pct
    if upside is not None:
        st.metric(
            "Potencjał vs śr. target",
            f"{upside:+.1f}%",
            delta_color=recommendation_tone(consensus.recommendation_key),
        )

    key = consensus.recommendation_key
    if key:
        st.caption(f"Kod Yahoo: `{key}` · Źródło: yfinance `Ticker.info`")
