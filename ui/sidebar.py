"""Wspólny panel boczny – import pliku i ustawienia waluty."""

from __future__ import annotations

import streamlit as st

from core.currencies import SUPPORTED_CURRENCIES
from core.importer_maps import (
    delete_ticker_override,
    load_ticker_overrides,
    map_ticker_to_yahoo,
    positions_missing_prices,
    set_ticker_override,
)
from core.multi_account import MULTI_ACCOUNT_CURRENCY
from core.prefs_backup import (
    default_backup_filename,
    export_prefs_zip,
    import_prefs_zip,
    list_existing_pref_files,
)
from core.session import (
    get_display_currency,
    get_report,
    init_session_state,
    process_uploads,
    remap_tickers_after_override,
    set_display_currency,
)
from ui.theme import render_theme_selector


def _render_prefs_backup_panel() -> None:
    existing = list_existing_pref_files()
    with st.expander("Backup preferencji", expanded=False):
        st.caption(
            "Lokalny ZIP: watchlist, alerty, tagi, snapshoty, mapowania, "
            "straty podatkowe, IKE/IKZE, motyw."
        )
        if existing:
            st.caption("Pliki: " + ", ".join(p.name for p in existing))
        else:
            st.caption("Brak lokalnych plików preferencji do spakowania.")

        if existing:
            st.download_button(
                "Pobierz backup ZIP",
                data=export_prefs_zip(),
                file_name=default_backup_filename(),
                mime="application/zip",
                key="prefs_backup_download",
                use_container_width=True,
            )

        uploaded = st.file_uploader(
            "Przywróć z ZIP",
            type=["zip"],
            key="prefs_backup_upload",
        )
        if uploaded is not None:
            if st.button("Przywróć (nadpisz)", key="prefs_backup_restore", use_container_width=True):
                restored = import_prefs_zip(uploaded.getvalue(), overwrite=True)
                if restored:
                    st.success("Przywrócono: " + ", ".join(restored))
                    st.rerun()
                else:
                    st.warning("W ZIP nie znaleziono znanych plików preferencji.")


def _render_ticker_mapping_panel() -> None:
    """Lista braków Yahoo + szybkie dodanie mapowania (bez wymuszania fetch cen)."""
    analyzed = st.session_state.get("analyzed_open")
    missing = positions_missing_prices(analyzed)
    overrides = load_ticker_overrides()

    with st.expander(
        f"Mapowanie tickerów ({len(missing)} bez ceny)" if missing else "Mapowanie tickerów",
        expanded=bool(missing),
    ):
        if missing:
            st.warning(
                "Brak ceny Yahoo dla poniższych symboli — dodaj mapowanie "
                "(np. `VWCE` → `VWCE.DE`)."
            )
            for row in missing[:12]:
                st.caption(f"• **{row['ticker_xtb']}** → `{row['ticker_yahoo']}`")
            if len(missing) > 12:
                st.caption(f"…i {len(missing) - 12} kolejnych")
        else:
            st.caption("Wszystkie otwarte pozycje mają cenę (lub brak portfela).")

        xtb_default = missing[0]["ticker_xtb"] if missing else ""
        with st.form("ticker_override_form", clear_on_submit=True):
            xtb_in = st.text_input("Symbol XTB", value=xtb_default, placeholder="VWCE")
            yahoo_guess = map_ticker_to_yahoo(xtb_in) if xtb_in.strip() else ""
            yahoo_in = st.text_input(
                "Symbol Yahoo",
                value=yahoo_guess,
                placeholder="VWCE.DE",
            )
            submitted = st.form_submit_button("Zapisz mapowanie")
            if submitted:
                if not xtb_in.strip() or not yahoo_in.strip():
                    st.error("Podaj oba symbole.")
                else:
                    set_ticker_override(xtb_in, yahoo_in)
                    remap_tickers_after_override()
                    st.success(f"Zapisano: {xtb_in.strip().upper()} → {yahoo_in.strip()}")
                    st.rerun()

        if overrides:
            st.caption("Twoje nadpisania (`ticker_overrides.json`):")
            for k, v in sorted(overrides.items()):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.text(f"{k} → {v}")
                with c2:
                    if st.button("Usuń", key=f"del_override_{k}"):
                        delete_ticker_override(k)
                        remap_tickers_after_override()
                        st.rerun()


def render_import_sidebar() -> bool:
    """
    Renderuje sidebar z uploadem i walutą wyświetlania.

    Zwraca True, gdy raport jest załadowany i gotowy do analizy.
    """
    init_session_state()

    with st.sidebar:
        render_theme_selector()
        st.divider()
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

        st.divider()
        _render_ticker_mapping_panel()
        _render_prefs_backup_panel()

    return True
