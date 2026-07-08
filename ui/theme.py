"""Globalny styl wizualny dashboardu (wstrzykiwany CSS).

Streamlit uruchamia każdą podstronę jako osobny skrypt, dlatego CSS
wstrzykujemy przy każdym renderze. Funkcja `inject_global_css()` jest
wołana raz na górze `render_import_sidebar()`, więc obejmuje wszystkie
strony, które korzystają ze wspólnego sidebaru.
"""

from __future__ import annotations

import streamlit as st

from core.preferences import load_preferences, save_preference

# Paleta spójna z wykresami (zysk/strata) i motywem config.toml
ACCENT = "#2563EB"
ACCENT_DARK = "#3B82F6"
PROFIT = "#16A34A"
PROFIT_DARK = "#22C55E"
LOSS = "#DC2626"
LOSS_DARK = "#EF4444"

_THEME_OPTIONS = ("light", "dark")
_THEME_STORAGE_KEY = "xtb_color_theme"

_CRITICAL_CSS = {
    "dark": """
        html, body,
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #0F172A !important;
            color: #E2E8F0 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #0B1220 !important;
        }
        [data-testid="stSidebarNav"] {
            background-color: #0B1220 !important;
        }
    """,
    "light": """
        html, body,
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #FFFFFF !important;
            color: #0F172A !important;
        }
        [data-testid="stSidebar"] {
            background-color: #F8FAFC !important;
        }
        [data-testid="stSidebarNav"] {
            background-color: #F8FAFC !important;
        }
    """,
}

_CSS_SHARED = """
<style>
.block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1280px;
}
h1 { font-weight: 750; letter-spacing: -0.02em; }
h2 { font-weight: 700; letter-spacing: -0.01em; margin-top: 0.4rem; }
h3 { font-weight: 650; }
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
    transition: all 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px);
}
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}
[data-testid="stExpander"] { border-radius: 12px; }
[data-testid="stExpander"] summary { font-weight: 600; }
hr { margin: 1.4rem 0; }
@media (max-width: 640px) {
    .block-container { padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 1.4rem; }
    [data-testid="stMetricValue"] { font-size: 1.25rem; }
    [data-testid="stMetric"] { padding: 12px 14px; }
    h1 { font-size: 1.6rem; }
}
</style>
"""

_CSS_WIDGETS_LIGHT = """
h1, h2, h3, h4, h5, h6,
p, label, span, li,
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p {
    color: #0F172A !important;
}
.stCaption, [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: #64748B !important;
}
.stTabs [data-baseweb="tab"] { color: #475569 !important; }
.stTabs [aria-selected="true"] { color: #2563EB !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stFileUploader"] section,
div[data-testid="stTextArea"] textarea {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border-color: #CBD5E1 !important;
}
div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label {
    color: #0F172A !important;
}
[data-testid="stDataEditor"],
[data-testid="stDataEditor"] [data-testid="glideDataEditor"],
[data-testid="stDataFrame"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
}
[data-testid="stDataEditor"] input,
[data-testid="stDataEditor"] textarea {
    color: #0F172A !important;
    background-color: #FFFFFF !important;
}
[data-testid="stPlotlyChart"] {
    background-color: #FFFFFF;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    padding: 4px;
}
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span {
    color: inherit !important;
}
"""

_CSS_WIDGETS_DARK = """
h1, h2, h3, h4, h5, h6, p, label, span, li { color: #E2E8F0; }
.stCaption, [data-testid="stCaptionContainer"] { color: #94A3B8 !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stFileUploader"] section,
div[data-testid="stTextArea"] textarea {
    background-color: #1E293B !important;
    color: #E2E8F0 !important;
    border-color: #334155 !important;
}
div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label {
    color: #E2E8F0 !important;
}
[data-testid="stDataEditor"],
[data-testid="stDataEditor"] [data-testid="glideDataEditor"],
[data-testid="stDataFrame"] {
    background-color: #1E293B !important;
    color: #E2E8F0 !important;
}
[data-testid="stDataEditor"] input,
[data-testid="stDataEditor"] textarea {
    color: #E2E8F0 !important;
    background-color: #1E293B !important;
}
[data-testid="stPlotlyChart"] {
    background-color: #1E293B;
    border-radius: 12px;
    border: 1px solid #334155;
    padding: 4px;
}
div[data-testid="stAlert"] p { color: inherit; }
"""

_CSS_VARS_LIGHT = """
<style>
:root {
    --background-color: #FFFFFF;
    --secondary-background-color: #F8FAFC;
    --text-color: #0F172A;
}
</style>
"""

