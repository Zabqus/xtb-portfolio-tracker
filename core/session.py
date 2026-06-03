"""
Streamlit session state – cache raportu między podstronami.
"""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from core.analyzer import analyze_portfolio
from core.importer import XTBReport, parse_xtb_report

SESSION_DEFAULTS = {
    "file_signature": None,
    "report": None,
    "display_currency": None,
    "analyzed_open": None,
    "analysis_signature": None,
    "parse_error": None,
}


def init_session_state() -> None:
    """Inicjalizuje domyślne klucze session_state."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _file_signature(uploaded_file) -> str:
    """Unikalny hash wgrywanego pliku (nazwa + rozmiar + suma bajtów)."""
    data = uploaded_file.getvalue()
    digest = hashlib.md5(data).hexdigest()
    return f"{uploaded_file.name}:{len(data)}:{digest}"


def process_upload(uploaded_file) -> bool:
    """
    Parsuje plik tylko gdy zmienił się upload (inaczej używa cache).

    Zwraca True, gdy raport jest dostępny; False przy błędzie lub braku pliku.
    """
    init_session_state()

    if uploaded_file is None:
        st.session_state.file_signature = None
        st.session_state.report = None
        st.session_state.analyzed_open = None
        st.session_state.analysis_signature = None
        st.session_state.parse_error = None
        return False

    signature = _file_signature(uploaded_file)
    if signature == st.session_state.file_signature and st.session_state.report is not None:
        return st.session_state.parse_error is None

    st.session_state.file_signature = signature
    st.session_state.analyzed_open = None
    st.session_state.analysis_signature = None

    try:
        uploaded_file.seek(0)
        report = parse_xtb_report(uploaded_file, uploaded_file.name)
        st.session_state.report = report
        st.session_state.parse_error = None
        if st.session_state.display_currency is None:
            st.session_state.display_currency = report.account_currency
        return True
    except (ValueError, pd.errors.ParserError) as exc:
        st.session_state.report = None
        st.session_state.parse_error = str(exc)
        return False


def get_report() -> XTBReport | None:
    return st.session_state.get("report")


def get_display_currency() -> str:
    report = get_report()
    default = report.account_currency if report else "PLN"
    return st.session_state.get("display_currency") or default


def set_display_currency(currency: str) -> None:
    st.session_state.display_currency = currency
    st.session_state.analyzed_open = None
    st.session_state.analysis_signature = None


def get_analyzed_open() -> pd.DataFrame | None:
    """
    Zwraca przeanalizowany portfel otwarty (cache w session_state).
    Przelicza tylko gdy zmieniła się waluta wyświetlania lub raport.
    """
    report = get_report()
    if report is None:
        return None

    display_currency = get_display_currency()
    signature = f"{st.session_state.file_signature}:{display_currency}"

    if (
        st.session_state.analyzed_open is not None
        and st.session_state.analysis_signature == signature
    ):
        return st.session_state.analyzed_open

    analyzed = analyze_portfolio(report.open_positions, display_currency=display_currency)
    st.session_state.analyzed_open = analyzed
    st.session_state.analysis_signature = signature
    return analyzed
