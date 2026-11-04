"""
Podstrona: historia transakcji, zamknięte pozycje, timeline portfela.
"""

import pandas as pd
import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from core.closed_analysis import closed_positions_summary, get_top_trades
from core.cost_basis import get_current_cost_basis
from core.belka_tax import compute_belka_year
from core.dividends import (
    dividends_per_ticker,
    dividends_per_year,
    dividends_summary,
    parse_dividends,
)
from core.pit38_export import Pit38ExportError, default_pit38_filename, generate_pit38_excel_bytes
from core.tax_loss_carry import (
    delete_carry_year,
    load_carry_entries,
    upsert_carry_loss,
)
from core.dividend_calendar import (
    build_dividend_calendar,
    build_dividend_growth_tracker,
    build_dividend_yield_comparison,
    build_projected_dividend_cashflow_12m,
)
from core.earnings_calendar import build_earnings_calendar
from core.session import (
    get_analyzed_open,
    get_cost_basis_history,
    get_display_currency,
    get_portfolio_timeline,
    get_report,
    get_trade_analytics,
)
from core.ike_ikze import (
    IKE_LIMIT_2025,
    IKZE_LIMIT_2025,
    IKZE_LIMIT_BIZ_2025,
    PIT_RATES,
    compare_accounts,
)
from core.tax_harvest import compute_tax_harvest
from core.trade_analytics import (
    add_trade_efficiency_metrics,
    apply_trade_tags,
    classify_exit_strategy,
    compute_expectancy_metrics,
    compute_rolling_metrics,
    compute_streak_stats,
    compute_trade_heatmap,
    filter_round_trips,
    filter_trades_for_analytics,
    summarize_tags,
)
from core.trade_excursions import compute_mae_mfe
from core.trade_tags import persist_tags_from_dataframe
from core.transactions import parse_cash_operations_trades
from ui.analytics_charts import (
    build_efficiency_chart,
    build_cost_basis_chart,
    build_exit_strategy_chart,
    build_holding_period_chart,
    build_holding_vs_outcome_chart,
    build_mae_mfe_chart,
    build_rolling_metrics_chart,
    build_round_trip_pnl_chart,
    build_streak_chart,
    build_tag_performance_chart,
    build_trade_heatmap_chart,
    build_trader_equity_curve,
    build_win_loss_comparison,
)
from ui.charts import build_closed_pnl_chart
from ui.formatters import format_currency, pnl_delta_color
from ui.history_charts import (
    build_contributions_vs_value_chart,
    build_cumulative_dividends_chart,
    build_cumulative_realized_pnl,
    build_dividend_growth_tracker_chart,
    build_dividend_yield_comparison_chart,
    build_dividends_per_year_chart,
    build_ex_dividend_calendar_chart,
    build_portfolio_timeline_chart,
    build_projected_dividend_cashflow_chart,
)
from ui.returns_charts import build_portfolio_value_drawdown_chart
from ui.sidebar import render_import_sidebar
from ui.tables import render_closed_positions_table, render_round_trips_table
from ui.tax_charts import build_ike_ikze_bars_chart, build_ike_ikze_comparison_chart
from ui.theme import bootstrap_page, metric_card_style, page_header, section_header

bootstrap_page()
page_header(
    "Historia",
    "Timeline, trade analytics, zamknięte pozycje, podatek i kalendarz",
)

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

report = get_report()
if report is None:
    st.stop()

currency = get_display_currency()
closed = report.closed_positions

(
    tab_timeline,
    tab_analytics,
    tab_closed,
    tab_tax,
    tab_calendar,
) = st.tabs(
    [
        "Timeline",
        "Trade Analytics",
        "Zamknięte",
        "Podatek Belki",
        "Kalendarz",
    ]
)

# --- Timeline ---
with tab_timeline:
    section_header(
        "Wartość portfela w czasie",
        "Rekonstrukcja z Cash Operations: dzienne saldo wycenione kursem Yahoo",
    )

    if report.cash_operations is None:
        st.warning("Timeline wymaga natywnego eksportu Excel z arkuszem Cash Operations.")
    else:
        with st.spinner("Budowanie timeline portfela (ceny historyczne)…"):
            timeline = get_portfolio_timeline()

        if timeline is None or timeline.empty:
            st.warning("Brak danych do zbudowania timeline.")
        else:
            valid = timeline.dropna(subset=["market_value"])
            if not valid.empty:
                last = valid.iloc[-1]
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric(
                        "Ostatnia wartość",
                        format_currency(float(last["market_value"]), currency),
                    )
                with c2:
                    st.metric(
                        "Baza kosztowa",
                        format_currency(float(last["cost_basis"]), currency),
                    )
                with c3:
                    unr = float(last["market_value"]) - float(last["cost_basis"])
                    st.metric(
                        "Niezrealizowany PnL",
                        format_currency(unr, currency),
                        delta_color=pnl_delta_color(unr),
                    )

            st.plotly_chart(
                build_portfolio_timeline_chart(timeline, currency),
                use_container_width=True,
            )

            with st.expander("Wartość + drawdown", expanded=False):
                st.plotly_chart(
                    build_portfolio_value_drawdown_chart(timeline, currency),
                    use_container_width=True,
                )
                st.caption(
                    "Górny panel: wartość rynkowa. Dolny: underwater — spadek od szczytu (%)."
                )

            with st.expander("Wpłaty vs wartość rynkowa", expanded=False):
                st.plotly_chart(
                    build_contributions_vs_value_chart(
                        timeline, report.cash_operations, currency
                    ),
                    use_container_width=True,
                )
                st.caption(
                    "Powyżej linii wpłat = zysk rynkowy; poniżej = strata względem wniesionych środków."
                )

