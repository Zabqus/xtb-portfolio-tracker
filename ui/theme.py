"""Globalny styl wizualny dashboardu (wstrzykiwany CSS).

Streamlit uruchamia każdą podstronę jako osobny skrypt, dlatego CSS
wstrzykujemy przy każdym renderze. Funkcja `inject_global_css()` jest
wołana raz na górze `render_import_sidebar()`, więc obejmuje wszystkie
strony, które korzystają ze wspólnego sidebaru.
"""

from __future__ import annotations

import streamlit as st

# Paleta spójna z wykresami (zysk/strata) i motywem config.toml
ACCENT = "#2563EB"
PROFIT = "#16A34A"
LOSS = "#DC2626"

_CSS = """
<style>
/* ── Layout: węższy, czytelny kontener z mniejszym górnym marginesem ── */
.block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1280px;
}

/* ── Typografia nagłówków ── */
h1 { font-weight: 750; letter-spacing: -0.02em; }
h2 { font-weight: 700; letter-spacing: -0.01em; margin-top: 0.4rem; }
h3 { font-weight: 650; }

/* ── Metryki jako karty ── */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    transform: translateY(-1px);
}
[data-testid="stMetricLabel"] p {
    font-size: 0.82rem;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
[data-testid="stMetricValue"] {
    font-weight: 720;
    font-size: 1.55rem;
}

/* ── Zakładki ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid #E2E8F0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: #EFF6FF;
    color: #2563EB;
}

/* ── Przyciski ── */
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid #E2E8F0;
    transition: all 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #2563EB;
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(37, 99, 235, 0.15);
}

/* ── Tabele / dataframe ── */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #E2E8F0;
}

/* ── Expandery i komunikaty ── */
[data-testid="stExpander"] {
    border-radius: 12px;
    border: 1px solid #E2E8F0;
}
[data-testid="stExpander"] summary { font-weight: 600; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #F8FAFC;
    border-right: 1px solid #E2E8F0;
}
[data-testid="stSidebar"] h2 { font-size: 1.15rem; }

/* ── Divider trochę luźniejszy ── */
hr { margin: 1.4rem 0; }

/* ── Responsywność: na wąskich ekranach mniej paddingu i mniejsze metryki ── */
@media (max-width: 640px) {
    .block-container { padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 1.4rem; }
    [data-testid="stMetricValue"] { font-size: 1.25rem; }
    [data-testid="stMetric"] { padding: 12px 14px; }
    h1 { font-size: 1.6rem; }
}
</style>
"""


def inject_global_css() -> None:
    """Wstrzykuje globalny CSS. Bezpieczne do wołania na każdej stronie."""
    st.markdown(_CSS, unsafe_allow_html=True)


def section_header(title: str, subtitle: str | None = None) -> None:
    """Spójny nagłówek sekcji z opcjonalnym podtytułem."""
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)
