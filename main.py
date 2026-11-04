"""
XTB Portfolio Tracker – strona główna.
Uruchomienie: streamlit run main.py
"""

import streamlit as st

from core.session import get_analyzed_open, get_display_currency, get_portfolio_timeline, get_report, init_session_state
from ui.kpi_dashboard import render_kpi_wall
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page, section_header

st.set_page_config(
    page_title="XTB Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

bootstrap_page()
init_session_state()

st.title("XTB Portfolio Tracker")
st.caption("Lokalny dashboard do analizy portfela akcji i ETF-ów z XTB")

render_import_sidebar()

report = get_report()

if report is None:
    st.info("Wgraj raport XTB w panelu bocznym, aby rozpocząć analizę.")

    section_header("Jak zacząć", "Trzy kroki do pierwszego podglądu portfela")
    step1, step2, step3 = st.columns(3)
    with step1:
        st.markdown("**1. Eksport z XTB**")
        st.caption("Pobierz Excel z *Cash Operations* i *Closed Positions*.")
    with step2:
        st.markdown("**2. Import**")
        st.caption("Wgraj plik w sidebarze — dane są cache'owane między stronami.")
    with step3:
        st.markdown("**3. Analiza**")
        st.caption("KPI, pozycje, historia, alokacja, zwroty i cele — w menu po lewej.")

    st.divider()

    with st.expander("Co znajdziesz w aplikacji", expanded=False):
        left, right = st.columns(2)
        with left:
            st.markdown(
                """
                - **Strona główna** — dashboard KPI (TWR, MWR, Sharpe)
                - **Portfolio** — otwarte pozycje, PnL, ryzyko, eksport
                - **Pozycja** — wykres, fundamenty, timing wejścia
                - **Historia** — timeline, Belka, kalendarz
                - **Analiza** — MA, RSI, MACD, Bollinger
                - **Watchlist** — tickery spoza portfela
                """
            )
        with right:
            st.markdown(
                """
                - **Alokacja** — sektor / region / FX + rebalancing
                - **Alerty** — progi ROI i alerty cenowe
                - **Konsensusy** — ratingi analityków i sygnały
                - **Zwroty** — MWR/TWR, benchmarki, snapshoty
                - **Cele** — cel wartości, FIRE, dywidendy
                - **Słownik** — wyjaśnienia pojęć (bez importu)
                """
            )

    st.caption(
        "Opcjonalnie: włącz **Multi-account** w sidebarze, aby połączyć dwa eksporty "
        "(np. PLN + EUR) w jeden widok majątku."
    )
    st.stop()

# --- Załadowany raport ---
if report.is_merged and report.account_labels:
    labels = ", ".join(report.account_labels)
    st.caption(f"Połączono konta · **{labels}**")
    for label in report.account_labels:
        fn = (report.source_filenames or {}).get(label, "—")
        st.caption(f"{label}: {fn}")
else:
    st.caption(f"Załadowano · **{report.filename}**")

closed_n = len(report.closed_positions) if report.closed_positions is not None else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Tryb", "Multi-account" if report.is_merged else "Jedno konto")
m2.metric(
    "Waluta konta",
    ", ".join(report.account_labels) if report.is_merged and report.account_labels else report.account_currency,
)
m3.metric("Otwarte pozycje", len(report.open_positions))
m4.metric("Zamknięte pozycje", closed_n)

st.divider()

with st.spinner("Ładowanie metryk analitycznych…"):
    analyzed = get_analyzed_open()
    timeline = get_portfolio_timeline()
    currency = get_display_currency()

if analyzed is not None and not analyzed.empty:
    render_kpi_wall(
        report,
        analyzed,
        timeline,
        currency,
        title="Dashboard analityczny",
    )
else:
    st.caption("Dashboard KPI pojawi się po poprawnej analizie otwartych pozycji.")
