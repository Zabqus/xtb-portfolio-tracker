"""
Podstrona: głęboka analiza pojedynczej pozycji (wykres, fundamenty, benchmark, timing).
"""

import pandas as pd
import streamlit as st

from core.analyzer import portfolio_summary
from core.benchmark import build_performance_comparison, resolve_benchmark
from core.analyst_consensus import fetch_analyst_consensus
from core.fundamentals import fetch_fundamentals, format_market_cap
from core.fx_decomposition import compute_fx_decomposition, summarize_fx_decomposition
from core.range_52w import range_position_52w
from ui.analyst_consensus import render_analyst_consensus
from core.history import PERIOD_OPTIONS, fetch_price_history
from core.timing_score import compute_timing_score
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_position_row,
    get_report,
    get_selected_ticker,
    set_selected_ticker,
)
from core.transactions import parse_cash_operations_trades
from ui.formatters import format_currency, pnl_delta_color
from ui.fx_charts import build_fx_waterfall_chart
from ui.position_charts import (
    build_benchmark_overlay_chart,
    build_price_drawdown_chart,
    build_price_volume_chart,
    build_timing_gauge,
)
from ui.sidebar import render_import_sidebar
from ui.theme import bootstrap_page

bootstrap_page()
st.title("🔍 Analiza pozycji")

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

analyzed = get_analyzed_open()
if analyzed is None:
    st.stop()

tickers = analyzed["ticker_xtb"].tolist()
preselect = get_selected_ticker()
default_idx = tickers.index(preselect) if preselect in tickers else 0

selected = st.selectbox(
    "Wybierz instrument",
    tickers,
    index=default_idx,
    format_func=lambda t: f"{t}  →  {analyzed.loc[analyzed['ticker_xtb'] == t, 'ticker_yahoo'].iloc[0]}",
)
set_selected_ticker(selected)

# Nawigacja ← → między pozycjami
current_idx = tickers.index(selected) if selected in tickers else 0

nav_l, nav_info, nav_r = st.columns([1, 4, 1])
with nav_l:
    if st.button("← Poprzedni", disabled=(current_idx == 0), use_container_width=True):
        set_selected_ticker(tickers[current_idx - 1])
        st.rerun()
with nav_info:
    st.caption(f"Pozycja {current_idx + 1} z {len(tickers)}")
with nav_r:
    if st.button("Następny →", disabled=(current_idx == len(tickers) - 1), use_container_width=True):
        set_selected_ticker(tickers[current_idx + 1])
        st.rerun()

row = get_position_row(selected)
if row is None:
    st.error("Nie znaleziono pozycji.")
    st.stop()

yahoo = row["ticker_yahoo"]
avg_price = float(row["avg_price"])
quantity = float(row["quantity"])
currency = row["currency"]
pnl = row.get("pnl")
roi = row.get("roi_pct")
market_value = row.get("market_value")

portfolio_total = float(portfolio_summary(analyzed)["total_value"])
pnl_portfolio_pct = None
weight_pct = None
if portfolio_total > 0:
    if pnl is not None and pnl == pnl:
        pnl_portfolio_pct = float(pnl) / portfolio_total * 100.0
    if market_value is not None and market_value == market_value:
        weight_pct = float(market_value) / portfolio_total * 100.0

st.caption(f"Yahoo: **{yahoo}** · Waluta notowań: **{currency}**")

# --- Nagłówek metryk pozycji ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Ilość", f"{quantity:,.4f}")
with m2:
    st.metric("Śr. cena zakupu", f"{avg_price:,.4f} {currency}")
with m3:
    if pnl is not None and not (isinstance(pnl, float) and pnl != pnl):
        pnl_label = format_currency(float(pnl), get_display_currency())
        if pnl_portfolio_pct is not None:
            pnl_label = f"{pnl_label} ({pnl_portfolio_pct:+.2f}% portfela)"
        st.metric(
            "Zysk / strata",
            pnl_label,
            delta=f"{roi:.2f}%" if roi == roi else None,
            delta_color=pnl_delta_color(float(pnl)),
        )
with m4:
    bench_name, _ = resolve_benchmark(selected, currency)
    if weight_pct is not None:
        st.metric("Benchmark", bench_name, delta=f"{weight_pct:.1f}% portfela")
    else:
        st.metric("Benchmark", bench_name)

