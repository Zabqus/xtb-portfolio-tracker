"""
Podstrona: otwarte pozycje i analiza bieżącego portfela.
"""

import streamlit as st

from core.analyzer import portfolio_summary, portfolio_summary_by_account
from core.excel_export import ExcelExportError, default_excel_filename, generate_excel_bytes
from core.pdf_report import PdfReportError, default_report_filename, generate_monthly_pdf_bytes
from core.market_data import get_fetch_age_seconds
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_report,
    set_selected_ticker,
)
from ui.charts import build_allocation_pie, build_pnl_bar_chart, build_portfolio_treemap
from ui.formatters import format_currency, pnl_delta_color
from ui.sidebar import render_import_sidebar
from ui.tables import render_open_positions_table

st.title("📊 Portfolio – otwarte pozycje")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym (strona główna lub tutaj).")
    st.stop()

report = get_report()
if report is None:
    st.stop()

with st.spinner("Pobieranie cen i kursów walut…"):
    analyzed = get_analyzed_open()

if analyzed is None:
    st.error("Nie udało się przeanalizować portfela.")
    st.stop()

age = get_fetch_age_seconds()
if age is not None:
    mins = int(age // 60)
    if mins < 2:
        st.caption("🟢 Ceny aktualne (pobrane przed chwilą)")
    elif mins < 60:
        st.caption(f"🟡 Ceny z {mins} min temu — odśwież stronę, aby pobrać nowe")
    else:
        st.caption("🔴 Ceny sprzed ponad godziny — odśwież stronę")
else:
    st.caption("⚪ Ceny będą pobrane przy pierwszym załadowaniu")

summary = portfolio_summary(analyzed)
currency = str(summary["display_currency"])

fx_rates = analyzed.attrs.get("fx_rates", {})
if len(fx_rates) > 1:
    with st.expander("Kursy użyte do przeliczenia"):
        rates_txt = ", ".join(
            f"1 {c} = {fx_rates[c]:.4f} {currency}"
            for c in sorted(fx_rates)
            if c != currency
        )
        st.caption(rates_txt or "—")

st.subheader("Podsumowanie portfela")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Całkowita wartość", format_currency(summary["total_value"], currency))
with col2:
    st.metric("Łączny koszt", format_currency(summary["total_cost"], currency))
with col3:
    pnl = summary["total_pnl"]
    st.metric(
        "Łączny zysk / strata",
        format_currency(pnl, currency),
        delta=f"{summary['total_roi_pct']:.2f}% ROI",
        delta_color=pnl_delta_color(pnl),
    )
with col4:
    if summary.get("is_merged"):
        st.metric("Konta", ", ".join(summary.get("account_labels", ())))
    else:
        st.metric("Waluta konta", summary["account_currency"])

by_account = portfolio_summary_by_account(analyzed)
if by_account is not None and not by_account.empty:
    st.markdown("**Podział na konta** (w walucie wyświetlania)")
    show_acc = by_account.copy()
    show_acc["Wartość"] = show_acc["market_value"].map(lambda v: format_currency(v, currency))
    show_acc["PnL"] = show_acc["pnl"].map(lambda v: format_currency(v, currency))
    show_acc["ROI %"] = show_acc["roi_pct"].map(lambda v: f"{v:.2f}%")
    st.dataframe(
        show_acc[["account_label", "positions", "Wartość", "PnL", "ROI %"]].rename(
            columns={
                "account_label": "Konto",
                "positions": "Pozycje",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

missing = analyzed["market_price"].isna().sum()
if missing > 0:
    tickers = analyzed.loc[analyzed["market_price"].isna(), "ticker_yahoo"].tolist()
    st.warning(f"Brak ceny Yahoo dla: {', '.join(tickers)}. Sprawdź core/importer_maps.py.")

st.subheader("Wizualizacje")
chart_view = st.radio(
    "Widok portfela",
    ["Pie + Bar", "Mapa (Treemap)"],
    horizontal=True,
    key="portfolio_chart_view",
)

if chart_view == "Mapa (Treemap)":
    st.plotly_chart(build_portfolio_treemap(analyzed, currency), use_container_width=True)
    st.caption(
        "Rozmiar kafla = wartość rynkowa pozycji. "
        "Kolor: zielony = zysk, czerwony = strata (skala ROI%)."
    )
else:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(build_allocation_pie(analyzed, currency), use_container_width=True)
    with c2:
        st.plotly_chart(build_pnl_bar_chart(analyzed, currency), use_container_width=True)

if st.button("Sektor i region (USA / EU / PL) →", key="portfolio_to_allocation"):
    st.switch_page("pages/6_Alokacja.py")

st.subheader("Eksport")
st.caption(
    "PDF: podsumowanie i wykresy (kaleido). Excel: arkusze Portfolio, Historia, Analiza (openpyxl)."
)


@st.cache_data(show_spinner="Generowanie raportu PDF…")
def _cached_monthly_pdf(analysis_signature: str) -> bytes:
    report = get_report()
    analyzed = get_analyzed_open()
    if report is None or analyzed is None:
        raise PdfReportError("Brak danych portfela.")
    return generate_monthly_pdf_bytes(report, analyzed)


export_sig = st.session_state.get("analysis_signature")
if export_sig:

    @st.cache_data(show_spinner="Generowanie pliku Excel…")
    def _cached_excel_export(analysis_signature: str) -> bytes:
        report = get_report()
        analyzed = get_analyzed_open()
        if report is None or analyzed is None:
            raise ExcelExportError("Brak danych portfela.")
        return generate_excel_bytes(report, analyzed)

    col_pdf, col_xlsx = st.columns(2)
    with col_pdf:
        try:
            pdf_bytes = _cached_monthly_pdf(export_sig)
            st.download_button(
                "Raport miesięczny (PDF)",
                data=pdf_bytes,
                file_name=default_report_filename(),
                mime="application/pdf",
                use_container_width=True,
                key="portfolio_pdf_download",
            )
        except PdfReportError as exc:
            st.error(str(exc))
    with col_xlsx:
        try:
            xlsx_bytes = _cached_excel_export(export_sig)
            st.download_button(
                "Eksport Excel (.xlsx)",
                data=xlsx_bytes,
                file_name=default_excel_filename(),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="portfolio_xlsx_download",
            )
        except ExcelExportError as exc:
            st.error(str(exc))

st.subheader("Otwarte pozycje")

# Filtry
f1, f2, f3 = st.columns(3)
with f1:
    show_filter = st.radio(
        "Pokaż",
        ["Wszystkie", "Tylko zyski", "Tylko straty"],
        horizontal=True,
        key="positions_filter_pnl",
    )
with f2:
    if "account_label" in analyzed.columns and analyzed["account_label"].nunique() > 1:
        accounts = ["Wszystkie"] + sorted(analyzed["account_label"].dropna().unique().tolist())
        acc_filter = st.selectbox("Konto", accounts, key="positions_filter_account")
    else:
        acc_filter = "Wszystkie"
with f3:
    sort_by = st.selectbox(
        "Sortuj po",
        ["ROI % (malejąco)", "ROI % (rosnąco)", "Wartość (malejąco)", "PnL (malejąco)"],
        key="positions_sort",
    )

# Zastosuj filtry
filtered = analyzed.copy()
if show_filter == "Tylko zyski":
    filtered = filtered[filtered["roi_pct"] > 0]
elif show_filter == "Tylko straty":
    filtered = filtered[filtered["roi_pct"] < 0]
if acc_filter != "Wszystkie":
    filtered = filtered[filtered["account_label"] == acc_filter]

sort_map = {
    "ROI % (malejąco)": ("roi_pct", False),
    "ROI % (rosnąco)": ("roi_pct", True),
    "Wartość (malejąco)": ("market_value", False),
    "PnL (malejąco)": ("pnl", False),
}
sort_col, asc = sort_map[sort_by]
if sort_col in filtered.columns:
    filtered = filtered.sort_values(sort_col, ascending=asc)

if filtered.empty:
    st.info("Brak pozycji spełniających wybrane filtry.")
else:
    render_open_positions_table(filtered, currency)

st.divider()
st.subheader("Analiza pojedynczej pozycji")
tickers = analyzed["ticker_xtb"].tolist()
pick = st.selectbox(
    "Wybierz ticker do szczegółowej analizy",
    tickers,
    key="portfolio_pick_ticker",
)
col_a, col_b = st.columns(2)
with col_a:
    if st.button("Analiza pozycji →", type="primary"):
        set_selected_ticker(pick)
        st.switch_page("pages/2_Pozycja.py")
with col_b:
    if st.button("Analiza techniczna →"):
        set_selected_ticker(pick)
        st.switch_page("pages/4_Analiza.py")
