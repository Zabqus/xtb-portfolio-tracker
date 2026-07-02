"""
XTB Portfolio Tracker – strona główna.
Uruchomienie: streamlit run main.py
"""

import streamlit as st

from core.session import get_analyzed_open, get_display_currency, get_portfolio_timeline, get_report, init_session_state
from ui.kpi_dashboard import render_kpi_wall
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page

st.set_page_config(
    page_title="XTB Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

bootstrap_page()
init_session_state()

st.title("📈 XTB Portfolio Tracker")
st.caption("Lokalny dashboard do analizy portfela akcji i ETF-ów z XTB")

render_import_sidebar()

report = get_report()

if report is None:
    st.info("Wgraj plik raportu XTB w panelu bocznym, aby rozpocząć analizę.")
    st.markdown(
        """
        ### Podstrony

        - **Strona główna** – dashboard KPI (TWR, MWR, Sharpe, alerty) ze sparkline'ami
        - **Portfolio** – otwarte pozycje, wykresy, metryki PnL
        - **Pozycja** – wykres 1Y/3Y/5Y, fundamenty, benchmark, timing wejścia
        - **Historia** – timeline, trade analytics, cost basis, zamknięte pozycje
        - **Analiza** – MA, RSI, MACD, Bollinger Bands (pandas_ta)
        - **Watchlist** – tickery spoza portfela, zwroty i porównanie z portfelem
        - **Alokacja** – podział sektorowy i geograficzny (USA / EU / PL)
        - **Eksport** – PDF i Excel (.xlsx) ze strony Portfolio
        - **Alerty** – pozycje powyżej progu ±X% ROI (w aplikacji, bez powiadomień systemowych)
        - **Konsensusy i sygnały** – cele analityków oraz sygnały kup / trzymaj / sprzedaj
        - **Zwroty** – prawdziwa stopa zwrotu (MWR/XIRR + TWR), portfel vs benchmark, snapshoty
        - **Słownik** – krótkie wyjaśnienia wszystkich pojęć używanych w aplikacji

        ### Wskazówki

        1. Pobierz raport Excel z platformy XTB (*Cash Operations* + *Closed Positions*).
        2. Wgraj plik w sidebarze – dane są cache'owane między podstronami.
        3. Opcjonalnie **Multi-account**: dwa eksporty (np. PLN + EUR) → jeden widok majątku.
        4. Wybierz walutę wyświetlania (PLN / EUR / USD / GBP).
        """
    )
    st.stop()

if report.is_merged and report.account_labels:
    st.success(f"Połączono konta: **{', '.join(report.account_labels)}**")
    for label in report.account_labels:
        fn = (report.source_filenames or {}).get(label, "—")
        st.caption(f"{label}: {fn}")
else:
    st.success(f"Załadowano: **{report.filename}**")

closed_n = len(report.closed_positions) if report.closed_positions is not None else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("Tryb", "Multi-account" if report.is_merged else "Jedno konto")
m2.metric("Waluta konta", report.account_currency)
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
        title="📊 Dashboard analityczny",
    )
else:
    st.caption("Dashboard KPI pojawi się po poprawnej analizie otwartych pozycji.")

st.divider()
st.caption(
    "Przejdź do **Portfolio**, **Pozycja**, **Historia**, **Analiza**, **Watchlist**, "
    "**Alokacja**, **Zwroty** lub **Słownik** w menu po lewej."
)
