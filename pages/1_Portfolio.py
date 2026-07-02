"""
Podstrona: otwarte pozycje i analiza bieżącego portfela.
"""

import streamlit as st

from core.analyzer import portfolio_summary, portfolio_summary_by_account
from core.excel_export import ExcelExportError, default_excel_filename, generate_excel_bytes
from core.pdf_report import PdfReportError, default_report_filename, generate_monthly_pdf_bytes
from core.market_data import get_fetch_age_seconds
from core.allocation import enrich_portfolio_allocation
from core.concentration import (
    compute_concentration_metrics,
    concentration_history_from_snapshots,
)
from core.pnl_breakdown import compute_pnl_breakdown
from core.position_risk import build_position_risk_data
from core.risk_metrics import (
    DEFAULT_RISK_FREE,
    build_correlation_matrix,
    compute_risk_metrics,
    compute_rolling_risk,
    high_correlation_pairs,
)
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_portfolio_timeline,
    get_report,
    set_selected_ticker,
)
from ui.chart_navigation import render_navigable_chart
from ui.charts import build_allocation_pie, build_pnl_bar_chart, build_portfolio_treemap
from ui.formatters import format_currency, pnl_delta_color
from ui.portfolio_filters import apply_portfolio_filters, render_portfolio_filters
from ui.pnl_charts import build_pnl_waterfall_chart
from ui.risk_charts import (
    build_concentration_chart,
    build_correlation_heatmap,
    build_position_risk_bubble,
    build_rolling_risk_chart,
)
from ui.sidebar import render_import_sidebar
from ui.tables import render_open_positions_table
from ui.theme import bootstrap_page

bootstrap_page()
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

st.subheader("Filtry globalne")
st.caption("Filtry dotyczą wykresów i tabeli poniżej — istniejące sekcje analityczne pozostają bez zmian.")
portfolio_filters = render_portfolio_filters(analyzed, key_prefix="portfolio")
filtered = apply_portfolio_filters(analyzed, portfolio_filters)

if filtered.empty:
    st.warning("Brak pozycji spełniających wybrane filtry — zmień kryteria powyżej.")

st.subheader("Wizualizacje")
chart_view = st.radio(
    "Widok portfela",
    ["Pie + Bar", "Mapa (Treemap)"],
    horizontal=True,
    key="portfolio_chart_view",
)

chart_df = filtered if not filtered.empty else analyzed
label_col = "ticker_xtb" if "ticker_xtb" in chart_df.columns else "ticker_yahoo"
chart_tickers = chart_df[label_col].tolist() if label_col in chart_df.columns else None

if chart_view == "Mapa (Treemap)":
    render_navigable_chart(
        build_portfolio_treemap(chart_df, currency),
        "portfolio_treemap",
        tickers=chart_tickers,
    )
    st.caption(
        "Rozmiar kafla = wartość rynkowa pozycji. "
        "Kolor: zielony = zysk, czerwony = strata (skala ROI%). "
        "**Kliknij ticker**, aby przejść do analizy pozycji."
    )
else:
    c1, c2 = st.columns(2)
    with c1:
        render_navigable_chart(
            build_allocation_pie(chart_df, currency),
            "portfolio_pie",
            tickers=chart_tickers,
        )
    with c2:
        render_navigable_chart(
            build_pnl_bar_chart(chart_df, currency),
            "portfolio_pnl_bar",
            tickers=chart_tickers,
        )
    st.caption("**Kliknij ticker na wykresie**, aby przejść do strony Pozycja.")

st.subheader("Portfolio i ryzyko")
st.caption("Nowe wizualizacje analityczne — istniejące wykresy powyżej pozostają bez zmian.")