# --- Trade Analytics ---
with tab_analytics:
    section_header("Statystyki tradingowe", "Round-tripy FIFO z Cash Operations")

    if report.cash_operations is None:
        st.warning("Wymagany natywny eksport Excel z arkuszem Cash Operations.")
    else:
        with st.spinner("Analiza transakcji i cost basis…"):
            summary, round_trips = get_trade_analytics()
            cost_history = get_cost_basis_history()

        has_round_trips = round_trips is not None and not round_trips.empty
        if summary is None or (summary.closed_trades == 0 and not has_round_trips):
            st.info("Brak zamkniętych round-tripów w wybranym okresie eksportu.")
        else:
            pf = summary.profit_factor
            pf_label = f"{pf:.2f}" if pf < 100 else "∞"

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            with m1:
                st.metric("Round-tripy", summary.closed_trades)
            with m2:
                st.metric("Win rate", f"{summary.win_rate_pct:.1f}%")
            with m3:
                st.metric("Śr. czas trzymania", f"{summary.avg_holding_days:.1f} dni")
            with m4:
                st.metric("Średni zysk", format_currency(summary.avg_win, currency))
            with m5:
                st.metric("Średnia strata", format_currency(summary.avg_loss, currency))
            with m6:
                st.metric("Profit factor", pf_label)

            st.caption(
                f"Mediana czasu trzymania: **{summary.median_holding_days:.1f} dni** · "
                f"Łączny zrealizowany PnL (round-tripy): "
                f"**{format_currency(summary.total_realized_pnl, currency)}**"
            )

            rt = pd.DataFrame()
            if has_round_trips:
                all_round_trips = round_trips.copy()
                all_round_trips["close_time"] = pd.to_datetime(
                    all_round_trips["close_time"], errors="coerce"
                )
                min_close = all_round_trips["close_time"].min().date()
                max_close = all_round_trips["close_time"].max().date()
                tickers_rt = ["Wszystkie"] + sorted(all_round_trips["ticker_xtb"].unique())

                st.markdown("### Filtry analizy")
                f1, f2, f3 = st.columns([2, 2, 2])
                with f1:
                    selected_ticker = st.selectbox(
                        "Ticker",
                        tickers_rt,
                        key="analytics_ticker_filter",
                    )
                with f2:
                    date_from = st.date_input(
                        "Od (data zamknięcia)",
                        value=min_close,
                        min_value=min_close,
                        max_value=max_close,
                        key="analytics_date_from",
                    )
                with f3:
                    date_to = st.date_input(
                        "Do (data zamknięcia)",
                        value=max_close,
                        min_value=min_close,
                        max_value=max_close,
                        key="analytics_date_to",
                    )

                rt = filter_round_trips(
                    all_round_trips,
                    ticker=selected_ticker,
                    date_from=pd.Timestamp(date_from),
                    date_to=pd.Timestamp(date_to),
                )
                if rt.empty:
                    st.warning("Brak round-tripów dla wybranych filtrów.")
                else:
                    st.caption(
                        f"Filtr aktywny: **{len(rt)} / {len(all_round_trips)}** round-tripów."
                    )

                exp = compute_expectancy_metrics(rt if not rt.empty else all_round_trips)
                e1, e2, e3 = st.columns(3)
                with e1:
                    st.metric("Expectancy / trade", format_currency(exp["expectancy_value"], currency))
                with e2:
                    st.metric("Expectancy (R)", f"{exp['expectancy_r']:.2f} R")
                with e3:
                    st.metric("Avg R-multiple", f"{exp['avg_r_multiple']:.2f} R")

            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(
                    build_win_loss_comparison(summary.avg_win, summary.avg_loss, currency),
                    use_container_width=True,
                )
            with c2:
                if has_round_trips and not rt.empty:
                    st.plotly_chart(
                        build_holding_period_chart(rt),
                        use_container_width=True,
                    )
                elif has_round_trips:
                    st.info("Brak danych do histogramu czasu trzymania dla filtra.")

            if has_round_trips and not rt.empty:
                trades = parse_cash_operations_trades(report.cash_operations)
                trades_filtered = filter_trades_for_analytics(trades, rt)

                st.caption("Krzywa equity — skumulowany zrealizowany PnL + markery transakcji")
                st.plotly_chart(
                    build_trader_equity_curve(rt, trades_filtered, currency),
                    use_container_width=True,
                )

                with st.expander("MAE / MFE i efficiency exitu", expanded=False):
                    st.caption(
                        "MAE — najgłębsza strata niezrealizowana; MFE — najwyższy niezrealizowany zysk. "
                        "Efficiency: realizacja względem MFE (zyski) lub MAE (straty)."
                    )
                    with st.spinner("Pobieranie cen historycznych (Yahoo)…"):
                        trips_exc = compute_mae_mfe(rt)
                    st.plotly_chart(build_mae_mfe_chart(trips_exc), use_container_width=True)
                    trips_eff = add_trade_efficiency_metrics(trips_exc)
                    st.plotly_chart(build_efficiency_chart(trips_eff), use_container_width=True)

                with st.expander("Forma tradera — rolling, heatmapy, serie", expanded=False):
                    st.plotly_chart(
                        build_holding_vs_outcome_chart(rt),
                        use_container_width=True,
                    )
                    rolling = compute_rolling_metrics(rt, windows=(30, 50))
                    st.plotly_chart(
                        build_rolling_metrics_chart(rolling),
                        use_container_width=True,
                    )

                    daily_heat, weekly_heat = compute_trade_heatmap(rt)
                    h1, h2 = st.columns(2)
                    with h1:
                        st.plotly_chart(
                            build_trade_heatmap_chart(
                                daily_heat,
                                "Heatmap P&L: dzień tygodnia × godzina",
                                "Godzina",
                                "Dzień",
                            ),
                            use_container_width=True,
                        )
                    with h2:
                        st.plotly_chart(
                            build_trade_heatmap_chart(
                                weekly_heat,
                                "Heatmap P&L: rok × tydzień ISO",
                                "Tydzień",
                                "Rok",
                            ),
                            use_container_width=True,
                        )

                    streak_stats = compute_streak_stats(rt)
                    s1, s2, s3, s4 = st.columns(4)
                    with s1:
                        st.metric("Max seria wygranych", streak_stats["max_win_streak"])
                    with s2:
                        st.metric("Max seria przegranych", streak_stats["max_loss_streak"])
                    with s3:
                        st.metric("Bieżąca seria", streak_stats["current_streak"])
                    with s4:
                        label = (
                            "wygranych"
                            if streak_stats["current_streak_type"] == "win"
                            else "przegranych"
                        )
                        st.metric("Typ serii", label)
                    st.plotly_chart(
                        build_streak_chart(rt, streak_stats["streak_events"]),
                        use_container_width=True,
                    )

                with st.expander("Strategie wyjścia i tagi", expanded=False):
                    trips_exit = classify_exit_strategy(rt)
                    st.caption(
                        "Heurystyka: zysk >20%, stop-loss (≤-5%), time-based (≥90 dni), inne."
                    )
                    st.plotly_chart(
                        build_exit_strategy_chart(trips_exit), use_container_width=True
                    )

                    st.caption("Tagi ręczne — zapis lokalny w `trade_tags.json`.")
                    tagged = apply_trade_tags(rt)
                    editable = tagged[
                        [
                            "trip_id",
                            "ticker_xtb",
                            "open_time",
                            "close_time",
                            "realized_pnl",
                            "entry_tag",
                            "exit_tag",
                        ]
                    ].copy()
                    editable = editable.rename(
                        columns={
                            "ticker_xtb": "Ticker",
                            "open_time": "Open",
                            "close_time": "Close",
                            "realized_pnl": "PnL",
                            "entry_tag": "Entry tag",
                            "exit_tag": "Exit tag",
                        }
                    )
                    edited = st.data_editor(
                        editable,
                        use_container_width=True,
                        hide_index=True,
                        key="trade_tags_editor",
                        num_rows="fixed",
                        column_config={"trip_id": None},
                    )
                    tagged["entry_tag"] = (
                        edited["Entry tag"].astype(str).str.strip().replace("", "other")
                    )
                    tagged["exit_tag"] = (
                        edited["Exit tag"].astype(str).str.strip().replace("", "other")
                    )
                    saved_count = persist_tags_from_dataframe(
                        tagged,
                        trip_id_col="trip_id",
                        entry_col="entry_tag",
                        exit_col="exit_tag",
                    )
                    if saved_count:
                        st.caption(f"Zapisano {saved_count} zmian tagów do `trade_tags.json`.")
                    tag_summary = summarize_tags(tagged)
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        st.plotly_chart(
                            build_tag_performance_chart(tag_summary, kind="entry"),
                            use_container_width=True,
                        )
                    with tc2:
                        st.plotly_chart(
                            build_tag_performance_chart(tag_summary, kind="exit"),
                            use_container_width=True,
                        )

                with st.expander("Lista round-tripów (FIFO)", expanded=False):
                    st.plotly_chart(
                        build_round_trip_pnl_chart(rt),
                        use_container_width=True,
                    )
                    st.caption(
                        f"**{len(rt)} wierszy** po filtrze (łącznie {len(all_round_trips)})."
                    )
                    render_round_trips_table(rt)

        with st.expander("Cost basis — historia średniej ceny", expanded=False):
            if cost_history is None or cost_history.empty:
                st.info("Brak historii cost basis.")
            else:
                tickers_cb = sorted(cost_history["ticker_xtb"].unique())
                selected_cb = st.selectbox("Ticker", tickers_cb, key="cost_basis_ticker")

                st.plotly_chart(
                    build_cost_basis_chart(cost_history, selected_cb),
                    use_container_width=True,
                )

                with st.expander("Szczegóły zdarzeń (cost basis per ticker)"):
                    ticker_events = cost_history[cost_history["ticker_xtb"] == selected_cb].copy()
                    show_cb = ticker_events[
                        [
                            "trade_time",
                            "event",
                            "trade_qty",
                            "trade_price",
                            "quantity_after",
                            "avg_price_after",
                            "cost_basis_after",
                        ]
                    ].rename(
                        columns={
                            "trade_time": "Czas",
                            "event": "Zdarzenie",
                            "trade_qty": "Ilość transakcji",
                            "trade_price": "Cena transakcji",
                            "quantity_after": "Ilość po",
                            "avg_price_after": "Śr. cena po",
                            "cost_basis_after": "Cost basis po",
                        }
                    )
                    for col in show_cb.columns:
                        if show_cb[col].dtype in ("float64", "float32"):
                            show_cb[col] = show_cb[col].map(
                                lambda x: round(x, 4) if pd.notna(x) else None
                            )
                    st.dataframe(show_cb, use_container_width=True, hide_index=True)

                current = get_current_cost_basis(cost_history)
                if not current.empty:
                    st.markdown("**Aktualny cost basis (otwarte pozycje)**")
                    cur = current.rename(
                        columns={
                            "ticker_xtb": "Ticker",
                            "quantity": "Ilość",
                            "avg_price": "Śr. cena",
                            "cost_basis": "Cost basis",
                            "last_trade_time": "Ostatnia transakcja",
                        }
                    )
                    st.dataframe(cur, use_container_width=True, hide_index=True)