# --- Dekompozycja FX dla pozycji w obcej walucie ---
display_ccy = get_display_currency()
if str(currency).upper() != str(display_ccy).upper():
    report_pos = get_report()
    trades_pos = None
    if (
        report_pos is not None
        and report_pos.cash_operations is not None
        and not report_pos.cash_operations.empty
    ):
        trades_pos = parse_cash_operations_trades(report_pos.cash_operations)
    pos_mask = analyzed["ticker_xtb"] == selected
    pos_slice = analyzed.loc[pos_mask].copy()
    pos_slice.attrs["display_currency"] = analyzed.attrs.get("display_currency", display_ccy)
    pos_slice.attrs["fx_rates"] = analyzed.attrs.get("fx_rates", {})
    pos_fx = compute_fx_decomposition(
        pos_slice,
        trades=trades_pos,
        account_currency=report_pos.account_currency if report_pos else "EUR",
    )
    if not pos_fx.empty and pd.notna(pos_fx.iloc[0].get("pnl_price")):
        rfx = pos_fx.iloc[0]
        with st.expander("💱 Dekompozycja FX tej pozycji", expanded=True):
            x1, x2, x3, x4 = st.columns(4)
            with x1:
                st.metric("Z ceny", format_currency(float(rfx["pnl_price"]), display_ccy))
            with x2:
                st.metric("Z waluty", format_currency(float(rfx["pnl_fx"]), display_ccy))
            with x3:
                st.metric("PnL łącznie", format_currency(float(rfx["pnl_fx_total"]), display_ccy))
            with x4:
                rate = rfx.get("fx_rate_purchase")
                st.metric(
                    "Kurs zakupu",
                    f"{float(rate):.4f}" if pd.notna(rate) else "—",
                    help=f"1 {currency} → {display_ccy} (szacowany)",
                )
            fx_one = summarize_fx_decomposition(pos_fx)
            st.plotly_chart(build_fx_waterfall_chart(fx_one), use_container_width=True)
            src = str(rfx.get("fx_rate_source", ""))
            if src == "trades":
                st.caption(
                    "Ile z PnL pochodzi z ruchu ceny spółki, a ile z kursu waluty — "
                    "kurs zakupu z Cash Operations (Amount)."
                )
            else:
                st.caption(
                    "Kurs zakupu z analyzera (position_cost / cost_native). "
                    "Przy natywnym eksporcie XTB z Amount efekt FX jest dokładniejszy."
                )

period_label = st.radio(
    "Horyzont czasowy",
    list(PERIOD_OPTIONS.keys()),
    horizontal=True,
    key="position_period",
)

tab_chart, tab_fund, tab_bench, tab_timing = st.tabs(
    ["Wykres i wolumen", "Fundamenty", "vs Benchmark", "Timing wejścia"]
)

with tab_chart:
    with st.spinner("Pobieranie historii notowań…"):
        history = fetch_price_history(yahoo, period_label)

    if history.empty:
        st.error(f"Brak danych historycznych dla {yahoo}.")
    else:
        chart_mode = st.radio(
            "Widok",
            ["Cena + Drawdown", "Cena + Wolumen"],
            horizontal=True,
            key="position_chart_mode",
        )
        if chart_mode == "Cena + Drawdown":
            st.plotly_chart(
                build_price_drawdown_chart(history, selected, avg_price, period_label),
                use_container_width=True,
            )
            st.caption(
                "Górny panel: cena zamknięcia + Twoja średnia cena zakupu. "
                "Dolny panel: drawdown — % poniżej dotychczasowego szczytu (ATH) w wybranym okresie."
            )
        else:
            st.plotly_chart(
                build_price_volume_chart(history, avg_price, selected, period_label),
                use_container_width=True,
            )
            st.caption(
                "Pomarańczowa linia — Twoja średnia cena zakupu z raportu XTB. "
                "Wykres używa cen skorygowanych (auto_adjust)."
            )

