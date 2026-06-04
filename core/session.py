"""
Streamlit session state – cache raportu między podstronami.
"""

from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from core.analyzer import analyze_portfolio
from core.importer import XTBReport, parse_xtb_report
from core.cost_basis import build_cost_basis_history
from core.timeline import build_portfolio_timeline
from core.trade_analytics import TradeAnalyticsSummary, compute_trade_analytics
from core.transactions import parse_cash_operations_trades
from core.watchlist import (
    WatchlistEntry,
    is_in_portfolio,
    load_watchlist_file,
    save_watchlist_file,
)

SESSION_DEFAULTS = {
    "file_signature": None,
    "report": None,
    "display_currency": None,
    "analyzed_open": None,
    "analysis_signature": None,
    "parse_error": None,
    "selected_ticker_xtb": None,
    "portfolio_timeline": None,
    "timeline_signature": None,
    "cost_basis_history": None,
    "trade_analytics_summary": None,
    "round_trips": None,
    "analytics_signature": None,
    "watchlist": None,
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
    st.session_state.portfolio_timeline = None
    st.session_state.timeline_signature = None
    st.session_state.cost_basis_history = None
    st.session_state.trade_analytics_summary = None
    st.session_state.round_trips = None
    st.session_state.analytics_signature = None

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


def get_selected_ticker() -> str | None:
    return st.session_state.get("selected_ticker_xtb")


def set_selected_ticker(ticker_xtb: str) -> None:
    st.session_state.selected_ticker_xtb = ticker_xtb


def get_position_row(ticker_xtb: str) -> pd.Series | None:
    """Zwraca wiersz otwartej pozycji dla podanego tickera XTB."""
    analyzed = get_analyzed_open()
    if analyzed is None:
        return None
    mask = analyzed["ticker_xtb"] == ticker_xtb
    if not mask.any():
        return None
    return analyzed.loc[mask].iloc[0]


def get_portfolio_timeline() -> pd.DataFrame | None:
    """Cache timeline portfela (wymaga natywnego Cash Operations w raporcie)."""
    report = get_report()
    if report is None or report.cash_operations is None:
        return None

    signature = st.session_state.file_signature
    if (
        st.session_state.portfolio_timeline is not None
        and st.session_state.timeline_signature == signature
    ):
        return st.session_state.portfolio_timeline

    timeline = build_portfolio_timeline(report.cash_operations)
    st.session_state.portfolio_timeline = timeline
    st.session_state.timeline_signature = signature
    return timeline


def _load_analytics_bundle() -> None:
    """Ładuje cost basis + trade analytics jednym przebiegiem (cache w session)."""
    report = get_report()
    if report is None or report.cash_operations is None:
        return

    signature = st.session_state.file_signature
    if st.session_state.analytics_signature == signature:
        return

    trades = parse_cash_operations_trades(report.cash_operations)
    st.session_state.cost_basis_history = build_cost_basis_history(trades)
    summary, round_trips = compute_trade_analytics(trades, report.closed_positions)
    st.session_state.trade_analytics_summary = summary
    st.session_state.round_trips = round_trips
    st.session_state.analytics_signature = signature


def get_trade_analytics() -> tuple[TradeAnalyticsSummary | None, pd.DataFrame | None]:
    """Cache statystyk tradingowych i round-tripów FIFO."""
    _load_analytics_bundle()
    return (
        st.session_state.trade_analytics_summary,
        st.session_state.round_trips,
    )


def get_cost_basis_history() -> pd.DataFrame | None:
    """Cache historii średniej ceny zakupu."""
    _load_analytics_bundle()
    return st.session_state.cost_basis_history


def _sync_watchlist_from_disk() -> list[WatchlistEntry]:
    if st.session_state.watchlist is None:
        st.session_state.watchlist = load_watchlist_file()
    return st.session_state.watchlist


def get_watchlist() -> list[WatchlistEntry]:
    """Lista symboli watchlisty (cache + plik watchlist.json)."""
    init_session_state()
    return list(_sync_watchlist_from_disk())


def add_watchlist_symbol(raw: str) -> tuple[bool, str]:
    """
    Dodaje symbol do watchlisty.

    Zwraca (sukces, komunikat).
    """
    init_session_state()
    try:
        entry = WatchlistEntry.from_symbol(raw)
    except ValueError as exc:
        return False, str(exc)

    report = get_report()
    open_df = report.open_positions if report else None

    if is_in_portfolio(entry, open_df):
        return False, f"{entry.symbol} jest już w otwartym portfelu — watchlista służy do symboli spoza portfela."

    entries = _sync_watchlist_from_disk()
    if any(e.yahoo.upper() == entry.yahoo.upper() for e in entries):
        return False, f"{entry.yahoo} jest już na watchliście."

    entries.append(entry)
    st.session_state.watchlist = entries
    save_watchlist_file(entries)
    return True, f"Dodano **{entry.symbol}** → Yahoo: `{entry.yahoo}`"


def remove_watchlist_symbol(symbol: str) -> None:
    """Usuwa wpis po symbolu wejściowym lub Yahoo."""
    key = str(symbol).strip().upper()
    entries = [e for e in _sync_watchlist_from_disk() if e.symbol.upper() != key and e.yahoo.upper() != key]
    st.session_state.watchlist = entries
    save_watchlist_file(entries)
