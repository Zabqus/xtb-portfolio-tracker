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
from core.rebalance import compute_rebalance, normalize_targets, suggest_cash_allocation
from core.session import get_analyzed_open, get_report
from ui.allocation_charts import (
    REGION_COLORS,
    build_breakdown_bar,
    build_breakdown_pie,
    build_rebalance_chart,
)
from ui.formatters import format_currency
from ui.plotly_theme import style_figure
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page

bootstrap_page()
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
st.subheader("⚖️ Rebalancing — sugestie dokupień")
st.caption(
    "Ustaw docelowy udział koszyków, a aplikacja policzy, ile dokupić lub zredukować, "
    "by trafić w cel. Opcjonalnie rozdziel nową gotówkę bez sprzedaży istniejących pozycji."
)

rb_dim = st.radio(
    "Wymiar rebalansu", ["Sektor", "Region"], horizontal=True, key="rebalance_dim"
)
rb_group_col = "sector" if rb_dim == "Sektor" else "region"
rb_breakdown = sector_df if rb_dim == "Sektor" else region_df

if rb_breakdown.empty or len(rb_breakdown) < 2:
    st.info("Za mało koszyków do rebalansu (potrzebne co najmniej dwa).")
else:
    total_value = float(rb_breakdown["market_value"].sum())

    target_editor = rb_breakdown[[rb_group_col, "weight_pct"]].copy()
    target_editor.columns = ["Koszyk", "Obecnie %"]
    target_editor["Obecnie %"] = target_editor["Obecnie %"].round(1)
    target_editor["Cel %"] = target_editor["Obecnie %"].round(0)

    edited = st.data_editor(
        target_editor,
        hide_index=True,
        use_container_width=True,
        disabled=["Koszyk", "Obecnie %"],
        column_config={
            "Cel %": st.column_config.NumberColumn(
                "Cel %", min_value=0.0, max_value=100.0, step=1.0,
                help="Docelowy udział koszyka (suma powinna wynosić 100%).",
            )
        },
        key="rebalance_targets_editor",
    )

    target_map = {
        str(r["Koszyk"]): float(r["Cel %"]) for _, r in edited.iterrows()
    }
    _, target_sum = normalize_targets(target_map)

    new_cash = st.number_input(
        f"Nowa gotówka do zainwestowania ({currency}, opcjonalnie)",
        min_value=0.0, value=0.0, step=100.0, key="rebalance_new_cash",
    )

    if abs(target_sum - 100.0) > 0.5:
        st.warning(f"Suma celów = **{target_sum:.0f}%** (powinno być 100%). Wynik i tak policzę proporcjonalnie.")

    rb = compute_rebalance(rb_breakdown, target_map, rb_group_col, new_cash=new_cash)
    if not rb.empty:
        st.plotly_chart(build_rebalance_chart(rb, rb_group_col), use_container_width=True)

        rb_show = rb.copy()
        rb_show["current_pct"] = rb_show["current_pct"].round(1)
        rb_show["target_pct"] = rb_show["target_pct"].round(1)
        rb_show["drift_pp"] = rb_show["drift_pp"].round(1)
        rb_show["delta_value"] = rb_show["delta_value"].round(2)
        st.dataframe(
            rb_show[[rb_group_col, "current_pct", "target_pct", "drift_pp", "delta_value", "action"]].rename(
                columns={
                    rb_group_col: "Koszyk",
                    "current_pct": "Obecnie %",
                    "target_pct": "Cel %",
                    "drift_pp": "Dryf (pp)",
                    "delta_value": f"Zmiana ({currency})",
                    "action": "Akcja",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Dryf = obecny − docelowy udział (pp). Dodatnia „Zmiana” = dokup, ujemna = zredukuj. "
            "Sugestie na poziomie koszyków — konkretny instrument w koszyku wybierasz sam."
        )

        if new_cash > 0:
            cash_alloc = suggest_cash_allocation(rb_breakdown, target_map, rb_group_col, new_cash)
            if not cash_alloc.empty:
                st.markdown(f"**Rozdział nowej gotówki ({format_currency(new_cash, currency)}) — tylko dokupienia:**")
                ca = cash_alloc.copy()
                ca["suggested_buy"] = ca["suggested_buy"].round(2)
                ca["buy_share_pct"] = ca["buy_share_pct"].round(1)
                st.dataframe(
                    ca[[rb_group_col, "suggested_buy", "buy_share_pct"]].rename(
                        columns={
                            rb_group_col: "Koszyk",
                            "suggested_buy": f"Dokup ({currency})",
                            "buy_share_pct": "Udział wpłaty %",
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
        st.plotly_chart(style_figure(fig_ce), use_container_width=True)
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

    st.caption(
        "ℹ️ To **waluta notowań instrumentu**, nie waluta konta. Kupując na koncie EUR "
        "akcję notowaną w USD, masz ekspozycję na USD — to ona decyduje o ryzyku kursowym."
    )

    # Multi-account: rozbicie ekspozycji walutowej per konto.
    report_alloc = get_report()
    if (
        report_alloc is not None
        and report_alloc.is_merged
        and "account_label" in analyzed.columns
        and analyzed["account_label"].nunique() > 1
    ):
        st.markdown("**Ekspozycja walutowa per konto**")
        st.caption(
            "Pokazuje, jak każde konto (np. PLN i EUR) realnie rozkłada się na waluty "
            "instrumentów — konto EUR może być pełne aktywów USD."
        )
        acc_ccy = (
            analyzed.dropna(subset=["market_value", "currency", "account_label"])
            .groupby(["account_label", "currency"], as_index=False)["market_value"]
            .sum()
        )
        if not acc_ccy.empty:
            fig_acc = px.bar(
                acc_ccy,
                x="account_label",
                y="market_value",
                color="currency",
                title=f"Waluta instrumentów per konto ({currency})",
                color_discrete_map={"USD": "#2196F3", "EUR": "#4CAF50", "PLN": "#FF9800", "GBP": "#9C27B0"},
                text_auto=".2s",
            )
            fig_acc.update_layout(
                height=380, barmode="stack",
                xaxis_title="Konto", yaxis_title=f"Wartość ({currency})",
                legend_title="Waluta instr.",
            )
            st.plotly_chart(style_figure(fig_acc), use_container_width=True)

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