_CSS_VARS_DARK = """
<style>
:root {
    --background-color: #0F172A;
    --secondary-background-color: #1E293B;
    --text-color: #E2E8F0;
}
</style>
"""

_CSS_LIGHT = f"""
<style>
.stApp, [data-testid="stAppViewContainer"] {{
    background-color: #FFFFFF;
    color: #0F172A;
}}
{_CSS_WIDGETS_LIGHT}
[data-testid="stMetric"] {{
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    transform: translateY(-1px);
}}
[data-testid="stMetricLabel"] p {{
    font-size: 0.82rem;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
[data-testid="stMetricValue"] {{ font-weight: 720; font-size: 1.55rem; color: #0F172A; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid #E2E8F0; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 8px 8px 0 0; padding: 8px 16px; font-weight: 600; }}
.stTabs [aria-selected="true"] {{ background: #EFF6FF; color: #2563EB; }}
.stButton > button, .stDownloadButton > button {{
    border: 1px solid #E2E8F0;
    background: #FFFFFF;
    color: #0F172A;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: #2563EB;
    box-shadow: 0 3px 10px rgba(37, 99, 235, 0.15);
}}
[data-testid="stDataFrame"] {{ border: 1px solid #E2E8F0; }}
[data-testid="stExpander"] {{ border: 1px solid #E2E8F0; background: #FFFFFF; }}
[data-testid="stSidebar"] {{
    background: #F8FAFC;
    border-right: 1px solid #E2E8F0;
}}
[data-testid="stSidebar"] h2 {{ font-size: 1.15rem; color: #0F172A; }}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {{ color: #334155; }}
div[data-testid="stAlert"] {{ border-radius: 10px; }}
</style>
"""

_CSS_DARK = f"""
<style>
.stApp, [data-testid="stAppViewContainer"] {{
    background-color: #0F172A;
    color: #E2E8F0;
}}
{_CSS_WIDGETS_DARK}
[data-testid="stMetric"] {{
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
    transition: box-shadow 0.15s ease, transform 0.15s ease;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    transform: translateY(-1px);
}}
[data-testid="stMetricLabel"] p {{
    font-size: 0.82rem;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
[data-testid="stMetricValue"] {{ font-weight: 720; font-size: 1.55rem; color: #F1F5F9; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid #334155; }}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
    font-weight: 600;
    color: #94A3B8;
    background: transparent;
}}
.stTabs [aria-selected="true"] {{ background: #1E3A5F; color: #60A5FA; }}
.stButton > button, .stDownloadButton > button {{
    border: 1px solid #334155;
    background: #1E293B;
    color: #E2E8F0;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: #3B82F6;
    box-shadow: 0 3px 12px rgba(59, 130, 246, 0.25);
}}
[data-testid="stDataFrame"] {{ border: 1px solid #334155; }}
[data-testid="stExpander"] {{
    border: 1px solid #334155;
    background: #1E293B;
}}
[data-testid="stSidebar"] {{
    background: #0B1220;
    border-right: 1px solid #334155;
}}
[data-testid="stSidebar"] h2 {{ font-size: 1.15rem; color: #F1F5F9; }}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {{ color: #CBD5E1; }}
div[data-testid="stAlert"] {{ border-radius: 10px; }}
</style>
"""


def init_color_theme() -> None:
    """Ładuje zapisany motyw do session_state (wspólny dla wszystkich podstron)."""
    if "color_theme" in st.session_state:
        return
    saved = load_preferences().get("color_theme", "dark")
    st.session_state.color_theme = saved if saved in _THEME_OPTIONS else "dark"


def _persist_color_theme() -> None:
    theme = st.session_state.color_theme
    save_preference("color_theme", theme)
    _sync_client_theme(theme)


def _sync_client_theme(theme: str) -> None:
    """Natychmiastowa synchronizacja motywu w localStorage (anty-flicker)."""
    safe = theme if theme in _THEME_OPTIONS else "dark"
    st.html(
        f"""<script>
        window.__xtbSetTheme && window.__xtbSetTheme({safe!r});
        </script>""",
        unsafe_allow_javascript=True,
    )


