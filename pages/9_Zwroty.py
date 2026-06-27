"""
Podstrona: prawdziwe stopy zwrotu (MWR/XIRR + TWR), porównanie z benchmarkiem
oraz lokalne snapshoty wartości portfela w czasie.
"""

import streamlit as st
import pandas as pd

from core.analyzer import analyze_portfolio, portfolio_summary
from core.portfolio_benchmark import (
    DEFAULT_BENCHMARK,
    PORTFOLIO_BENCHMARKS,
    build_portfolio_vs_benchmark,
    relative_performance,
)
from core.benchmark_risk import compute_benchmark_risk_series, summarize_benchmark_risk
from core.performance_analytics import (
    MULTI_BENCHMARK_NAMES,
    build_portfolio_vs_multi_benchmark,
    compute_calendar_returns,
    compute_return_attribution,
    compute_rolling_returns_heatmap,
    compute_whatif_scenario,
    run_monte_carlo,
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
    build_benchmark_risk_chart,
    build_calendar_returns_heatmap,
    build_monte_carlo_fan_chart,
    build_multi_benchmark_chart,
    build_portfolio_vs_benchmark_chart,
    build_return_attribution_chart,
    build_rolling_returns_heatmap,
    build_snapshots_chart,
    build_twr_index_chart,
    build_twr_with_drawdown_chart,
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

tab_returns, tab_benchmark, tab_attribution, tab_snapshots, tab_scenarios = st.tabs(
    [
        "📊 Stopa zwrotu (MWR / TWR)",
        "🏁 Portfel vs benchmark",
        "🎯 Atrybucja i rolling",
        "📌 Snapshoty",
        "🔮 Scenariusze",
    ]
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

            st.markdown("##### Krzywa TWR + drawdown (underwater)")
            st.plotly_chart(build_twr_with_drawdown_chart(twr.index), use_container_width=True)
            st.caption(
                "Dolny panel pokazuje spadek od szczytu (%) — jak w funduszach: "
                "equity curve + underwater chart."
            )

            st.markdown("##### Kalendarz dziennych zwrotów")
            calendar_df = compute_calendar_returns(twr.index)
            if calendar_df.empty:
                st.caption("Za mało danych do kalendarza zwrotów.")
            else:
                st.plotly_chart(
                    build_calendar_returns_heatmap(calendar_df),
                    use_container_width=True,
                )
                st.caption(
                    "Kolor = dzienny zwrot TWR (zielony zysk, czerwony spadek). "
                    "Intuicyjny podgląd jak GitHub contributions — dobry do PDF."
                )

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

                with st.spinner("Liczenie beta i tracking error…"):
                    risk_series = compute_benchmark_risk_series(twr.index, benchmark_name)
                    risk_summary = summarize_benchmark_risk(risk_series)

                if risk_summary.has_data:
                    st.markdown("##### Beta i tracking error (rolling 1Y)")
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.metric(
                            "Beta (ostatnia)",
                            f"{risk_summary.beta:.2f}" if risk_summary.beta is not None else "—",
                            help="Wrażliwość portfela na ruchy benchmarku.",
                        )
                    with r2:
                        st.metric(
                            "Tracking error",
                            f"{risk_summary.tracking_error_pct:.1f}%"
                            if risk_summary.tracking_error_pct is not None
                            else "—",
                            help="Roczne odchylenie dziennych zwrotów portfela od benchmarku.",
                        )
                    with r3:
                        st.metric(
                            "Information ratio",
                            f"{risk_summary.information_ratio:.2f}"
                            if risk_summary.information_ratio is not None
                            else "—",
                            help="Nadwyżka zwrotu / tracking error.",
                        )
                    st.plotly_chart(
                        build_benchmark_risk_chart(risk_series, benchmark_name),
                        use_container_width=True,
                    )
                else:
                    st.caption(
                        "Beta i tracking error wymagają co najmniej ~1 roku wspólnych danych "
                        "portfela i benchmarku."
                    )

            st.divider()
            st.markdown("##### Porównanie wielu benchmarków naraz")
            st.caption(
                "Jedna linia portfela + cienkie linie indeksów — SPY/S&P 500, QQQ/NASDAQ, "
                "MSCI World, WIG20."
            )
            with st.spinner("Pobieranie wielu benchmarków…"):
                multi = build_portfolio_vs_multi_benchmark(
                    twr.index, list(MULTI_BENCHMARK_NAMES)
                )
            if multi.empty:
                st.info("Brak danych do wykresu multi-benchmark.")
            else:
                st.plotly_chart(
                    build_multi_benchmark_chart(multi, list(MULTI_BENCHMARK_NAMES)),
                    use_container_width=True,
                )

# ───────────────────────── Atrybucja i rolling ─────────────────────────
with tab_attribution:
    st.subheader("Atrybucja zwrotu i rolling returns")
    st.caption(
        "Ile poszczególne pozycje / sektory / regiony wniosły do TWR w wybranym okresie "
        "oraz heatmapa rolling returns."
    )

    if report.cash_operations is None:
        st.warning("Wymagany natywny eksport Excel z arkuszem Cash Operations.")
    else:
        with st.spinner("Liczenie TWR i atrybucji…"):
            timeline = get_portfolio_timeline()
            twr = compute_twr(timeline, report.cash_operations)
            analyzed = get_analyzed_open()

        if not twr.has_data or twr.index.empty:
            st.info("Za mało danych timeline, aby policzyć atrybucję.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                group_by = st.selectbox(
                    "Grupuj wg",
                    ["position", "sector", "region"],
                    format_func=lambda x: {"position": "Pozycja", "sector": "Sektor", "region": "Region"}[x],
                    key="attr_group_by",
                )
            with c2:
                period = st.selectbox(
                    "Okres",
                    ["Cały okres", "YTD", "1 rok", "6 miesięcy", "3 miesiące"],
                    key="attr_period",
                )
            with c3:
                freq = st.selectbox(
                    "Rolling — wiersze",
                    ["month", "quarter"],
                    format_func=lambda x: "Miesiące" if x == "month" else "Kwartały",
                    key="rolling_freq",
                )

            with st.spinner("Liczenie atrybucji zwrotu…"):
                attribution = compute_return_attribution(
                    report.cash_operations,
                    twr.index,
                    group_by=group_by,
                    period=period,
                    analyzed=analyzed,
                )

            if attribution.empty:
                st.info("Za mało danych do atrybucji w wybranym okresie.")
            else:
                group_label = {"position": "pozycje", "sector": "sektory", "region": "regiony"}[group_by]
                st.plotly_chart(
                    build_return_attribution_chart(attribution, f"{period}, {group_label}"),
                    use_container_width=True,
                )
                st.caption(
                    "Wkład w pp — suma dziennych wag × zwrotów pozycji (link effect). "
                    "Pokazuje, które obszary portfela napędzały lub hamowały TWR."
                )

            st.divider()
            st.markdown("##### Rolling returns — heatmapa")
            heatmap_df = compute_rolling_returns_heatmap(twr.index, freq=freq)
            if heatmap_df.empty:
                st.info("Za mało danych do heatmapy rolling returns.")
            else:
                st.plotly_chart(
                    build_rolling_returns_heatmap(heatmap_df),
                    use_container_width=True,
                )
                st.caption(
                    "Szybka odpowiedź: czy ostatnie 3 miesiące odstają od długiego trendu? "
                    "Porównaj wiersze (okresy) z kolumną 3M vs 1Y."
                )

# ───────────────────────── Scenariusze ─────────────────────────
with tab_scenarios:
    st.subheader("Scenariusze „co jeśli”")
    st.caption("Prosty stress test i symulacja Monte Carlo na historycznych zwrotach TWR.")

    analyzed = get_analyzed_open()
    twr = None
    if report.cash_operations is not None:
        with st.spinner("Liczenie TWR…"):
            timeline = get_portfolio_timeline()
            twr = compute_twr(timeline, report.cash_operations)

    st.markdown("#### Stress test — spadek top pozycji")
    if analyzed is None or analyzed.empty:
        st.info("Brak otwartych pozycji do symulacji.")
    else:
        s1, s2 = st.columns(2)
        with s1:
            top_n = st.slider("Top N pozycji", min_value=1, max_value=10, value=3, key="whatif_top_n")
        with s2:
            shock_pct = st.slider(
                "Spadek cen (%)",
                min_value=-50,
                max_value=0,
                value=-10,
                step=1,
                key="whatif_shock",
            )

        whatif = compute_whatif_scenario(
            analyzed,
            top_n=top_n,
            shock_pct=shock_pct,
            twr_index=twr.index if twr and twr.has_data else None,
        )

        if whatif.has_data:
            w1, w2, w3, w4 = st.columns(4)
            with w1:
                st.metric(
                    "Wartość dziś",
                    format_currency(whatif.current_value, display_currency),
                )
            with w2:
                st.metric(
                    "Po scenariuszu",
                    format_currency(whatif.shocked_value, display_currency),
                    delta=f"{whatif.change_pct:+.1f}%",
                    delta_color=pnl_delta_color(whatif.change_pct),
                )
            with w3:
                st.metric("Drawdown dziś", f"{whatif.current_drawdown_pct:.1f}%")
            with w4:
                st.metric(
                    "Drawdown po scenariuszu",
                    f"{whatif.shocked_drawdown_pct:.1f}%",
                    delta=f"{whatif.shocked_drawdown_pct - whatif.current_drawdown_pct:+.1f} pp",
                    delta_color=pnl_delta_color(
                        whatif.shocked_drawdown_pct - whatif.current_drawdown_pct
                    ),
                )

            if whatif.shocked_positions:
                shock_df = pd.DataFrame(whatif.shocked_positions)
                shock_df["old_value"] = shock_df["old_value"].round(2)
                shock_df["new_value"] = shock_df["new_value"].round(2)
                shock_df["weight_pct"] = shock_df["weight_pct"].round(1)
                st.dataframe(
                    shock_df.rename(
                        columns={
                            "ticker": "Ticker",
                            "old_value": f"Wartość ({display_currency})",
                            "new_value": f"Po scenariuszu ({display_currency})",
                            "weight_pct": "Waga %",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    st.divider()
    st.markdown("#### Monte Carlo (bootstrap historycznych zwrotów)")

    if twr is None or not twr.has_data or twr.index.empty:
        st.info("Monte Carlo wymaga timeline z Cash Operations (min. ~30 dni TWR).")
    else:
        mc1, mc2 = st.columns(2)
        with mc1:
            horizon_years = st.selectbox(
                "Horyzont",
                [1, 3, 5],
                format_func=lambda x: f"{x} {'rok' if x == 1 else 'lata'}",
                index=1,
                key="mc_horizon",
            )
        with mc2:
            n_sims = st.selectbox("Symulacje", [200, 500, 1000], index=1, key="mc_sims")

        with st.spinner("Symulacja Monte Carlo…"):
            mc = run_monte_carlo(
                twr.index,
                horizon_years=float(horizon_years),
                n_simulations=n_sims,
            )

        if not mc.has_data:
            st.info("Za mało historycznych zwrotów do symulacji (min. ~30 dni).")
        else:
            st.plotly_chart(
                build_monte_carlo_fan_chart(mc.paths, float(horizon_years)),
                use_container_width=True,
            )
            last = mc.paths.iloc[-1]
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("P10 (pesymistyczny)", f"{last['p10']:.0f}")
            with m2:
                st.metric("Mediana P50", f"{last['p50']:.0f}")
            with m3:
                st.metric("P90 (optymistyczny)", f"{last['p90']:.0f}")
            st.caption(
                f"Rozkład wartości portfela za {horizon_years} lat "
                f"({mc.n_simulations} symulacji, bootstrap dziennych zwrotów TWR). "
                "Indeks start = 100. To uproszczenie — bez pełnej macierzy korelacji pozycji."
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
