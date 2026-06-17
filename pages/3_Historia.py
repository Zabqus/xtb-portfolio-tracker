"""
Podstrona: historia transakcji, zamknięte pozycje, timeline portfela.
"""

import pandas as pd
import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from core.closed_analysis import closed_positions_summary, get_top_trades
from core.cost_basis import get_current_cost_basis
from core.dividends import (
    dividends_per_ticker,
    dividends_per_year,
    dividends_summary,
    parse_dividends,
)
from core.session import (
    get_cost_basis_history,
    get_display_currency,
    get_portfolio_timeline,
    get_report,
    get_trade_analytics,
)
from core.transactions import parse_cash_operations_trades
from ui.analytics_charts import (
    build_cost_basis_chart,
    build_holding_period_chart,
    build_round_trip_pnl_chart,
    build_win_loss_comparison,
)
from ui.charts import build_closed_pnl_chart
from ui.formatters import format_currency, pnl_delta_color
from ui.history_charts import (
    build_contributions_vs_value_chart,
    build_cumulative_dividends_chart,
    build_cumulative_realized_pnl,
    build_dividends_per_year_chart,
    build_portfolio_timeline_chart,
)
from ui.sidebar import render_import_sidebar
from ui.tables import render_closed_positions_table, render_round_trips_table

st.title("📜 Historia i zamknięte pozycje")

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
    tab_trades,
    tab_tax,
    tab_dividends,
) = st.tabs(
    [
        "Timeline portfela",
        "Trade Analytics",
        "Zamknięte pozycje",
        "Historia transakcji",
        "💰 Podatek Belki",
        "💵 Dywidendy",
    ]
)

