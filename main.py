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
        - **Closed Positions** – historia zamkniętych transakcji z eksportu XTB

        ### Wskazówki

        1. Pobierz raport Excel z platformy XTB (*Cash Operations* + *Closed Positions*).
        2. Wgraj plik w sidebarze – dane są cache'owane między podstronami.
        3. Wybierz walutę wyświetlania (PLN / EUR / USD / GBP).
        """
    )
    st.stop()

st.success(f"Załadowano: **{report.filename}**")
st.markdown(
    f"""
    | | |
    |---|---|
    | Waluta konta | **{report.account_currency}** |
    | Otwarte pozycje | **{len(report.open_positions)}** |
    | Zamknięte pozycje | **{len(report.closed_positions) if report.closed_positions is not None else 0}** |

    Przejdź do podstrony **Portfolio** lub **Closed Positions** w menu po lewej.
    """
)
