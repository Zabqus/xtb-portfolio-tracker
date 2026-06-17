"""Wspólny panel boczny – import pliku i ustawienia waluty."""

from __future__ import annotations

import streamlit as st

from core.currencies import SUPPORTED_CURRENCIES
from core.multi_account import MULTI_ACCOUNT_CURRENCY
from core.session import (
    get_display_currency,
    get_report,
    init_session_state,
    process_uploads,
    set_display_currency,
)
from ui.theme import inject_global_css


def render_import_sidebar() -> bool:
    """
    Renderuje sidebar z uploadem i walutą wyświetlania.

    Zwraca True, gdy raport jest załadowany i gotowy do analizy.
    """
    inject_global_css()
    init_session_state()

    with st.sidebar:
        st.header("Import z XTB")
        multi = st.checkbox(
            "Multi-account (np. PLN + EUR)",
            key="multi_account_enabled",
            help="Wgraj dwa eksporty — jeden widok całego majątku.",
        )

        uploaded_1 = st.file_uploader(
            "Eksport — konto 1" if multi else "Wgraj eksport z XTB (Excel lub CSV)",
            type=["csv", "xlsx", "xls"],
            key="xtb_file_uploader_1",
        )
        uploaded_2 = None
        if multi:
            uploaded_2 = st.file_uploader(
                "Eksport — konto 2",
                type=["csv", "xlsx", "xls"],
                key="xtb_file_uploader_2",
            )

        st.caption(
            "Natywny Excel (Cash Operations + Closed Positions) "
            "lub uproszczony CSV."
        )

        if uploaded_1 is not None or uploaded_2 is not None:
            process_uploads(uploaded_1, uploaded_2)

        if st.session_state.parse_error:
            st.error(f"Błąd importu: {st.session_state.parse_error}")
            return False

        report = get_report()
        if report is None:
            return False

        st.divider()
        st.subheader("Konta" if report.is_merged else "Waluta")

        if report.is_merged and report.account_labels and report.source_filenames:
            st.success(f"Połączono **{len(report.account_labels)}** konta")
            for label in report.account_labels:
                fn = report.source_filenames.get(label, "—")
                st.caption(f"**{label}**: {fn}")
            if report.account_number:
                st.caption(f"Numery: {report.account_number}")
        else:
            if report.account_number:
                st.caption(f"Konto: {report.account_number}")
            st.info(f"Wykryta waluta konta: **{report.account_currency}**")
            st.caption(f"Plik: {report.filename}")

        if report.account_currency == MULTI_ACCOUNT_CURRENCY:
            default_ccy = get_display_currency()
        else:
            default_ccy = report.account_currency

        idx = (
            SUPPORTED_CURRENCIES.index(default_ccy)
            if default_ccy in SUPPORTED_CURRENCIES
            else 0
        )
        selected = st.selectbox(
            "Przelicz cały majątek na walutę",
            SUPPORTED_CURRENCIES,
            index=idx,
            key="display_currency_select",
        )
        if selected != get_display_currency():
            set_display_currency(selected)

        if report.closed_positions is not None:
            n = len(report.closed_positions)
            st.caption(f"Zamknięte pozycje (łącznie): {n}")

    return True
