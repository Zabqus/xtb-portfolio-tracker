"""
Podstrona: prawdziwe stopy zwrotu (MWR/XIRR + TWR), porównanie z benchmarkiem
oraz lokalne snapshoty wartości portfela w czasie.
"""

import streamlit as st

from core.analyzer import analyze_portfolio, portfolio_summary
from core.portfolio_benchmark import (
    DEFAULT_BENCHMARK,
    PORTFOLIO_BENCHMARKS,
    build_portfolio_vs_benchmark,
    relative_performance,
)
from core.returns import MIN_ANNUALIZE_DAYS, compute_mwr, compute_twr
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_portfolio_timeline,
    get_report,
)
from core.snapshots import (
    add_snapshot,
    available_currencies,
    clear_snapshots,
    load_snapshots,
    snapshots_to_df,
)
from ui.formatters import format_currency, pnl_delta_color
from ui.returns_charts import (
    build_portfolio_vs_benchmark_chart,
    build_snapshots_chart,
    build_twr_index_chart,
)
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page

bootstrap_page()
st.title("📈 Zwroty i wartość w czasie")
st.caption(
    "Prawdziwa stopa zwrotu portfela (ważona czasem i przepływami), porównanie "
    "z indeksem oraz własne snapshoty wartości."
)

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

report = get_report()
if report is None:
    st.stop()

display_currency = get_display_currency()

tab_returns, tab_benchmark, tab_snapshots = st.tabs(
    ["📊 Stopa zwrotu (MWR / TWR)", "🏁 Portfel vs benchmark", "📌 Snapshoty"]
)

# ───────────────────────── MWR / TWR ─────────────────────────
with tab_returns:
    st.subheader("Prawdziwa stopa zwrotu")

    if report.cash_operations is None:
        st.warning(
            "Stopy MWR/TWR wymagają natywnego eksportu Excel z arkuszem "
            "**Cash Operations** (potrzebne przepływy i timeline)."
        )
    else:
        with st.spinner("Budowanie timeline i liczenie zwrotów…"):
            timeline = get_portfolio_timeline()
            twr = compute_twr(timeline, report.cash_operations)

            mwr = None
            if not report.is_merged:
                acct_ccy = report.account_currency
                analyzed_acct = analyze_portfolio(
                    report.open_positions, display_currency=acct_ccy
                )
                holdings_acct = float(portfolio_summary(analyzed_acct)["total_value"])
                mwr = compute_mwr(
                    report.cash_operations, holdings_acct, currency=acct_ccy
                )

        # — MWR (ważona przepływami) —
        st.markdown("#### MWR — zwrot ważony przepływami (Twój kapitał)")
        if mwr is None:
            st.info(
                "MWR liczymy dla pojedynczego konta — przy trybie multi-account "
                "wpłaty są w różnych walutach. TWR poniżej działa również dla multi-account."
            )
        elif not mwr.has_data:
            st.info("Brak operacji wpłat (Deposit) w eksporcie — nie można policzyć MWR.")
        else:
            cc = mwr.currency
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Wpłaty netto", format_currency(mwr.net_contributions, cc))
            with c2:
                st.metric(
                    "Wartość konta dziś",
                    format_currency(mwr.terminal_value, cc),
                    help="Pozycje otwarte + szacowane wolne środki (suma Amount).",
                )
            with c3:
                st.metric(
                    "Zysk / strata",
                    format_currency(mwr.total_gain, cc),
                    delta_color=pnl_delta_color(mwr.total_gain),
                )
            with c4:
                if mwr.xirr_pct is not None:
                    st.metric(
                        "MWR roczny (XIRR)",
                        f"{mwr.xirr_pct:+.1f}%",
                        help="Roczna stopa uwzględniająca timing wpłat.",
                    )
                elif mwr.simple_return_pct is not None:
                    st.metric(
                        "Zwrot na kapitale",
                        f"{mwr.simple_return_pct:+.1f}%",
                        help=f"Okres < {MIN_ANNUALIZE_DAYS} dni — bez annualizacji.",
                    )
                else:
                    st.metric("MWR", "—")

            note = (
                f"Wolne środki: **{format_currency(mwr.cash_balance, cc)}** · "
                f"pozycje: **{format_currency(mwr.holdings_value, cc)}** · "
                f"{mwr.flow_count} wpłat/wypłat · okres {mwr.days} dni."
            )
            if mwr.xirr_pct is None and mwr.days < MIN_ANNUALIZE_DAYS:
                note += (
                    f" Okres krótszy niż {MIN_ANNUALIZE_DAYS} dni — roczny XIRR "
                    "pominięty (przeliczenie byłoby zawyżone)."
                )
            st.caption(note)

        st.divider()

        # — TWR (ważona czasem) —
        st.markdown("#### TWR — zwrot ważony czasem (jakość doboru pozycji)")
        if not twr.has_data:
            st.info("Za mało danych w timeline, aby policzyć TWR.")
        else:
            t1, t2, t3 = st.columns(3)
            with t1:
                st.metric(
                    "TWR (cały okres)",
                    f"{twr.twr_total_pct:+.1f}%" if twr.twr_total_pct is not None else "—",
                )
            with t2:
                if twr.twr_annualized_pct is not None:
                    st.metric("TWR roczny", f"{twr.twr_annualized_pct:+.1f}%")
                else:
                    st.metric(
                        "TWR roczny",
                        "—",
                        help=f"Okres < {MIN_ANNUALIZE_DAYS} dni — bez annualizacji.",
                    )
            with t3:
                st.metric("Długość okresu", f"{twr.days} dni")

            st.plotly_chart(build_twr_index_chart(twr.index), use_container_width=True)

        with st.expander("ℹ️ MWR vs TWR — czym się różnią?"):
            st.markdown(
                """
                - **MWR (XIRR)** odpowiada na pytanie *„ile zarobiłem na włożonym kapitale?”*
                  Uwzględnia, **kiedy** dopłacałeś — duża wpłata tuż przed wzrostem podbija MWR.
                - **TWR** odpowiada *„jak dobre były moje pozycje?”* Usuwa wpływ momentu wpłat,
                  więc jest **porównywalny z indeksami i funduszami**.
                - Gdy regularnie dopłacasz, **TWR ≠ MWR** — i to normalne. Duża różnica oznacza,
                  że timing wpłat istotnie wpłynął na wynik.

                *MWR liczony w walucie konta na podstawie wpłat/wypłat z Cash Operations.
                Zakłada, że eksport obejmuje pełną historię konta (do oszacowania wolnych środków).*
                """
            )