# --- Zamknięte pozycje (+ historia transakcji) ---
with tab_closed:
    section_header(
        "Zrealizowane zyski i straty",
        "Closed Positions z XTB · do analizy FIFO użyj zakładki Trade Analytics",
    )

    if closed is None or closed.empty:
        st.warning(
            "Brak arkusza **Closed Positions** w pliku. "
            "Pobierz pełny eksport Excel z platformy XTB."
        )
    else:
        # Filtr roku podatkowego i kierunku PnL
        closed = closed.copy()
        closed["close_year"] = pd.to_datetime(closed["close_time"], errors="coerce").dt.year
        available_years = sorted(
            closed["close_year"].dropna().unique().astype(int).tolist(), reverse=True
        )

        col_year, col_dir = st.columns([2, 3])
        with col_year:
            selected_year = st.selectbox(
                "Rok podatkowy",
                ["Wszystkie lata"] + available_years,
                key="closed_year_filter",
            )
        with col_dir:
            pnl_filter = st.radio(
                "Filtruj",
                ["Wszystkie", "Tylko zyski", "Tylko straty"],
                horizontal=True,
                key="closed_pnl_filter",
            )

        closed_filtered = closed.copy()
        if selected_year != "Wszystkie lata":
            closed_filtered = closed_filtered[closed_filtered["close_year"] == int(selected_year)]
        if pnl_filter == "Tylko zyski":
            closed_filtered = closed_filtered[closed_filtered["pnl"] > 0]
        elif pnl_filter == "Tylko straty":
            closed_filtered = closed_filtered[closed_filtered["pnl"] < 0]

        if closed_filtered.empty:
            st.info("Brak zamkniętych pozycji dla wybranych filtrów.")
        else:
            stats = closed_positions_summary(closed_filtered)

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Pozycje", stats["count"])
            with col2:
                st.metric(
                    "Łączny PnL",
                    format_currency(stats["total_pnl"], currency),
                    delta_color=pnl_delta_color(stats["total_pnl"]),
                )
            with col3:
                st.metric("Win rate", f"{stats['win_rate_pct']:.1f}%")
            with col4:
                st.metric("Zyskowne", stats["winners"])
            with col5:
                st.metric("Stratne", stats["losers"])

            try:
                style_metric_cards(**metric_card_style())
            except Exception:
                pass

            st.plotly_chart(
                build_cumulative_realized_pnl(closed_filtered, currency),
                use_container_width=True,
            )
            st.plotly_chart(
                build_closed_pnl_chart(closed_filtered, currency),
                use_container_width=True,
            )

            with st.expander("🏆 Top 5 zyskowne / 📉 Top 5 stratne (podgląd)"):
                best, worst = get_top_trades(closed_filtered, n=5)
                bcol, wcol = st.columns(2)

                def _trade_display(df: pd.DataFrame) -> pd.DataFrame:
                    show = df[["ticker_xtb", "instrument", "pnl", "close_time"]].copy()
                    if "purchase_value" in df.columns:
                        pv = df["purchase_value"].replace(0, pd.NA)
                        show["ROI %"] = (df["pnl"] / pv * 100).round(1)
                    show["pnl"] = show["pnl"].round(2)
                    return show

                with bcol:
                    st.markdown("**Najlepsze**")
                    if not best.empty:
                        st.dataframe(_trade_display(best), use_container_width=True, hide_index=True)
                with wcol:
                    st.markdown("**Najgorsze**")
                    if not worst.empty:
                        st.dataframe(_trade_display(worst), use_container_width=True, hide_index=True)

            with st.expander("Wszystkie zamknięte pozycje (XTB)", expanded=False):
                render_closed_positions_table(closed_filtered.drop(columns=["close_year"]))

    with st.expander("Historia transakcji (Cash Operations)", expanded=False):
        if report.cash_operations is None:
            st.warning("Wymagany natywny eksport Excel z arkuszem Cash Operations.")
        else:
            trades = parse_cash_operations_trades(report.cash_operations)
            if trades.empty:
                st.info("Brak transakcji giełdowych w wybranym okresie.")
            else:
                st.caption(f"Łącznie **{len(trades)}** operacji OPEN/CLOSE BUY")

                display = trades.copy()
                display = display.rename(
                    columns={
                        "trade_time": "Czas (UTC)",
                        "ticker_xtb": "Ticker XTB",
                        "ticker_yahoo": "Ticker Yahoo",
                        "side": "Strona",
                        "quantity": "Ilość",
                        "price": "Cena",
                        "amount": "Kwota (konto)",
                        "operation_type": "Typ operacji",
                        "comment": "Komentarz",
                    }
                )
                drop_cols = [c for c in display.columns if c in ("trade_date",)]
                display = display.drop(columns=drop_cols, errors="ignore")

                for col in ("Ilość", "Cena", "Kwota (konto)"):
                    if col in display.columns:
                        display[col] = display[col].map(
                            lambda x: round(x, 4) if pd.notna(x) else None
                        )

                st.dataframe(display, use_container_width=True, hide_index=True)

