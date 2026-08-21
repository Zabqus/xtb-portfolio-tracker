"""
Podstrona: cele inwestycyjne i FIRE.

Dwa kalkulatory na bazie danych, które aplikacja już liczy (wartość portfela,
stopa zwrotu TWR, forward yield, historia wpłat):
- Cel wartości portfela — ile lat/miesięcy do zadanej kwoty.
- FIRE / dochód pasywny — liczba FIRE i moment, gdy dywidendy pokryją wydatki.
"""

import streamlit as st

from core.analyzer import portfolio_summary
from core.dividend_calendar import build_dividend_calendar
from core.goals import (
    DEFAULT_DIV_GROWTH,
    DEFAULT_RETURN,
    DEFAULT_SWR,
    compute_fire,
    format_duration,
    infer_monthly_contribution,
    project_goal,
)
from core.returns import compute_twr, extract_external_cashflows
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_portfolio_timeline,
    get_report,
)
from ui.formatters import format_currency
from ui.goals_charts import build_goal_trajectory_chart, build_snowball_chart
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page

bootstrap_page()
st.title("🎯 Cele i FIRE")
st.caption(
    "Zaplanuj cel wartości portfela i niezależność finansową (FIRE) na bazie "
    "Twojej stopy zwrotu, wpłat i dywidend. Cała matematyka jest lokalna."
)

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

report = get_report()
if report is None:
    st.stop()

with st.spinner("Analiza portfela…"):
    analyzed = get_analyzed_open()

if analyzed is None:
    st.error("Nie udało się przeanalizować portfela.")
    st.stop()

summary = portfolio_summary(analyzed)
currency = str(summary["display_currency"])
current_value = float(summary["total_value"])

# Domyślna stopa zwrotu z annualizowanego TWR (jeśli dostępny).
default_return = DEFAULT_RETURN
inferred_contrib: float | None = None
if report.cash_operations is not None:
    timeline = get_portfolio_timeline()
    twr = compute_twr(timeline, report.cash_operations, target_currency=currency)
    if twr.twr_annualized_pct is not None:
        default_return = round(float(twr.twr_annualized_pct), 1)
    inferred_contrib = infer_monthly_contribution(
        extract_external_cashflows(report.cash_operations)
    )

default_contrib = round(inferred_contrib) if inferred_contrib else 500.0

st.metric("Obecna wartość portfela", format_currency(current_value, currency))

tab_goal, tab_fire = st.tabs(["🎯 Cel wartości", "🔥 FIRE / dochód pasywny"])

# ───────────────────────── Cel wartości ─────────────────────────
with tab_goal:
    st.subheader("Cel wartości portfela")

    default_target = max(100_000.0, round(current_value * 2, -3))
    g1, g2, g3 = st.columns(3)
    with g1:
        target_value = st.number_input(
            f"Kwota docelowa ({currency})",
            min_value=0.0, value=float(default_target), step=10_000.0,
            key="goal_target",
        )
    with g2:
        monthly_contribution = st.number_input(
            f"Miesięczna dopłata ({currency})",
            min_value=0.0, value=float(default_contrib), step=100.0,
            key="goal_contribution",
        )
    with g3:
        annual_return = st.number_input(
            "Zakładany roczny zwrot (%)",
            min_value=-20.0, max_value=50.0, value=float(default_return), step=0.5,
            key="goal_return",
        )

    if inferred_contrib:
        st.caption(
            f"💡 Z historii wpłat wykryto ok. **{format_currency(inferred_contrib, currency)}** "
            "miesięcznie — możesz nadpisać powyżej."
        )

    proj = project_goal(current_value, target_value, monthly_contribution, annual_return)

    st.progress(min(proj.progress_pct / 100.0, 1.0))

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Postęp do celu", f"{proj.progress_pct:.1f}%")
    with m2:
        st.metric("Czas do celu", format_duration(proj.months_to_goal))
    with m3:
        st.metric(
            "Przewidywana data",
            proj.target_date.strftime("%Y-%m") if proj.target_date is not None else "—",
        )
    with m4:
        st.metric("Do uzbierania", format_currency(max(0.0, target_value - current_value), currency))

    if proj.reached_now:
        st.success("🎉 Cel już osiągnięty — gratulacje!")
    elif not proj.ever_reaches:
        st.warning(
            "Przy tych założeniach cel jest nieosiągalny w 40 lat. Zwiększ dopłatę "
            "lub zakładaną stopę zwrotu."
        )

    st.plotly_chart(
        build_goal_trajectory_chart(proj.trajectory, target_value, currency),
        use_container_width=True,
    )
    st.caption(
        "Projekcja: procent składany miesięcznie + stała dopłata. Zwrot i dopłata są "
        "założeniami — rynek nie rośnie liniowo. To orientacja, nie gwarancja."
    )