with tab_fund:
    with st.spinner("Pobieranie danych fundamentalnych…"):
        fund = fetch_fundamentals(yahoo)
        consensus = fetch_analyst_consensus(yahoo)

    if fund.name:
        st.subheader(fund.name)

    render_analyst_consensus(consensus, currency_hint=currency)
    st.divider()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("P/E (trailing)", f"{fund.pe_ratio:,.2f}" if fund.pe_ratio else "—")
        st.metric("P/E (forward)", f"{fund.forward_pe:,.2f}" if fund.forward_pe else "—")
    with c2:
        st.metric("Kapitalizacja", format_market_cap(fund.market_cap))
        st.metric("Sektor", fund.sector or "—")
    with c3:
        st.metric("52W High", f"{fund.week_52_high:,.2f}" if fund.week_52_high else "—")
        st.metric("52W Low", f"{fund.week_52_low:,.2f}" if fund.week_52_low else "—")

    range_pos = range_position_52w(
        float(row["market_price"]) if row.get("market_price") == row.get("market_price") else None,
        fund.week_52_low,
        fund.week_52_high,
    )
    if range_pos is not None:
        st.progress(range_pos, text=f"Pozycja w zakresie 52W: {range_pos * 100:.0f}% (0% = dołek, 100% = szczyt)")
    elif fund.week_52_low and fund.week_52_high:
        st.caption("Brak aktualnej ceny do wyliczenia pozycji w zakresie 52W.")

    c4, c5 = st.columns(2)
    with c4:
        st.metric("Dywidenda", f"{fund.dividend_yield:.2f}%" if fund.dividend_yield else "—")
    with c5:
        st.metric("Branża", fund.industry or "—")

    if not fund.pe_ratio and not fund.market_cap and not consensus.has_data:
        st.caption(
            "ETF-y (np. XAIX.DE) zwykle nie mają P/E, kapitalizacji ani konsensusu analityków w Yahoo — "
            "to normalne. Porównanie z indeksem: zakładka **vs Benchmark**."
        )

with tab_bench:
    with st.spinner("Porównanie z indeksem…"):
        merged, bench_name, bench_sym = build_performance_comparison(
            yahoo,
            period_label,
            ticker_xtb=selected,
            currency=currency,
        )

    if merged.empty:
        st.warning(
            f"Brak wspólnych notowań dla **{yahoo}** i **{bench_name}** (`{bench_sym or '—'}`) "
            f"w okresie {period_label}. Spróbuj inny horyzont lub sprawdź symbol Yahoo."
        )
    else:
        st.caption(f"Indeks: **{bench_name}** (`{bench_sym}`) · ta sama skala czasu co wykres {period_label}")

        last = merged.iloc[-1]
        inst_ret = float(last["instrument"]) - 100
        bench_ret = float(last["benchmark"]) - 100
        alpha = inst_ret - bench_ret

        b1, b2, b3 = st.columns(3)
        with b1:
            st.metric(f"Zwrot {selected}", f"{inst_ret:+.2f}%")
        with b2:
            st.metric(f"Zwrot {bench_name}", f"{bench_ret:+.2f}%")
        with b3:
            st.metric("Alfa (różnica)", f"{alpha:+.2f}%", delta_color=pnl_delta_color(alpha))

        st.plotly_chart(
            build_benchmark_overlay_chart(merged, selected, bench_name, period_label),
            use_container_width=True,
        )

with tab_timing:
    st.subheader("Gdzie kupiłeś?")
    with st.spinner("Wyliczanie percentyla w zakresie 3M…"):
        timing = compute_timing_score(yahoo, avg_price, window_months=3)

    if timing is None:
        st.warning("Brak danych do oceny timingu wejścia.")
    else:
        t1, t2 = st.columns([1, 2])
        with t1:
            st.plotly_chart(build_timing_gauge(timing.percentile, timing.label), use_container_width=True)
        with t2:
            st.markdown(f"### {timing.label}")
            st.write(timing.hint)
            st.markdown(
                f"""
                | | |
                |---|---|
                | Twoja śr. cena | **{timing.entry_price:,.4f}** {currency} |
                | Dołek 3M | {timing.range_low:,.4f} |
                | Szczyt 3M | {timing.range_high:,.4f} |
                | Percentyl w zakresie | **{timing.percentile:.1f}%** |
                """
            )
            st.caption(
                "0% = blisko minimum z ostatnich 3 miesięcy, 100% = blisko maksimum. "
                "To przybliżenie bez daty pierwszego zakupu z XTB."
            )