# ───────────────────────── Portfel vs benchmark ─────────────────────────
with tab_benchmark:
    st.subheader("Portfel (TWR) vs benchmark rynkowy")
    st.caption(
        "Porównujemy **indeks TWR** portfela (bez wpływu dopłat) z indeksem rynkowym — "
        "to jedyne uczciwe zestawienie portfela z dopłatami i benchmarku."
    )

    if report.cash_operations is None:
        st.warning("Wymagany natywny eksport Excel z arkuszem Cash Operations.")
    else:
        with st.spinner("Liczenie TWR…"):
            timeline = get_portfolio_timeline()
            twr = compute_twr(timeline, report.cash_operations)

        if not twr.has_data or twr.index.empty:
            st.info("Za mało danych timeline, aby zbudować krzywą porównawczą.")
        else:
            bench_names = list(PORTFOLIO_BENCHMARKS.keys())
            default_idx = bench_names.index(DEFAULT_BENCHMARK) if DEFAULT_BENCHMARK in bench_names else 0
            benchmark_name = st.selectbox(
                "Benchmark", bench_names, index=default_idx, key="portfolio_benchmark_select"
            )

            with st.spinner(f"Pobieranie danych: {benchmark_name}…"):
                merged = build_portfolio_vs_benchmark(twr.index, benchmark_name)

            if merged.empty or "benchmark" not in merged.columns:
                st.warning(
                    f"Nie udało się pobrać danych dla **{benchmark_name}**. "
                    "Spróbuj innego indeksu."
                )
                st.plotly_chart(
                    build_portfolio_vs_benchmark_chart(merged, benchmark_name),
                    use_container_width=True,
                )
            else:
                rel = relative_performance(merged)
                if rel is not None:
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        st.metric("Portfel (TWR)", f"{rel['portfolio_pct']:+.1f}%")
                    with b2:
                        st.metric(benchmark_name, f"{rel['benchmark_pct']:+.1f}%")
                    with b3:
                        st.metric(
                            "Alpha (portfel − benchmark)",
                            f"{rel['alpha_pct']:+.1f} pp",
                            delta_color=pnl_delta_color(rel["alpha_pct"]),
                            help="Przewaga (lub strata) względem indeksu w punktach procentowych.",
                        )

                st.plotly_chart(
                    build_portfolio_vs_benchmark_chart(merged, benchmark_name),
                    use_container_width=True,
                )
                st.caption(
                    "Obie krzywe startują od 100 w tym samym dniu. Powyżej benchmarku = "
                    "Twój portfel bije rynek; poniżej = przegrywa z rynkiem."
                )

