"""
Podstrona: głęboka analiza pojedynczej pozycji (wykres, fundamenty, benchmark, timing).
"""

import streamlit as st

from core.benchmark import build_performance_comparison, resolve_benchmark
from core.analyst_consensus import fetch_analyst_consensus
from core.fundamentals import fetch_fundamentals, format_market_cap
from ui.analyst_consensus import render_analyst_consensus
from core.history import PERIOD_OPTIONS, fetch_price_history
from core.timing_score import compute_timing_score
from core.session import (
    get_analyzed_open,
    get_display_currency,
    get_position_row,
    get_selected_ticker,
    set_selected_ticker,
)
from ui.formatters import format_currency, pnl_delta_color
from ui.position_charts import (
    build_benchmark_overlay_chart,
    build_price_volume_chart,
    build_timing_gauge,
)
from ui.sidebar import render_import_sidebar

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

st.caption(f"Yahoo: **{yahoo}** · Waluta notowań: **{currency}**")

# --- Nagłówek metryk pozycji ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Ilość", f"{quantity:,.4f}")
with m2:
    st.metric("Śr. cena zakupu", f"{avg_price:,.4f} {currency}")
with m3:
    if pnl is not None and not (isinstance(pnl, float) and pnl != pnl):
        st.metric(
            "Zysk / strata",
            format_currency(float(pnl), get_display_currency()),
            delta=f"{roi:.2f}%" if roi == roi else None,
            delta_color=pnl_delta_color(float(pnl)),
        )
with m4:
    bench_name, _ = resolve_benchmark(selected, currency)
    st.metric("Benchmark", bench_name)

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
