"""
Podstrona: alokacja portfela — sektor i podział geograficzny (USA / EU / PL).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from core.allocation import (
    REGION_ORDER,
    aggregate_breakdown,
    enrich_portfolio_allocation,
    get_currency_exposure,
)
from core.analyzer import portfolio_summary
from core.session import get_analyzed_open, get_report
from ui.allocation_charts import REGION_COLORS, build_breakdown_bar, build_breakdown_pie
from ui.formatters import format_currency
from ui.sidebar import render_import_sidebar

st.title("🌍 Alokacja portfela")

st.caption(
    "Podział **sektorowy** i **geograficzny** (USA / EU / PL) na podstawie wartości rynkowej pozycji. "
    "Dane: Yahoo Finance `sector` i `country` z `.info` (z uzupełnieniem po sufiksie tickera)."
)

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

if get_report() is None:
    st.stop()

with st.spinner("Pobieranie cen, kursów i metadanych Yahoo…"):
    analyzed = get_analyzed_open()

if analyzed is None:
    st.error("Nie udało się przeanalizować portfela.")
    st.stop()

summary = portfolio_summary(analyzed)
currency = str(summary["display_currency"])

with st.spinner("Klasyfikacja sektorów i regionów…"):
    enriched = enrich_portfolio_allocation(analyzed)

if enriched.empty:
    st.warning("Brak pozycji z wartością rynkową do alokacji.")
    st.stop()

sector_df = aggregate_breakdown(enriched, "sector")
region_df = aggregate_breakdown(enriched, "region", sort_order=REGION_ORDER)

st.subheader("Podsumowanie")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Wartość portfela", format_currency(summary["total_value"], currency))
with c2:
    top_sector = sector_df.iloc[0] if not sector_df.empty else None
    if top_sector is not None:
        st.metric(
            "Dominujący sektor",
            str(top_sector["sector"]),
            delta=f"{top_sector['weight_pct']:.1f}%",
        )
with c3:
    top_region = region_df.loc[region_df["weight_pct"].idxmax()] if not region_df.empty else None
    if top_region is not None:
        st.metric(
            "Dominujący region",
            str(top_region["region"]),
            delta=f"{top_region['weight_pct']:.1f}%",
        )

view = st.radio("Widok wykresów", ["Kołowy", "Słupkowy"], horizontal=True, key="allocation_chart_type")

st.subheader("Struktura alokacji")
col_l, col_r = st.columns(2)

build_pie = build_breakdown_pie
build_bar = build_breakdown_bar

with col_l:
    if view == "Kołowy":
        st.plotly_chart(
            build_pie(sector_df, "sector", currency, "Według sektora"),
            use_container_width=True,
        )
    else:
        st.plotly_chart(
            build_bar(sector_df, "sector", currency, "Według sektora"),
            use_container_width=True,
        )

with col_r:
    if view == "Kołowy":
        st.plotly_chart(
            build_pie(
                region_df,
                "region",
                currency,
                "Według regionu",
                color_map=REGION_COLORS,
            ),
            use_container_width=True,
        )
    else:
        st.plotly_chart(
            build_bar(
                region_df,
                "region",
                currency,
                "Według regionu (USA / EU / PL)",
                color_map=REGION_COLORS,
            ),
            use_container_width=True,
        )

unknown_region = enriched[enriched["region"] == "Inne"]
if not unknown_region.empty:
    with st.expander("Pozycje w regionie „Inne” (brak country w Yahoo)"):
        st.dataframe(
            unknown_region[["ticker_xtb", "ticker_yahoo", "country", "weight_pct"]].rename(
                columns={
                    "ticker_xtb": "XTB",
                    "ticker_yahoo": "Yahoo",
                    "country": "Kraj (.info)",
                    "weight_pct": "Udział %",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader("Ekspozycja walutowa")
st.caption(
    "Ile % portfela jest denominowane w każdej walucie. "
    "Ważne przy ocenie ryzyka kursowego (np. umocnienie PLN redukuje wartość aktywów USD/EUR)."
)

currency_exp = get_currency_exposure(analyzed)

if currency_exp.empty:
    st.info("Brak danych o walutach pozycji.")
else:
    ce_col1, ce_col2 = st.columns(2)
    with ce_col1:
        fig_ce = px.pie(
            currency_exp,
            names="currency",
            values="weight_pct",
            title="Ekspozycja walutowa (%)",
            hole=0.35,
            color="currency",
            color_discrete_map={"USD": "#2196F3", "EUR": "#4CAF50", "PLN": "#FF9800"},
        )
        fig_ce.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_ce, use_container_width=True)
    with ce_col2:
        st.dataframe(
            currency_exp.rename(
                columns={
                    "currency": "Waluta",
                    "value": f"Wartość ({currency})",
                    "weight_pct": "Udział %",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    dominant_ccy = currency_exp.iloc[0]["currency"]
    dominant_pct = currency_exp.iloc[0]["weight_pct"]
    if dominant_pct > 70:
        st.info(
            f"Ponad {dominant_pct:.0f}% portfela jest w **{dominant_ccy}**. "
            "Rozważ dywersyfikację walutową lub hedging, jeśli zależy Ci na stabilności w PLN."
        )

st.divider()
st.subheader("Szczegóły per pozycja")

display = enriched.copy()
display["Wartość"] = display["market_value"].apply(lambda v: format_currency(v, currency))
display["Udział %"] = display["weight_pct"].map(lambda v: f"{v:.2f}%")

st.dataframe(
    display[
        [
            "ticker_xtb",
            "ticker_yahoo",
            "name",
            "sector",
            "country",
            "region",
            "Wartość",
            "Udział %",
        ]
    ].rename(
        columns={
            "ticker_xtb": "XTB",
            "ticker_yahoo": "Yahoo",
            "name": "Nazwa",
            "sector": "Sektor",
            "country": "Kraj",
            "region": "Region",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Region: najpierw `country` z Yahoo; jeśli brak — sufiks tickera (np. `.WA` → PL, `.DE` → EU, `.US` / brak sufiksu → USA). "
    "ETF-y często nie mają sektora — pokazujemy kategorię funduszu lub „ETF / fundusz”."
)