# --- Podatek Belki ---
with tab_tax:
    section_header(
        "Kalkulator podatku Belki (19%)",
        "NBP · WHT · przenoszenie strat · eksport PIT-38 (szacunek edukacyjny)",
    )

    if closed is None or closed.empty or "close_time" not in closed.columns:
        st.warning(
            "Brak arkusza **Closed Positions** w pliku. "
            "Pobierz pełny eksport Excel z platformy XTB."
        )
        selected_tax_year = pd.Timestamp.now().year
        belka = None
        net_income = 0.0
    else:
        tax_df = closed.copy()
        tax_df["close_dt"] = pd.to_datetime(tax_df["close_time"], errors="coerce")
        tax_df = tax_df.dropna(subset=["close_dt", "pnl"])
        tax_df["tax_year"] = tax_df["close_dt"].dt.year

        years = sorted(tax_df["tax_year"].unique().astype(int).tolist(), reverse=True)
        if not years:
            st.info("Brak zamkniętych pozycji z poprawną datą zamknięcia.")
            selected_tax_year = pd.Timestamp.now().year
            belka = None
            net_income = 0.0
        else:
            current_year = pd.Timestamp.now().year
            default_idx = years.index(current_year) if current_year in years else 0
            selected_tax_year = st.selectbox(
                "Rok podatkowy",
                years,
                index=default_idx,
                key="tax_year_filter",
            )

            with st.spinner("Przeliczanie Belki (kursy NBP + WHT)…"):
                belka = compute_belka_year(
                    closed,
                    report.cash_operations,
                    int(selected_tax_year),
                    report.account_currency or currency,
                )
            tax_ccy = belka.currency
            net_income = belka.capital_net

            fx_label = {
                "nbp": "kursy średnie NBP (data zamknięcia / wypłaty)",
                "mixed": "NBP + fallback (część wierszy bez kursu)",
                "account": "waluta konta (bez przeliczenia NBP)",
            }.get(belka.fx_method, belka.fx_method)
            st.caption(f"Przeliczenie: **{fx_label}** · wyniki w **{tax_ccy}**")

            t1, t2, t3, t4 = st.columns(4)
            with t1:
                st.metric("Zrealizowane zyski", format_currency(belka.capital_gains, tax_ccy))
            with t2:
                st.metric("Zrealizowane straty", format_currency(belka.capital_losses, tax_ccy))
            with t3:
                st.metric(
                    "Wynik netto",
                    format_currency(belka.capital_net, tax_ccy),
                    delta_color=pnl_delta_color(belka.capital_net),
                )
            with t4:
                st.metric(
                    "Podatek od zysków (po stratach z lat ub.)",
                    format_currency(belka.capital_tax, tax_ccy),
                    help=(
                        f"Podstawa {format_currency(belka.capital_base, tax_ccy)} "
                        f"po odjęciu {format_currency(belka.carry_applied, tax_ccy)} z ledżera."
                    ),
                )

            if belka.capital_net < 0:
                st.info(
                    f"Strata netto **{format_currency(belka.capital_net, tax_ccy)}** — "
                    "podatek od zysków = 0. Zapisz ją w ledżerze poniżej "
                    "(do 5 lat, max 50% danej straty rocznie)."
                )

            # Dywidendy + WHT
            st.divider()
            st.markdown("#### Dywidendy i podatek u źródła (WHT)")
            d1, d2, d3, d4 = st.columns(4)
            with d1:
                st.metric("Dywidendy brutto", format_currency(belka.dividends_gross, tax_ccy))
            with d2:
                st.metric("Belka 19% od dywidend", format_currency(belka.dividend_tax_gross, tax_ccy))
            with d3:
                st.metric(
                    "WHT (zagranica)",
                    format_currency(belka.withholding_tax, tax_ccy),
                    help="Suma |withholding| z Cash Operations, przeliczona NBP.",
                )
            with d4:
                st.metric(
                    "Dopłata Belki po WHT",
                    format_currency(belka.dividend_tax_after_wht, tax_ccy),
                )
            st.metric("Łączny szacunek Belki", format_currency(belka.total_tax, tax_ccy))
            st.caption(
                "Kredyt WHT nie może przekroczyć polskiego 19% od tych dywidend. "
                "Umowy o unikaniu podwójnego opodatkowania mogą zmieniać limit — to szacunek."
            )

            year_df = belka.closed_detail
            if year_df is not None and not year_df.empty:
                show = year_df[["ticker_xtb", "close_dt", "pnl_pln"]].copy()
                show["cumulative_pnl"] = show["pnl_pln"].cumsum()
                show["cumulative_tax"] = show["cumulative_pnl"].clip(lower=0) * 0.19
                show = show.rename(
                    columns={
                        "ticker_xtb": "Ticker",
                        "close_dt": "Data zamknięcia",
                        "pnl_pln": "PnL PLN",
                        "cumulative_pnl": "Skumulowany PnL",
                        "cumulative_tax": "Podatek narastający",
                    }
                )
                for col in ("PnL PLN", "Skumulowany PnL", "Podatek narastający"):
                    show[col] = show[col].round(2)
                st.dataframe(show, use_container_width=True, hide_index=True)

            # --- Przenoszenie strat ---
            st.divider()
            st.markdown("#### Przenoszenie strat (5 lat / max 50%)")
            st.caption(
                "Zapisz stratę netto z roku, w którym powstała. W kolejnych latach "
                "aplikacja pomniejszy dodatnią podstawę (max 50% danej straty rocznie)."
            )
            carry_entries = load_carry_entries()
            if belka.carry_applied > 0:
                st.success(
                    f"Zastosowano **{format_currency(belka.carry_applied, tax_ccy)}** "
                    f"strat z lat ubiegłych → podstawa **{format_currency(belka.capital_base, tax_ccy)}**."
                )
                if belka.carry and belka.carry.details:
                    st.dataframe(
                        pd.DataFrame(belka.carry.details),
                        use_container_width=True,
                        hide_index=True,
                    )

            with st.form("carry_loss_form"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    carry_year = st.number_input(
                        "Rok powstania straty",
                        min_value=2000,
                        max_value=2100,
                        value=int(selected_tax_year),
                        step=1,
                    )
                with c2:
                    default_loss = abs(min(0.0, belka.capital_net)) if int(carry_year) == int(selected_tax_year) else 0.0
                    carry_loss = st.number_input(
                        "Kwota straty (PLN, dodatnia)",
                        min_value=0.0,
                        value=float(round(default_loss, 2)),
                        step=100.0,
                    )
                with c3:
                    carry_note = st.text_input("Notatka", value="")
                save_carry = st.form_submit_button("Zapisz / nadpisz stratę w ledżerze")
                if save_carry:
                    if carry_loss <= 0:
                        st.error("Podaj dodatnią kwotę straty.")
                    else:
                        upsert_carry_loss(int(carry_year), float(carry_loss), carry_note)
                        st.success(f"Zapisano stratę {carry_loss:.2f} PLN z roku {int(carry_year)}.")
                        st.rerun()

            if carry_entries:
                led = pd.DataFrame(
                    [
                        {
                            "Rok": e.origin_year,
                            "Strata": round(e.original_loss, 2),
                            "Wykorzystano": round(e.used_so_far, 2),
                            "Pozostało": round(e.remaining, 2),
                            "Notatka": e.note,
                        }
                        for e in carry_entries
                    ]
                )
                st.dataframe(led, use_container_width=True, hide_index=True)
                del_year = st.selectbox(
                    "Usuń wpis z roku",
                    options=[e.origin_year for e in carry_entries],
                    key="carry_delete_year",
                )
                if st.button("Usuń wybrany wpis", key="carry_delete_btn"):
                    delete_carry_year(int(del_year))
                    st.rerun()

            # --- Eksport PIT-38 ---
            st.divider()
            st.markdown("#### Eksport pomocniczy PIT-38")
            st.caption(
                "Excel z podsumowaniem (zyski/straty, dywidendy, WHT, ledżer strat). "
                "To nie jest e-Deklaracja — tylko dane do ręcznego uzupełnienia."
            )
            try:
                pit_bytes = generate_pit38_excel_bytes(
                    report, int(selected_tax_year), summary=belka
                )
                st.download_button(
                    label="Pobierz Excel (PIT-38 helper)",
                    data=pit_bytes,
                    file_name=default_pit38_filename(int(selected_tax_year)),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="pit38_download",
                )
            except Pit38ExportError as exc:
                st.error(f"Nie udało się wygenerować eksportu: {exc}")
            except Exception as exc:
                st.error(f"Nie udało się wygenerować eksportu: {exc}")

            # --- Tax-loss harvesting ---
            st.divider()
            st.markdown("#### Tax-loss harvesting")
            st.caption(
                "Sprzedaż otwartych pozycji ze stratą **przed końcem roku** obniża podstawę "
                "opodatkowania zysków kapitałowych (Belka 19%). Strata nie pomniejsza dywidend."
            )

            current_year = pd.Timestamp.now().year
            if int(selected_tax_year) != current_year:
                st.info(
                    f"Wybrany rok podatkowy to **{selected_tax_year}**. Tax-loss harvesting "
                    f"ma sens dla **bieżącego roku ({current_year})** — przełącz rok wyżej."
                )

            analyzed_tlh = get_analyzed_open()
            if analyzed_tlh is None or analyzed_tlh.empty:
                st.info("Brak otwartych pozycji do analizy.")
            else:
                harvest = compute_tax_harvest(
                    analyzed_tlh, realized_gain_ytd=net_income, currency=tax_ccy
                )
                if not harvest.has_losers:
                    st.success(
                        "Brak otwartych pozycji ze stratą — nie ma czego realizować."
                    )
                else:
                    h1, h2, h3, h4 = st.columns(4)
                    with h1:
                        st.metric(
                            "Zrealizowany wynik (rok)",
                            format_currency(harvest.realized_gain_ytd, tax_ccy),
                            delta_color=pnl_delta_color(harvest.realized_gain_ytd),
                        )
                    with h2:
                        st.metric(
                            "Strata do zebrania",
                            format_currency(harvest.harvestable_loss, tax_ccy),
                            help="Suma niezrealizowanych strat na otwartych pozycjach.",
                        )
                    with h3:
                        st.metric(
                            "Oszczędność podatku (ten rok)",
                            format_currency(harvest.tax_saved, tax_ccy),
                            help="Spadek podatku Belki, jeśli zrealizujesz straty.",
                        )
                    with h4:
                        st.metric(
                            "Do przeniesienia (5 lat)",
                            format_currency(harvest.carry_forward, tax_ccy),
                            help="Nadwyżka straty ponad tegoroczne zyski — rozliczysz w kolejnych latach.",
                        )

                    if harvest.tax_saved <= 0 and harvest.realized_gain_ytd <= 0:
                        st.caption(
                            "W tym roku nie masz zysków do skompensowania, ale zrealizowana "
                            "strata przejdzie na kolejne lata (max 50% rocznie przez 5 lat)."
                        )

                    cand = harvest.losers.copy()
                    cand["market_value"] = cand["market_value"].round(2)
                    cand["loss"] = cand["loss"].round(2)
                    cand["roi_pct"] = cand["roi_pct"].round(1)
                    cand["tax_shield"] = cand["tax_shield"].round(2)
                    st.dataframe(
                        cand.rename(
                            columns={
                                "ticker_xtb": "Ticker",
                                "market_value": f"Wartość ({tax_ccy})",
                                "loss": f"Strata ({tax_ccy})",
                                "roi_pct": "ROI %",
                                "tax_shield": f"Tarcza podatkowa ({tax_ccy})",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        "„Tarcza podatkowa” = realne zmniejszenie tegorocznego podatku z danej "
                        "pozycji (do wysokości tegorocznych zysków). Po sprzedaży uważaj na "
                        "natychmiastowy odkup tych samych walorów oraz na koszty prowizji/spreadu."
                    )

            st.caption(
                "To jest szacunek edukacyjny. Skonsultuj z doradcą podatkowym. "
                "NBP / WHT / ledżer strat upraszczają rozliczenie — nie zastępują PIT-38."
            )

    # --- IKE / IKZE (nie wymaga Closed Positions) ---
    st.divider()
    with st.expander("IKE / IKZE — optymalizacja podatkowa", expanded=False):
        st.markdown(
            "Kalkulator ile realnie zyskujesz, trzymając inwestycje na koncie emerytalnym "
            "zamiast na zwykłym. Przy tej samej rocznej wpłacie i stopie zwrotu porównujemy "
            "**zwykłe / IKE / IKZE** na zadanym horyzoncie."
        )
        st.caption(
            "**IKE** — brak Belki (19%) przy wypłacie po 60. r.ż. · "
            "**IKZE** — wpłata odliczana od PIT (natychmiastowy zwrot = wpłata × stawka); "
            "przy wypłacie po 65. r.ż. ryczałt 10% od całości. Zwroty PIT reinwestujemy "
            "na zwykłym (Belka od ich zysków)."
        )

        lim1, lim2, lim3 = st.columns(3)
        with lim1:
            ike_limit = st.number_input(
                "Limit IKE (zł/rok)",
                min_value=0.0,
                value=float(IKE_LIMIT_2025),
                step=100.0,
                key="ike_limit",
                help="Domyślnie limit 2025. Zmienia się co rok — sprawdź aktualną wartość.",
            )
        with lim2:
            ikze_limit_std = st.number_input(
                "Limit IKZE (zł/rok)",
                min_value=0.0,
                value=float(IKZE_LIMIT_2025),
                step=100.0,
                key="ikze_limit",
                help="Limit standardowy 2025. Dla działalności — przełącz poniżej.",
            )
        with lim3:
            use_biz_limit = st.checkbox(
                "IKZE — działalność (1,5×)",
                value=False,
                key="ikze_biz",
                help=f"Limit dla prowadzących działalność: {IKZE_LIMIT_BIZ_2025:,.0f} zł (2025).",
            )
        ikze_limit = float(IKZE_LIMIT_BIZ_2025) if use_biz_limit else float(ikze_limit_std)
        if use_biz_limit:
            st.caption(f"Stosowany limit IKZE (działalność): **{ikze_limit:,.0f} zł**.")

        i1, i2, i3, i4 = st.columns(4)
        with i1:
            ike_contrib = st.number_input(
                "Roczna wpłata (zł)",
                min_value=0.0,
                value=min(10_000.0, float(IKE_LIMIT_2025)),
                step=500.0,
                key="ike_contrib",
            )
        with i2:
            ike_years = st.number_input(
                "Lata do emerytury",
                min_value=1,
                max_value=50,
                value=25,
                step=1,
                key="ike_years",
            )
        with i3:
            ike_return = st.number_input(
                "Roczny zwrot (%)",
                min_value=-10.0,
                max_value=30.0,
                value=7.0,
                step=0.5,
                key="ike_return",
            )
        with i4:
            pit_label = st.selectbox(
                "Stawka PIT (IKZE)",
                options=list(PIT_RATES.keys()),
                index=0,
                key="ike_pit",
            )
        pit_rate = PIT_RATES[pit_label]

        cmp = compare_accounts(
            annual_contribution=float(ike_contrib),
            years=int(ike_years),
            annual_return_pct=float(ike_return),
            pit_rate=pit_rate,
            ike_limit=float(ike_limit),
            ikze_limit=ikze_limit,
        )
        pln = "PLN"

        if cmp.ike.capped or cmp.ikze.capped:
            bits = []
            if cmp.ike.capped:
                bits.append(f"IKE → {cmp.ike.annual_contribution:,.0f} zł")
            if cmp.ikze.capped:
                bits.append(f"IKZE → {cmp.ikze.annual_contribution:,.0f} zł")
            st.info(
                "Wpłata przekracza limit — na koncie emerytalnym liczymy uciętą kwotę: "
                + ", ".join(bits)
                + ". Zwykłe konto przyjmuje pełną wpłatę."
            )

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric(
                "Zwykłe — netto",
                format_currency(cmp.taxable.net_value, pln),
                help=(
                    f"Wpłacono {format_currency(cmp.taxable.total_contributed, pln)}, "
                    f"Belka {format_currency(cmp.taxable.exit_tax, pln)}."
                ),
            )
        with m2:
            st.metric(
                "IKE — netto",
                format_currency(cmp.ike.net_value, pln),
                delta=f"+{format_currency(cmp.ike.tax_saved_vs_taxable, pln)} vs Belka",
                help=(
                    "Bez Belki przy wypłacie po 60. r.ż. Delta = oszczędność vs ta sama "
                    "wpłata na zwykłym."
                ),
            )
        with m3:
            st.metric(
                "IKZE — netto",
                format_currency(cmp.ikze.net_value, pln),
                delta=f"+{format_currency(cmp.ikze.tax_saved_vs_taxable, pln)} vs Belka",
                help=(
                    f"Ryczałt 10% = {format_currency(cmp.ikze.exit_tax, pln)}; "
                    f"zwroty PIT reinwestowane netto = "
                    f"{format_currency(cmp.ikze.side_pocket_net, pln)}."
                ),
            )

        if cmp.ikze.immediate_refund_annual > 0:
            st.caption(
                f"Natychmiastowy zwrot PIT z IKZE: "
                f"**{format_currency(cmp.ikze.immediate_refund_annual, pln)}/rok** "
                f"({pit_label}) — w modelu reinwestowany na zwykłym koncie."
            )

        best = max(
            (cmp.taxable.net_value, "Zwykłe"),
            (cmp.ike.net_value, "IKE"),
            (cmp.ikze.net_value, "IKZE"),
            key=lambda x: x[0],
        )
        if best[0] > 0:
            st.success(
                f"Na tym horyzoncie najwyższa wartość netto: **{best[1]}** "
                f"({format_currency(best[0], pln)})."
            )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                build_ike_ikze_comparison_chart(cmp.trajectory, pln),
                use_container_width=True,
            )
        with c2:
            st.plotly_chart(
                build_ike_ikze_bars_chart(
                    cmp.taxable.net_value,
                    cmp.ike.net_value,
                    cmp.ikze.net_value,
                    pln,
                ),
                use_container_width=True,
            )

        st.caption(
            "⚠️ Limity IKE/IKZE zmieniają się co rok — wartości domyślne to **2025**. "
            "Model zakłada wypłatę całości na końcu horyzontu przy spełnieniu warunków "
            "wiekowych. To szacunek edukacyjny, nie porada podatkowa."
        )

# --- Kalendarz (dywidendy + wyniki) ---
with tab_calendar:
    tab_div, tab_earn = st.tabs(["Dywidendy", "Wyniki"])

    with tab_div:
        section_header("Dywidendy", "Historia wypłat, yield i projekcja cashflow")

        if report.cash_operations is None:
            st.warning("Wymagany natywny eksport Excel z arkuszem Cash Operations.")
        else:
            dividends = parse_dividends(report.cash_operations)
            if dividends.empty:
                st.info(
                    "Brak historycznych wypłat dywidend w okresie eksportu — "
                    "poniżej znajdziesz prognozę forward dla otwartych pozycji."
                )
            else:
                current_year = pd.Timestamp.now().year
                stats = dividends_summary(dividends, current_year=current_year)

                d1, d2, d3, d4 = st.columns(4)
                with d1:
                    st.metric("Łączne dywidendy", format_currency(stats["total"], currency))
                with d2:
                    st.metric(
                        f"W roku {current_year}",
                        format_currency(stats["current_year"], currency),
                    )
                with d3:
                    st.metric("Liczba wypłat", stats["count"])
                with d4:
                    st.metric("Śr. na wypłatę", format_currency(stats["avg"], currency))

                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(
                        build_dividends_per_year_chart(
                            dividends_per_year(dividends), currency
                        ),
                        use_container_width=True,
                    )
                with c2:
                    st.plotly_chart(
                        build_cumulative_dividends_chart(dividends, currency),
                        use_container_width=True,
                    )

                st.markdown("#### Dywidendy per ticker")
                per_ticker = dividends_per_ticker(dividends)
                if not per_ticker.empty:
                    show_pt = per_ticker.rename(
                        columns={
                            "ticker_xtb": "Ticker",
                            "total": "Suma",
                            "payouts": "Liczba wypłat",
                            "last_date": "Ostatnia wypłata",
                        }
                    )
                    show_pt["Suma"] = show_pt["Suma"].round(2)
                    st.dataframe(show_pt, use_container_width=True, hide_index=True)

                with st.expander("Wszystkie wypłaty (surowe dane)"):
                    show_raw = dividends.rename(
                        columns={
                            "date": "Data",
                            "year": "Rok",
                            "ticker_xtb": "Ticker",
                            "amount": "Kwota",
                            "comment": "Komentarz",
                        }
                    )
                    show_raw["Kwota"] = show_raw["Kwota"].round(2)
                    st.dataframe(show_raw, use_container_width=True, hide_index=True)

            # Forward kalendarz — zawsze, niezależnie od historii wypłat.
            st.divider()
            st.markdown("#### Kalendarz ex-date i forward yield")
            st.caption(
                "Prognozowana stopa dywidendy i najbliższe daty odcięcia (ex-date) dla "
                "obecnie otwartych pozycji — dane z Yahoo Finance `.info`."
            )
            analyzed_div = get_analyzed_open()
            if analyzed_div is None or analyzed_div.empty:
                st.info("Brak otwartych pozycji do prognozy dywidend.")
            else:
                with st.spinner("Pobieranie danych dywidendowych…"):
                    cal, cal_summary = build_dividend_calendar(analyzed_div, currency)

                if cal.empty:
                    st.info(
                        "Żadna z otwartych pozycji nie wypłaca dywidend (lub Yahoo nie podaje "
                        "stopy). Spółki wzrostowe i część ETF-ów akumulacyjnych nie płacą dywidend."
                    )
                else:
                    fc1, fc2, fc3 = st.columns(3)
                    with fc1:
                        st.metric(
                            "Szac. roczny przychód",
                            format_currency(cal_summary["annual_income"], currency),
                            help="Wartość pozycji × forward yield (suma po pozycjach).",
                        )
                    with fc2:
                        st.metric(
                            "Forward yield portfela",
                            f"{cal_summary['portfolio_yield_pct']:.2f}%",
                        )
                    with fc3:
                        st.metric("Pozycje płacące", cal_summary["paying_positions"])

                    cal_show = cal.copy()
                    cal_show["yield_pct"] = cal_show["yield_pct"].round(2)
                    cal_show["annual_income"] = cal_show["annual_income"].round(2)
                    cal_show["ex_date"] = cal_show["ex_date"].apply(
                        lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else "—"
                    )
                    cal_show["ex_upcoming"] = cal_show["ex_upcoming"].map(
                        {True: "🟢 nadchodzi", False: "⚪ minęła/szac."}
                    )
                    cal_show["rate_per_share"] = cal_show["rate_per_share"].apply(
                        lambda v: round(v, 4) if pd.notna(v) else None
                    )
                    st.dataframe(
                        cal_show[
                            [
                                "ticker_xtb",
                                "yield_pct",
                                "ex_date",
                                "ex_upcoming",
                                "annual_income",
                                "rate_per_share",
                            ]
                        ].rename(
                            columns={
                                "ticker_xtb": "Ticker",
                                "yield_pct": "Yield %",
                                "ex_date": "Ex-date",
                                "ex_upcoming": "Status",
                                "annual_income": f"Szac. rocznie ({currency})",
                                "rate_per_share": "Na akcję",
                            }
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        "ℹ️ Forward yield to prognoza na bazie ostatniej dywidendy — rzeczywiste "
                        "wypłaty mogą się różnić. Ex-date z przeszłości to wartość orientacyjna."
                    )

                    yield_cmp = build_dividend_yield_comparison(analyzed_div, currency)
                    if not yield_cmp.empty:
                        st.markdown("#### Yield on cost vs forward yield")
                        st.caption(
                            "Yield on cost = roczna dywidenda / koszt pozycji. "
                            "Forward yield = prognoza Yahoo na bazie bieżącej ceny."
                        )
                        st.plotly_chart(
                            build_dividend_yield_comparison_chart(yield_cmp),
                            use_container_width=True,
                        )

                    st.markdown("#### Widok kalendarza ex-dividend")
                    cal_months = sorted(
                        {
                            pd.Timestamp(d).strftime("%Y-%m")
                            for d in cal["ex_date"].dropna()
                        }
                    )
                    if not cal_months:
                        cal_months = [pd.Timestamp.now().strftime("%Y-%m")]
                    selected_month = st.selectbox(
                        "Miesiąc",
                        cal_months,
                        index=len(cal_months) - 1,
                        key="ex_div_month",
                    )
                    st.plotly_chart(
                        build_ex_dividend_calendar_chart(
                            cal, pd.Timestamp(f"{selected_month}-01")
                        ),
                        use_container_width=True,
                    )

                    projected_12m, _projected_summary = build_projected_dividend_cashflow_12m(
                        analyzed_div, currency
                    )
                    if not projected_12m.empty:
                        st.markdown("#### Projected cashflow 12M (miesięcznie)")
                        st.metric(
                            "Suma projekcji 12M",
                            format_currency(
                                float(projected_12m["projected_income"].sum()), currency
                            ),
                        )
                        st.plotly_chart(
                            build_projected_dividend_cashflow_chart(
                                projected_12m, currency
                            ),
                            use_container_width=True,
                        )

                    growth_df = build_dividend_growth_tracker(analyzed_div)
                    if not growth_df.empty:
                        st.markdown("#### Dividend growth tracker")
                        st.plotly_chart(
                            build_dividend_growth_tracker_chart(growth_df),
                            use_container_width=True,
                        )
                        growth_show = growth_df.rename(
                            columns={
                                "ticker_yahoo": "Ticker",
                                "current_rate": "Current rate",
                                "previous_rate": "Previous rate",
                                "growth_pct": "Growth %",
                                "status": "Status",
                            }
                        ).copy()
                        growth_show["Growth %"] = growth_show["Growth %"].round(2)
                        st.dataframe(
                            growth_show, use_container_width=True, hide_index=True
                        )

    with tab_earn:
        section_header("Kalendarz wyników (earnings)")
        st.caption(
            "Nadchodzące daty publikacji wyników kwartalnych dla otwartych pozycji — "
            "dane z Yahoo Finance `Ticker.calendar` (cache 24h)."
        )
        st.info(
            "⚠️ Wokół raportów wyniki bywają bardzo zmienne: duże ruchy dzienne i luki "
            "cenowe to norma. Traktuj ten kalendarz jako ostrzeżenie przed zmiennością, "
            "nie jako rekomendację."
        )

        analyzed_earn = get_analyzed_open()
        if analyzed_earn is None or analyzed_earn.empty:
            st.info("Brak otwartych pozycji do kalendarza wyników.")
        else:
            with st.spinner("Pobieranie dat wyników…"):
                earn, earn_summary = build_earnings_calendar(analyzed_earn)

            e1, e2, e3, e4 = st.columns(4)
            with e1:
                st.metric("Z datą raportu", earn_summary["with_date"])
            with e2:
                st.metric("W ciągu 7 dni", earn_summary["within_7d"])
            with e3:
                st.metric("W ciągu 14 dni", earn_summary["within_14d"])
            with e4:
                st.metric(
                    "Bez daty / ETF",
                    earn_summary["missing"],
                    help="Yahoo często nie podaje earnings dla ETF-ów i części zagranicznych.",
                )

            if earn.empty:
                st.info(
                    "Brak nadchodzących dat wyników dla otwartych pozycji. "
                    "ETF-y i część spółek zagranicznych mogą nie mieć danych w Yahoo."
                )
            else:
                urgency_label = {
                    "7d": "🔴 ≤7 dni",
                    "14d": "🟡 ≤14 dni",
                    "later": "⚪ dalej",
                }
                earn_show = earn.copy()
                earn_show["earnings_date"] = earn_show["earnings_date"].dt.strftime(
                    "%Y-%m-%d"
                )
                earn_show["eps_estimate"] = earn_show["eps_estimate"].apply(
                    lambda v: round(v, 3) if pd.notna(v) else None
                )
                earn_show["urgency"] = earn_show["urgency"].map(urgency_label)

                def _earn_row_style(row: pd.Series) -> list[str]:
                    label = str(row.get("Okno", ""))
                    if "≤7" in label:
                        color = "background-color: rgba(220, 53, 69, 0.18)"
                    elif "≤14" in label:
                        color = "background-color: rgba(255, 193, 7, 0.22)"
                    else:
                        color = ""
                    return [color] * len(row)

                display_earn = earn_show[
                    [
                        "ticker_xtb",
                        "earnings_date",
                        "days_until",
                        "eps_estimate",
                        "urgency",
                    ]
                ].rename(
                    columns={
                        "ticker_xtb": "Ticker",
                        "earnings_date": "Data raportu",
                        "days_until": "Dni do raportu",
                        "eps_estimate": "Prognoza EPS",
                        "urgency": "Okno",
                    }
                )
                try:
                    styled = display_earn.style.apply(_earn_row_style, axis=1)
                    st.dataframe(styled, use_container_width=True, hide_index=True)
                except Exception:
                    st.dataframe(display_earn, use_container_width=True, hide_index=True)

                st.caption(
                    "ℹ️ Prognoza EPS = konsensus analityków (`Earnings Average` z Yahoo). "
                    "Daty bywają oknem — pokazujemy najwcześniejszy dzień. Brak wiersza = "
                    "Yahoo nie zwróciło daty (częste dla ETF-ów)."
                )