with st.expander("💧 Wodospad P&L", expanded=False):
    breakdown = compute_pnl_breakdown(
        analyzed,
        closed=report.closed_positions,
        cash_ops=report.cash_operations,
        account_currency=report.account_currency,
    )
    if not breakdown.has_data:
        st.info("Brak danych do wykresu wodospadowego.")
    else:
        st.plotly_chart(build_pnl_waterfall_chart(breakdown), use_container_width=True)
        w1, w2, w3, w4 = st.columns(4)
        with w1:
            st.metric("Niezrealizowany", format_currency(breakdown.unrealized_pnl, currency))
        with w2:
            st.metric("Zrealizowany", format_currency(breakdown.realized_pnl, currency))
        with w3:
            st.metric("Dywidendy", format_currency(breakdown.dividends, currency))
        with w4:
            st.metric(
                "Podatek (szac.)",
                format_currency(breakdown.estimated_tax, currency),
                help="Szacunek Belki 19% od dodatnich zysków kapitałowych i dywidend.",
            )
        st.caption(
            "Całkowity wynik = niezrealizowany + zrealizowany + dywidendy − podatek. "
            "Podatek to szacunek edukacyjny — patrz zakładka Historia → Podatek Belki."
        )

with st.expander("📊 Koncentracja (HHI / Top-N)", expanded=False):
    with st.spinner("Liczenie koncentracji…"):
        enriched = enrich_portfolio_allocation(analyzed)
        conc = compute_concentration_metrics(enriched)
        conc_history = concentration_history_from_snapshots(currency)

    if conc.position_count == 0:
        st.info("Brak pozycji do analizy koncentracji.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Top-5", f"{conc.top5_pct:.1f}%")
        with c2:
            st.metric("HHI", f"{conc.hhi * 100:.0f}", help="Herfindahl-Hirschman ×100 (im wyżej, tym bardziej skoncentrowany).")
        with c3:
            st.metric("Efektywne N", f"{conc.effective_n:.1f}")
        with c4:
            st.metric("Pozycje", conc.position_count)
        st.plotly_chart(
            build_concentration_chart(conc, conc_history if not conc_history.empty else None),
            use_container_width=True,
        )
        if conc_history.empty:
            st.caption(
                "Brak historii HHI — zapisuj snapshoty na stronie Zwroty, "
                "aby śledzić koncentrację w czasie."
            )
        else:
            st.caption("Dolny panel: HHI i Top-5% z zapisanych snapshotów portfela.")

with st.expander("🫧 Mapa ryzyka pozycji", expanded=False):
    with st.spinner("Pobieranie zmienności 90d i sektorów…"):
        risk_map = build_position_risk_data(analyzed)
    if risk_map.empty:
        st.info("Brak danych do mapy ryzyka pozycji.")
    else:
        st.plotly_chart(build_position_risk_bubble(risk_map, currency), use_container_width=True)
        st.caption(
            "Oś X = waga w portfelu, oś Y = ROI%, rozmiar bąbla = zmienność 90d, kolor = sektor. "
            "Duża pozycja w prawym górnym rogu z dużym bąblem = wysoka ekspozycja i ryzyko."
        )