# ───────────────────────── FIRE ─────────────────────────
with tab_fire:
    st.subheader("FIRE — niezależność finansowa")
    st.caption(
        "FIRE = moment, gdy majątek (reguła 4%) lub same dywidendy pokrywają Twoje "
        "roczne wydatki. Poniżej projekcja na bazie forward yield portfela."
    )

    with st.spinner("Liczenie forward yield portfela…"):
        _, cal_summary = build_dividend_calendar(analyzed, currency)
    yield_pct = float(cal_summary.get("portfolio_yield_pct", 0.0) or 0.0)

    f1, f2, f3 = st.columns(3)
    with f1:
        monthly_expenses = st.number_input(
            f"Miesięczne wydatki ({currency})",
            min_value=0.0, value=4_000.0, step=250.0, key="fire_expenses",
        )
    with f2:
        fire_contribution = st.number_input(
            f"Miesięczna dopłata ({currency})",
            min_value=0.0, value=float(default_contrib), step=100.0, key="fire_contribution",
        )
    with f3:
        fire_return = st.number_input(
            "Roczny zwrot (%)",
            min_value=-20.0, max_value=50.0, value=float(default_return), step=0.5,
            key="fire_return",
        )

    f4, f5, f6 = st.columns(3)
    with f4:
        swr = st.number_input(
            "Bezpieczna stopa wypłaty (%)",
            min_value=1.0, max_value=10.0, value=float(DEFAULT_SWR), step=0.5,
            key="fire_swr",
            help="Reguła 4% → majątek = 25× rocznych wydatków.",
        )
    with f5:
        div_growth = st.number_input(
            "Roczny wzrost dywidend (%)",
            min_value=0.0, max_value=20.0, value=float(DEFAULT_DIV_GROWTH), step=0.5,
            key="fire_div_growth",
        )
    with f6:
        inflation = st.number_input(
            "Inflacja wydatków (%)",
            min_value=0.0, max_value=15.0, value=0.0, step=0.5, key="fire_inflation",
        )

    fire = compute_fire(
        current_value,
        monthly_expenses * 12.0,
        yield_pct,
        fire_contribution,
        fire_return,
        dividend_growth_pct=div_growth,
        swr_pct=swr,
        inflation_pct=inflation,
    )

    st.progress(min(fire.fire_progress_pct / 100.0, 1.0))

    r1, r2, r3 = st.columns(3)
    with r1:
        st.metric(
            "Liczba FIRE",
            format_currency(fire.fire_number, currency),
            help=f"Majątek = roczne wydatki / {swr:.0f}% (reguła {swr:.0f}%).",
        )
    with r2:
        st.metric("Postęp do FIRE", f"{fire.fire_progress_pct:.1f}%")
    with r3:
        st.metric(
            "Lata do FIRE (majątek)",
            f"{fire.years_to_fire_number} lat" if fire.years_to_fire_number is not None else "> 40 lat",
        )

    r4, r5, r6 = st.columns(3)
    with r4:
        st.metric(
            "Dochód z dywidend (rok)",
            format_currency(fire.current_annual_dividends, currency),
            help=f"Forward yield portfela: {yield_pct:.2f}%.",
        )
    with r5:
        st.metric("Pokrycie wydatków dywidendami", f"{fire.coverage_pct:.1f}%")
    with r6:
        st.metric(
            "Lata do pokrycia dywidendami",
            f"{fire.years_to_dividend_cover} lat" if fire.years_to_dividend_cover is not None else "> 40 lat",
        )

    if yield_pct <= 0:
        st.info(
            "Portfel nie generuje dywidend (lub Yahoo nie podaje stopy) — projekcja "
            "„snowball” będzie zerowa. Liczba FIRE i postęp majątkowy pozostają aktualne."
        )
    else:
        st.plotly_chart(build_snowball_chart(fire.snowball, currency), use_container_width=True)

    st.caption(
        "⚠️ Uproszczony model edukacyjny: zakłada stały zwrot, stały forward yield rosnący "
        "o wzrost dywidend i brak podatków przy wypłacie. Nie jest poradą finansową."
    )
