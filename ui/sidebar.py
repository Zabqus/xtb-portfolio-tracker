"""Wspólny panel boczny – import pliku i ustawienia waluty."""

from __future__ import annotations

import streamlit as st

from core.currencies import SUPPORTED_CURRENCIES
from core.session import (
    get_display_currency,
    get_report,
    init_session_state,
    process_upload,
    set_display_currency,
)


def render_import_sidebar() -> bool:
    """
    Renderuje sidebar z uploadem i walutą wyświetlania.

    Zwraca True, gdy raport jest załadowany i gotowy do analizy.
    """
    init_session_state()

    with st.sidebar:
        st.header("Import z XTB")
        uploaded = st.file_uploader(
            "Wgraj eksport z XTB (Excel lub CSV)",
            type=["csv", "xlsx", "xls"],
            key="xtb_file_uploader",
        )
        st.caption(
            "Natywny Excel (Cash Operations + Closed Positions) "
            "lub uproszczony CSV."
        )

        if uploaded is not None:
            process_upload(uploaded)

        if st.session_state.parse_error:
            st.error(f"Błąd importu: {st.session_state.parse_error}")
            return False

        report = get_report()
        if report is None:
            return False

        st.divider()
        st.subheader("Waluta")
        if report.account_number:
            st.caption(f"Konto: {report.account_number}")
        st.info(f"Wykryta waluta konta: **{report.account_currency}**")

        idx = (
            SUPPORTED_CURRENCIES.index(report.account_currency)
            if report.account_currency in SUPPORTED_CURRENCIES
            else 0
        )
        selected = st.selectbox(
            "Przelicz sumy na walutę",
            SUPPORTED_CURRENCIES,
            index=idx,
            key="display_currency_select",
        )
        if selected != get_display_currency():
            set_display_currency(selected)

        st.caption(f"Plik: {report.filename}")
        if report.closed_positions is not None:
            n = len(report.closed_positions)
            st.caption(f"Zamknięte pozycje w pliku: {n}")

    return True
