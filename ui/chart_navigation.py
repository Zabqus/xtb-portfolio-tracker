"""Nawigacja z wykresów Plotly do strony Pozycja."""

from __future__ import annotations

import streamlit as st

from core.session import set_selected_ticker


def extract_ticker_from_selection(
    event,
    chart_key: str,
    labels: list[str] | None = None,
) -> str | None:
    """Wyciąga ticker z zaznaczenia wykresu Plotly (Streamlit on_select)."""
    if event is None:
        return None
    selection = getattr(event, "selection", None)
    if not selection:
        return None
    points = getattr(selection, "points", None) or []
    if not points:
        return None

    pt = points[0]
    ticker = pt.get("x") or pt.get("label") or pt.get("text")
    if (ticker is None or str(ticker).strip() == "") and "point_index" in pt and labels:
        idx = int(pt["point_index"])
        if 0 <= idx < len(labels):
            ticker = labels[idx]
    if ticker is None:
        return None
    ticker = str(ticker).strip()
    if not ticker:
        return None

    state_key = f"_chart_sel_{chart_key}"
    if st.session_state.get(state_key) == ticker:
        return None
    st.session_state[state_key] = ticker
    return ticker


def navigate_to_position(ticker: str) -> None:
    """Ustawia ticker w sesji i przechodzi do analizy pozycji."""
    set_selected_ticker(ticker)
    st.switch_page("pages/2_Pozycja.py")


def render_navigable_chart(
    fig,
    chart_key: str,
    *,
    tickers: list[str] | None = None,
) -> None:
    """Renderuje wykres z obsługą kliknięcia → Pozycja."""
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        selection_mode=("points",),
        key=chart_key,
    )
    ticker = extract_ticker_from_selection(event, chart_key, labels=tickers)
    if ticker:
        navigate_to_position(ticker)