with st.expander("📊 Metryki ryzyka portfela"):
    if report.cash_operations is None:
        st.info(
            "Metryki ryzyka wymagają natywnego eksportu Excel z arkuszem Cash Operations "
            "(potrzebny timeline portfela)."
        )
    else:
        default_rf = DEFAULT_RISK_FREE.get(currency, 0.045)
        risk_free_pct = st.slider(
            "Stopa wolna od ryzyka (roczna, %)",
            min_value=0.0,
            max_value=10.0,
            value=round(default_rf * 100, 2),
            step=0.25,
            key="risk_free_slider",
            help="Używana do Sharpe ratio. Domyślnie orientacyjna stopa dla waluty wyświetlania.",
        )

        with st.spinner("Liczenie metryk ryzyka…"):
            timeline = get_portfolio_timeline()
            metrics = compute_risk_metrics(timeline, risk_free=risk_free_pct / 100)

        if not metrics.has_data:
            st.warning("Za mało danych w timeline, aby policzyć metryki ryzyka.")
        else:
            r1, r2, r3, r4, r5 = st.columns(5)
            with r1:
                st.metric(
                    "Zmienność (roczna)",
                    f"{metrics.volatility_pct:.1f}%",
                    help="Odchylenie standardowe dziennych zwrotów × √252.",
                )
            with r2:
                st.metric(
                    "Max Drawdown",
                    f"{metrics.max_drawdown_pct:.1f}%",
                    delta_color="inverse",
                    help="Największy spadek od szczytu wartości portfela.",
                )
            with r3:
                st.metric(
                    "Sharpe Ratio",
                    f"{metrics.sharpe_ratio:.2f}" if metrics.sharpe_ratio is not None else "—",
                    help="(Zwrot roczny − stopa wolna od ryzyka) / zmienność.",
                )
            with r4:
                st.metric(
                    "Calmar Ratio",
                    f"{metrics.calmar_ratio:.2f}" if metrics.calmar_ratio is not None else "—",
                    help="Zwrot roczny / |max drawdown|.",
                )
            with r5:
                best = f"{metrics.best_day_pct:+.1f}%" if metrics.best_day_pct is not None else "—"
                worst = f"{metrics.worst_day_pct:+.1f}%" if metrics.worst_day_pct is not None else "—"
                st.metric("Najlepszy / najgorszy dzień", best, delta=worst)

            st.caption(
                f"Szacowany zwrot roczny (annualizowany): **{metrics.annual_return_pct:+.1f}%**. "
                "Metryki liczone na podstawie dziennej wyceny portfela z timeline."
            )

            rolling = compute_rolling_risk(timeline, risk_free=risk_free_pct / 100)
            if not rolling.empty:
                st.markdown("##### Rolling risk metrics (trend w czasie)")
                st.plotly_chart(build_rolling_risk_chart(rolling), use_container_width=True)
                st.caption(
                    "Zmienność, Sharpe i max drawdown w oknach 30 / 60 / 90 dni — "
                    "pokazują trend ryzyka, nie tylko jedną liczbę."
                )
            else:
                st.caption("Za mało danych timeline do rolling risk metrics (min. ~90 dni).")

with st.expander("🔗 Korelacja między pozycjami"):
    tickers_yahoo = tuple(sorted(analyzed["ticker_yahoo"].dropna().unique().tolist()))
    if len(tickers_yahoo) < 2:
        st.info("Korelacja wymaga co najmniej dwóch pozycji z danymi cenowymi.")
    else:
        corr_period = st.selectbox(
            "Okres do korelacji",
            ["1Y", "3Y", "5Y"],
            key="correlation_period",
        )
        with st.spinner("Pobieranie historii cen i liczenie korelacji…"):
            corr = build_correlation_matrix(tickers_yahoo, corr_period)

        if corr.empty:
            st.warning("Za mało wspólnych danych cenowych, aby policzyć korelację.")
        else:
            st.plotly_chart(build_correlation_heatmap(corr), use_container_width=True)
            pairs = high_correlation_pairs(corr, threshold=0.9)
            if pairs:
                st.warning("⚠️ Wysoka korelacja (≥ 0.9) — możliwe duplikowanie ekspozycji:")
                for a, b, value in pairs:
                    st.caption(f"• **{a}** ↔ **{b}**: korelacja {value:.2f}")
            else:
                st.caption("Brak par o korelacji ≥ 0.9 — dywersyfikacja wygląda zdrowo.")

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

sort_by = st.selectbox(
    "Sortuj tabelę po",
    ["ROI % (malejąco)", "ROI % (rosnąco)", "Wartość (malejąco)", "PnL (malejąco)"],
    key="positions_sort",
)

table_df = filtered.copy() if not filtered.empty else analyzed.copy()
sort_map = {
    "ROI % (malejąco)": ("roi_pct", False),
    "ROI % (rosnąco)": ("roi_pct", True),
    "Wartość (malejąco)": ("market_value", False),
    "PnL (malejąco)": ("pnl", False),
}
sort_col, asc = sort_map[sort_by]
if sort_col in table_df.columns:
    table_df = table_df.sort_values(sort_col, ascending=asc)

with st.expander("📋 Tabela pozycji — szczegóły", expanded=False):
    if table_df.empty:
        st.info("Brak pozycji spełniających wybrane filtry.")
    else:
        table_total = float(portfolio_summary(table_df)["total_value"])
        render_open_positions_table(table_df, currency, total_value=table_total, show_52w=True)
        st.caption(
            "Kolumna **52W Low → High** pokazuje, gdzie jest aktualna cena w rocznym zakresie. "
            "Przy P&L widzisz też udział zysku/straty w całym portfelu."
        )

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