def _theme_preload_html(server_theme: str) -> str:
    critical = {k: v.replace("`", "\\`") for k, v in _CRITICAL_CSS.items()}
    return f"""<script>
(function () {{
  const STORAGE_KEY = {_THEME_STORAGE_KEY!r};
  const STYLE_ID = "xtb-theme-critical";
  const CRITICAL = {{
    dark: `{critical["dark"]}`,
    light: `{critical["light"]}`,
  }};
  const SERVER = {server_theme!r};

  function resolveTheme() {{
    return SERVER === "dark" ? "dark" : "light";
  }}

  function applyTheme(theme) {{
    const resolved = theme === "dark" ? "dark" : "light";
    const css = CRITICAL[resolved] || CRITICAL.dark;
    try {{ localStorage.setItem(STORAGE_KEY, resolved); }} catch (e) {{}}
    let el = document.getElementById(STYLE_ID);
    if (!el) {{
      el = document.createElement("style");
      el.id = STYLE_ID;
      document.head.appendChild(el);
    }}
    el.textContent = css;
    document.documentElement.setAttribute("data-xtb-theme", resolved);
  }}

  window.__xtbSetTheme = applyTheme;
  applyTheme(resolveTheme());
}})();
</script>"""


def inject_theme_preload() -> None:
    """Wstrzykuje skrypt anty-flicker — czyta localStorage zanim wyrenderuje się treść."""
    init_color_theme()
    st.html(_theme_preload_html(get_color_theme()), unsafe_allow_javascript=True)


def bootstrap_page() -> None:
    """Wywołaj jako pierwszą instrukcję Streamlit na każdej podstronie (po set_page_config)."""
    init_color_theme()
    inject_theme_preload()
    inject_global_css()


def get_color_theme() -> str:
    """Aktywny motyw: 'light' lub 'dark'."""
    init_color_theme()
    theme = st.session_state.color_theme
    return theme if theme in _THEME_OPTIONS else "dark"


def is_dark_theme() -> bool:
    return get_color_theme() == "dark"


def accent_color() -> str:
    return ACCENT_DARK if is_dark_theme() else ACCENT


def profit_color() -> str:
    return PROFIT_DARK if is_dark_theme() else PROFIT


def loss_color() -> str:
    return LOSS_DARK if is_dark_theme() else LOSS


def inject_global_css() -> None:
    """Wstrzykuje globalny CSS. Bezpieczne do wołania na każdej stronie."""
    init_color_theme()
    dark = is_dark_theme()
    css = _CSS_SHARED + (_CSS_VARS_DARK if dark else _CSS_VARS_LIGHT)
    css += _CSS_DARK if dark else _CSS_LIGHT
    st.markdown(css, unsafe_allow_html=True)
    _sync_client_theme(get_color_theme())


def render_theme_selector() -> None:
    """Przełącznik motywu w sidebarze — zapis trwały między podstronami i sesjami."""
    init_color_theme()
    st.selectbox(
        "Motyw",
        options=list(_THEME_OPTIONS),
        format_func=lambda t: "🌙 Ciemny" if t == "dark" else "☀️ Jasny",
        key="color_theme",
        on_change=_persist_color_theme,
    )


def metric_card_style() -> dict[str, str]:
    """Argumenty dla streamlit_extras.metric_cards.style_metric_cards."""
    if is_dark_theme():
        return {
            "background_color": "#1E293B",
            "border_left_color": "#3B82F6",
            "border_color": "#334155",
            "box_shadow": "rgba(0,0,0,0.35)",
        }
    return {
        "background_color": "#FFFFFF",
        "border_left_color": "#2563EB",
        "border_color": "#E2E8F0",
        "box_shadow": "rgba(15, 23, 42, 0.06)",
    }


def trend_color_css(kind: str) -> str:
    """Kolor CSS dla stylera pandas (positive / negative)."""
    if kind == "positive":
        return profit_color()
    if kind == "negative":
        return loss_color()
    return ""


def muted_text_color() -> str:
    return "#94A3B8" if is_dark_theme() else "#64748B"


def glossary_term_html(term: str, definition: str) -> str:
    """HTML karty pojęcia w słowniku — dopasowany do motywu."""
    if is_dark_theme():
        bg, border, accent, title, body, muted = (
            "#1E293B",
            "#334155",
            "#3B82F6",
            "#F1F5F9",
            "#CBD5E1",
            "#64748B",
        )
    else:
        bg, border, accent, title, body, muted = (
            "#FFFFFF",
            "#E2E8F0",
            "#2563EB",
            "#0F172A",
            "#475569",
            "#94A3B8",
        )
    term_html = term
    return f"""
        <div style="
            background:{bg};
            border:1px solid {border};
            border-left:4px solid {accent};
            border-radius:10px;
            padding:12px 16px;
            margin-bottom:10px;">
            <div style="font-weight:700;font-size:1.02rem;color:{title};">{term_html}</div>
            <div style="color:{body};font-size:0.92rem;margin-top:3px;">{definition}</div>
        </div>
        """


def section_header(title: str, subtitle: str | None = None) -> None:
    """Spójny nagłówek sekcji z opcjonalnym podtytułem."""
    st.subheader(title)
    if subtitle:
        st.caption(subtitle)
