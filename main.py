"""
XTB Portfolio Tracker – strona główna.
Uruchomienie: streamlit run main.py
"""

import streamlit as st

from core.session import get_report, init_session_state
from ui.sidebar import render_import_sidebar

st.set_page_config(
    page_title="XTB Portfolio Tracker",
    page_icon="📈",
    layout="wide",
)

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

        - **Portfolio** – otwarte pozycje, wykresy, metryki PnL
        - **Pozycja** – wykres 1Y/3Y/5Y, fundamenty, benchmark, timing wejścia
        - **Historia** – timeline, trade analytics, cost basis, zamknięte pozycje
        - **Analiza** – MA, RSI, MACD, Bollinger Bands (pandas_ta)
        - **Watchlist** – tickery spoza portfela, zwroty i porównanie z portfelem
        - **Alokacja** – podział sektorowy i geograficzny (USA / EU / PL)
        - **Eksport** – PDF i Excel (.xlsx) ze strony Portfolio
        - **Alerty** – pozycje powyżej progu ±X% ROI (w aplikacji, bez powiadomień systemowych)

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
st.markdown(
    f"""
    | | |
    |---|---|
    | Tryb | **{"Multi-account" if report.is_merged else "Jedno konto"}** |
    | Waluta konta | **{report.account_currency}** |
    | Otwarte pozycje | **{len(report.open_positions)}** |
    | Zamknięte pozycje | **{closed_n}** |

    Przejdź do **Portfolio**, **Pozycja**, **Historia**, **Analiza**, **Watchlist** lub **Alokacja** w menu po lewej.
    """
)
