"""
Podstrona: watchlist – tickery spoza portfela, zwroty i porównanie z portfelem.
"""

import pandas as pd
import streamlit as st

from core.session import (
    add_watchlist_symbol,
    get_analyzed_open,
    get_report,
    get_watchlist,
    remove_watchlist_symbol,
)
from core.watchlist import (
    COMPARE_PERIODS,
    build_normalized_comparison,
    build_watchlist_table,
    portfolio_weighted_return_from_analyzed,
    resolve_watchlist_symbol,
)
from ui.sidebar import render_import_sidebar
from ui.watchlist_charts import build_normalized_lines_chart, build_vs_portfolio_bar

st.title("👁️ Watchlist")

st.caption(
    "Dodaj tickery, których **nie masz** w otwartym portfelu — śledź ceny i zwroty "
    "oraz porównuj je ze średnią ważoną Twoich pozycji."
)

render_import_sidebar()

report = get_report()
analyzed = get_analyzed_open() if report else None

# --- Zarządzanie listą ---
st.subheader("Dodaj instrument")
c_in, c_btn = st.columns([3, 1])
with c_in:
    new_symbol = st.text_input(
        "Symbol (XTB lub Yahoo)",
        placeholder="np. NVDA.US, AAPL, VWCE",
        key="watchlist_new_symbol",
        label_visibility="collapsed",
    )
with c_btn:
    st.write("")
    add_clicked = st.button("Dodaj", type="primary", use_container_width=True)

if add_clicked and new_symbol.strip():
    ok, msg = add_watchlist_symbol(new_symbol)
    if ok:
        st.success(msg)
        st.rerun()
    else:
        st.warning(msg)
elif add_clicked:
    st.warning("Wpisz symbol instrumentu.")

if new_symbol.strip():
    try:
        preview = resolve_watchlist_symbol(new_symbol)
        st.caption(f"Podgląd mapowania Yahoo: `{preview}`")
    except ValueError:
        pass

entries = get_watchlist()
if not entries:
    st.info(
        "Watchlista jest pusta. Dodaj symbol powyżej — dane zapisują się lokalnie w "
        "`watchlist.json` w katalogu projektu."
    )
    if not report:
        st.caption("Aby porównać zwroty z portfelem, wgraj też eksport XTB w sidebarze.")
    st.stop()

st.divider()
st.subheader(f"Twoja watchlista ({len(entries)})")

period_label = st.radio(
    "Okres porównania",
    list(COMPARE_PERIODS),
    horizontal=True,
    key="watchlist_period",
)

with st.spinner("Pobieranie cen i zwrotów…"):
    table = build_watchlist_table(entries, analyzed, period_label)

if table.empty:
    st.warning("Brak danych do wyświetlenia.")
    st.stop()

ret_col = f"return_{period_label}"
port_ret = portfolio_weighted_return_from_analyzed(analyzed, period_label)

if analyzed is None:
    st.warning("Wgraj raport XTB, aby zobaczyć porównanie z portfelem (kolumna „vs portfel”).")
else:
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Pozycje na watchliście", len(entries))
    with m2:
        if port_ret is not None:
            st.metric(f"Zwrot portfela ({period_label}, ważony)", f"{port_ret:+.2f}%")
        else:
            st.metric(f"Zwrot portfela ({period_label})", "—")
    with m3:
        valid_vs = table["vs_portfolio_pct"].dropna()
        if not valid_vs.empty:
            best = table.loc[valid_vs.idxmax()]
            st.metric(
                "Najlepsza alfa vs portfel",
                f"{best['symbol']} ({best['vs_portfolio_pct']:+.2f}%)",
            )

in_port = table[table["in_portfolio"]]
if not in_port.empty:
    st.warning(
        "Te symbole są już w portfelu (możesz je usunąć z watchlisty): "
        + ", ".join(in_port["symbol"].tolist())
    )

display = table.copy()
display["Cena"] = display["market_price"].apply(
    lambda v: f"{v:,.2f}" if pd.notna(v) else "—"
)
display[f"Zwrot {period_label}"] = display[ret_col].apply(
    lambda v: f"{v:+.2f}%" if pd.notna(v) else "—"
)
display["vs portfel"] = display["vs_portfolio_pct"].apply(
    lambda v: f"{v:+.2f}%" if pd.notna(v) else "—"
)
display["W portfelu"] = display["in_portfolio"].map({True: "tak", False: "—"})

st.dataframe(
    display[
        ["symbol", "yahoo", "Cena", f"Zwrot {period_label}", "vs portfel", "W portfelu"]
    ].rename(
        columns={
            "symbol": "Symbol",
            "yahoo": "Yahoo",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

# --- Wykresy ---
st.subheader("Wizualizacje")
if port_ret is not None:
    st.plotly_chart(
        build_vs_portfolio_bar(table, period_label, port_ret),
        use_container_width=True,
    )

if analyzed is not None:
    wl_yahoo = tuple(e.yahoo for e in entries)
    port_yahoo = tuple(
        analyzed.dropna(subset=["ticker_yahoo"])["ticker_yahoo"].astype(str).unique()
    )
    with st.spinner("Budowanie wykresu porównawczego…"):
        comparison = build_normalized_comparison(wl_yahoo, port_yahoo, period_label)
    if comparison.empty:
        st.caption("Brak wspólnych sesji giełdowych do wykresu znormalizowanego.")
    else:
        st.plotly_chart(
            build_normalized_lines_chart(comparison, period_label),
            use_container_width=True,
        )
        st.caption(
            "Pomarańczowa linia — średnia znormalizowana otwartych pozycji; "
            "niebieska — średnia instrumentów z watchlisty (wspólne dni notowań)."
        )

# --- Usuwanie ---
st.divider()
st.subheader("Usuń z watchlisty")
to_remove = st.selectbox(
    "Wybierz symbol",
    [e.symbol for e in entries],
    format_func=lambda s: next(
        (f"{e.symbol} → {e.yahoo}" for e in entries if e.symbol == s),
        s,
    ),
    key="watchlist_remove_pick",
)
if st.button("Usuń wybrany", type="secondary"):
    remove_watchlist_symbol(to_remove)
    st.success(f"Usunięto **{to_remove}**.")
    st.rerun()

st.caption(
    "Mapowanie symboli: `core/importer_maps.py`. Plik `watchlist.json` nie jest commitowany do repozytorium."
)