# --- Timeline ---
with tab_timeline:
    st.subheader("Wartość portfela w czasie")
    st.caption(
        "Rekonstrukcja z arkusza **Cash Operations**: dzienne saldo pozycji "
        "wycenione kursem zamknięcia Yahoo (auto_adjust)."
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

            st.markdown("#### Wpłaty vs wartość rynkowa")
            st.plotly_chart(
                build_contributions_vs_value_chart(
                    timeline, report.cash_operations, currency
                ),
                use_container_width=True,
            )
            st.caption(
                "Zielony obszar powyżej niebieskiej linii = Twój zysk rynkowy. "
                "Obszar poniżej = strata względem wpłaconych środków."
            )

# --- Trade Analytics ---
with tab_analytics:
    st.subheader("Statystyki tradingowe")

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

            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(
                    build_win_loss_comparison(summary.avg_win, summary.avg_loss, currency),
                    use_container_width=True,
                )
            with c2:
                if has_round_trips:
                    st.plotly_chart(
                        build_holding_period_chart(round_trips),
                        use_container_width=True,
                    )

            if has_round_trips:
                st.plotly_chart(
                    build_round_trip_pnl_chart(round_trips),
                    use_container_width=True,
                )

                st.markdown("### Round-tripy (FIFO z Cash Operations)")
                st.caption(
                    f"**{len(round_trips)} wierszy** = tyle zamkniętych fragmentów pozycji "
                    "(każdy wiersz to jedno dopasowanie kupno → sprzedaż). "
                    "To **jedna tabela**, nie wiele kopii. "
                    "Różni się od zakładki *Zamknięte pozycje* (raport XTB, inny podział transakcji)."
                )
                render_round_trips_table(round_trips)

        st.divider()
        st.subheader("Cost basis — historia średniej ceny")

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

# --- Zamknięte pozycje ---
with tab_closed:
    st.subheader("Zrealizowane zyski i straty")
    st.caption(
        "Dane z arkusza **Closed Positions** w eksporcie XTB (widok brokera). "
        "Do analizy FIFO z historii transakcji użyj zakładki **Trade Analytics**."
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
                style_metric_cards(
                    background_color="#1e1e2e",
                    border_left_color="#4a9eff",
                    border_color="#2d2d3f",
                    box_shadow="rgba(0,0,0,0.2)",
                )
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

            st.subheader("Wszystkie zamknięte pozycje (XTB)")
            render_closed_positions_table(closed_filtered.drop(columns=["close_year"]))

# --- Historia transakcji ---
with tab_trades:
    st.subheader("Historia transakcji (Cash Operations)")

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
    st.subheader("Kalkulator podatku Belki (19%)")
    st.caption(
        "Szacunek na podstawie zrealizowanych zysków/strat z arkusza **Closed Positions** "
        "oraz dywidend z **Cash Operations**."
    )

    if closed is None or closed.empty or "close_time" not in closed.columns:
        st.warning(
            "Brak arkusza **Closed Positions** w pliku. "
            "Pobierz pełny eksport Excel z platformy XTB."
        )
    else:
        tax_df = closed.copy()
        tax_df["close_dt"] = pd.to_datetime(tax_df["close_time"], errors="coerce")
        tax_df = tax_df.dropna(subset=["close_dt", "pnl"])
        tax_df["tax_year"] = tax_df["close_dt"].dt.year

        years = sorted(tax_df["tax_year"].unique().astype(int).tolist(), reverse=True)
        if not years:
            st.info("Brak zamkniętych pozycji z poprawną datą zamknięcia.")
        else:
            current_year = pd.Timestamp.now().year
            default_idx = years.index(current_year) if current_year in years else 0
            selected_tax_year = st.selectbox(
                "Rok podatkowy",
                years,
                index=default_idx,
                key="tax_year_filter",
            )

            year_df = tax_df[tax_df["tax_year"] == int(selected_tax_year)].copy()
            year_df = year_df.sort_values("close_dt")

            total_gain = float(year_df.loc[year_df["pnl"] > 0, "pnl"].sum())
            total_loss = float(year_df.loc[year_df["pnl"] < 0, "pnl"].sum())
            net_income = total_gain + total_loss
            tax_due = max(0.0, net_income * 0.19)

            t1, t2, t3, t4 = st.columns(4)
            with t1:
                st.metric("Zrealizowane zyski", format_currency(total_gain, currency))
            with t2:
                st.metric("Zrealizowane straty", format_currency(total_loss, currency))
            with t3:
                st.metric(
                    "Podstawa opodatkowania",
                    format_currency(net_income, currency),
                    delta_color=pnl_delta_color(net_income),
                )
            with t4:
                st.metric("Szacunkowy podatek (19%)", format_currency(tax_due, currency))

            if net_income < 0:
                st.info(
                    f"Strata netto **{format_currency(net_income, currency)}** — "
                    "podatek = 0. Stratę można rozliczyć w kolejnych latach "
                    "(do 5 lat, max 50% rocznie)."
                )

            # Dywidendy w danym roku
            if report.cash_operations is not None:
                div_all = parse_dividends(report.cash_operations)
                if not div_all.empty:
                    div_year = div_all[div_all["year"] == int(selected_tax_year)]
                    total_dividends = float(div_year["amount"].sum())
                    if total_dividends != 0:
                        tax_on_dividends = total_dividends * 0.19
                        st.divider()
                        d1, d2 = st.columns(2)
                        with d1:
                            st.metric(
                                "Dywidendy (rok)",
                                format_currency(total_dividends, currency),
                            )
                        with d2:
                            st.metric(
                                "Podatek od dywidend (19%)",
                                format_currency(tax_on_dividends, currency),
                            )
                        st.caption(
                            "ℹ️ Dywidendy zagraniczne mogą być już częściowo opodatkowane "
                            "u źródła (withholding tax). Faktyczna dopłata w PL może być niższa."
                        )

            # Tabela narastająca
            if not year_df.empty:
                show = year_df[["ticker_xtb", "close_dt", "pnl"]].copy()
                show["cumulative_pnl"] = show["pnl"].cumsum()
                show["cumulative_tax"] = show["cumulative_pnl"].clip(lower=0) * 0.19
                show = show.rename(
                    columns={
                        "ticker_xtb": "Ticker",
                        "close_dt": "Data zamknięcia",
                        "pnl": "PnL",
                        "cumulative_pnl": "Skumulowany PnL",
                        "cumulative_tax": "Podatek narastający",
                    }
                )
                for col in ("PnL", "Skumulowany PnL", "Podatek narastający"):
                    show[col] = show[col].round(2)
                st.dataframe(show, use_container_width=True, hide_index=True)

            st.caption(
                "⚠️ To jest szacunek edukacyjny. Skonsultuj z doradcą podatkowym. "
                "Nie uwzględnia podatku u źródła, ulg ani umów o unikaniu podwójnego "
                "opodatkowania."
            )

# --- Dywidendy ---
with tab_dividends:
    st.subheader("Dywidendy")

    if report.cash_operations is None:
        st.warning("Wymagany natywny eksport Excel z arkuszem Cash Operations.")
    else:
        dividends = parse_dividends(report.cash_operations)
        if dividends.empty:
            st.info("Brak operacji dywidendowych w wybranym okresie eksportu.")
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
                    build_dividends_per_year_chart(dividends_per_year(dividends), currency),
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