# ───────────────────────── Snapshoty ─────────────────────────
with tab_snapshots:
    st.subheader("Snapshoty portfela")
    st.caption(
        "Zapisuj bieżący stan portfela do lokalnego pliku `snapshots.json`. "
        "Buduje własny timeline wartości — działa też dla importu CSV (bez Cash Operations)."
    )

    analyzed = get_analyzed_open()
    col_save, col_info = st.columns([1, 2])
    with col_save:
        if st.button("📌 Zapisz snapshot na dziś", type="primary", key="save_snapshot_btn"):
            if analyzed is None or analyzed.empty:
                st.error("Brak przeanalizowanego portfela do zapisania.")
            else:
                summary = portfolio_summary(analyzed)
                is_new, msg = add_snapshot(summary, display_currency, analyzed)
                if is_new:
                    st.success(msg)
                else:
                    st.info(msg)
    with col_info:
        st.caption(
            f"Snapshot zapisze się w walucie wyświetlania: **{display_currency}**. "
            "Jeden zapis na dzień (kolejny tego samego dnia nadpisuje poprzedni)."
        )

    all_currencies = available_currencies()
    if not all_currencies:
        st.info("Brak zapisanych snapshotów. Kliknij **Zapisz snapshot na dziś**, aby zacząć.")
    else:
        view_ccy = display_currency if display_currency in all_currencies else all_currencies[0]
        if len(all_currencies) > 1:
            view_ccy = st.selectbox(
                "Waluta snapshotów", all_currencies,
                index=all_currencies.index(view_ccy), key="snapshot_ccy_view",
            )

        snaps = snapshots_to_df(currency=view_ccy)
        if snaps.empty:
            st.info(f"Brak snapshotów w walucie {view_ccy}.")
        else:
            last = snaps.iloc[-1]
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                st.metric("Snapshotów", len(snaps))
            with s2:
                st.metric("Ostatnia wartość", format_currency(float(last["total_value"]), view_ccy))
            with s3:
                st.metric(
                    "Ostatni PnL",
                    format_currency(float(last["total_pnl"]), view_ccy),
                    delta=f"{float(last['roi_pct']):+.1f}% ROI",
                    delta_color=pnl_delta_color(float(last["total_pnl"])),
                )
            with s4:
                if len(snaps) >= 2:
                    change = float(last["total_value"]) - float(snaps.iloc[-2]["total_value"])
                    st.metric(
                        "Zmiana vs poprzedni",
                        format_currency(change, view_ccy),
                        delta_color=pnl_delta_color(change),
                    )
                else:
                    st.metric("Zmiana vs poprzedni", "—")

            st.plotly_chart(build_snapshots_chart(snaps, view_ccy), use_container_width=True)

            show = snaps.copy()
            show["date"] = show["date"].dt.strftime("%Y-%m-%d")
            for col in ("total_value", "total_cost", "total_pnl", "roi_pct"):
                show[col] = show[col].astype(float).round(2)
            show = show.rename(
                columns={
                    "date": "Data",
                    "total_value": f"Wartość ({view_ccy})",
                    "total_cost": f"Koszt ({view_ccy})",
                    "total_pnl": f"PnL ({view_ccy})",
                    "roi_pct": "ROI %",
                    "positions_count": "Pozycje",
                }
            )
            st.dataframe(
                show.drop(columns=["currency"]).iloc[::-1],
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("⚙️ Zarządzaj snapshotami"):
            st.caption(f"Łącznie zapisów (wszystkie waluty): {len(load_snapshots())}")
            if st.button("🗑️ Usuń wszystkie snapshoty", key="clear_snapshots_btn"):
                clear_snapshots()
                st.success("Usunięto wszystkie snapshoty.")
                st.rerun()
