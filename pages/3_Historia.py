"""
Podstrona: historia transakcji, zamknięte pozycje, timeline portfela.
"""

import pandas as pd
import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

from core.closed_analysis import closed_positions_summary, get_top_trades
from core.session import get_portfolio_timeline, get_report
from core.transactions import parse_cash_operations_trades
from ui.charts import build_closed_pnl_chart
from ui.formatters import format_currency, pnl_delta_color
from ui.history_charts import build_cumulative_realized_pnl, build_portfolio_timeline_chart
from ui.sidebar import render_import_sidebar
from ui.tables import render_closed_positions_table

st.title("📜 Historia i zamknięte pozycje")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

report = get_report()
if report is None:
    st.stop()

currency = report.account_currency
closed = report.closed_positions

tab_timeline, tab_closed, tab_trades = st.tabs(
    ["Timeline portfela", "Zamknięte pozycje", "Historia transakcji"]
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

# --- Zamknięte pozycje ---
with tab_closed:
    st.subheader("Zrealizowane zyski i straty")

    if closed is None or closed.empty:
        st.warning(
            "Brak arkusza **Closed Positions** w pliku. "
            "Pobierz pełny eksport Excel z platformy XTB."
        )
    else:
        stats = closed_positions_summary(closed)

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
            build_cumulative_realized_pnl(closed, currency),
            use_container_width=True,
        )
        st.plotly_chart(
            build_closed_pnl_chart(closed, currency),
            use_container_width=True,
        )

        best, worst = get_top_trades(closed, n=5)
        bcol, wcol = st.columns(2)

        def _trade_display(df: pd.DataFrame) -> pd.DataFrame:
            show = df[["ticker_xtb", "instrument", "pnl", "close_time"]].copy()
            if "purchase_value" in df.columns:
                pv = df["purchase_value"].replace(0, pd.NA)
                show["ROI %"] = (df["pnl"] / pv * 100).round(1)
            show["pnl"] = show["pnl"].round(2)
            return show

        with bcol:
            st.markdown("### 🏆 Najlepsze transakcje")
            if best.empty:
                st.caption("—")
            else:
                st.dataframe(_trade_display(best), use_container_width=True, hide_index=True)

        with wcol:
            st.markdown("### 📉 Najgorsze transakcje")
            if worst.empty:
                st.caption("—")
            else:
                st.dataframe(_trade_display(worst), use_container_width=True, hide_index=True)

        st.subheader("Wszystkie zamknięte pozycje")
        render_closed_positions_table(closed)

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
