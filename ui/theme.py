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
    padding-top: 1.6rem;
    padding-bottom: 3.5rem;
    max-width: 1240px;
}
/* Hierarchy: title → section → body → caption */
h1 {
    font-weight: 720;
    letter-spacing: -0.025em;
    line-height: 1.2;
    margin-bottom: 0.15rem !important;
}
h2 {
    font-weight: 680;
    letter-spacing: -0.015em;
    margin-top: 0.35rem;
    margin-bottom: 0.35rem !important;
}
h3 {
    font-weight: 650;
    letter-spacing: -0.01em;
    margin-bottom: 0.25rem !important;
}
.stCaption, [data-testid="stCaptionContainer"] {
    line-height: 1.45;
}
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
    transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}
[data-testid="stExpander"] { border-radius: 12px; }
[data-testid="stExpander"] summary { font-weight: 600; }
hr {
    margin: 1.1rem 0 1.35rem 0;
    border: none;
    height: 1px;
    opacity: 0.65;
}
div[data-testid="stHorizontalBlock"] {
    gap: 0.85rem;
}
[data-testid="stMetric"] {
    height: 100%;
}
/* Soften default Streamlit success/info banners */
div[data-testid="stAlert"] {
    border-radius: 10px;
    padding: 0.65rem 0.9rem;
}
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        padding-top: 1.1rem;
    }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    [data-testid="stMetric"] { padding: 12px 14px !important; }
    h1 { font-size: 1.55rem; }
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
    background-color: transparent;
    border-radius: 12px;
    border: 1px solid #F1F5F9;
    padding: 2px;
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
    background-color: transparent;
    border-radius: 12px;
    border: 1px solid #1E293B;
    padding: 2px;
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
    border: 1px solid #E8EEF5;
    border-left: 3px solid #2563EB;
    border-radius: 12px;
    padding: 14px 16px 12px 14px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
    transition: box-shadow 0.15s ease, border-color 0.15s ease;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);
    border-color: #D6E0EC;
}}
[data-testid="stMetricLabel"] p {{
    font-size: 0.78rem;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
[data-testid="stMetricValue"] {{
    font-weight: 700;
    font-size: 1.48rem;
    color: #0F172A;
    letter-spacing: -0.02em;
}}
[data-testid="stMetricDelta"] {{ font-size: 0.85rem; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid #E8EEF5; }}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px 8px 0 0;
    padding: 8px 14px;
    font-weight: 600;
}}
.stTabs [aria-selected="true"] {{ background: #EFF6FF; color: #2563EB; }}
.stButton > button, .stDownloadButton > button {{
    border: 1px solid #E2E8F0;
    background: #FFFFFF;
    color: #0F172A;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: #2563EB;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.12);
}}
[data-testid="stDataFrame"] {{ border: 1px solid #E8EEF5; }}
[data-testid="stExpander"] {{ border: 1px solid #E8EEF5; background: #FFFFFF; }}
[data-testid="stSidebar"] {{
    background: #F8FAFC;
    border-right: 1px solid #E8EEF5;
}}
[data-testid="stSidebar"] h2 {{ font-size: 1.1rem; color: #0F172A; }}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {{ color: #334155; }}
hr {{ background: #E8EEF5; }}
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
    background: #1A2436;
    border: 1px solid #2A3649;
    border-left: 3px solid #3B82F6;
    border-radius: 12px;
    padding: 14px 16px 12px 14px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
    transition: box-shadow 0.15s ease, border-color 0.15s ease;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 3px 14px rgba(0, 0, 0, 0.28);
    border-color: #3A4A63;
}}
[data-testid="stMetricLabel"] p {{
    font-size: 0.78rem;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
[data-testid="stMetricValue"] {{
    font-weight: 700;
    font-size: 1.48rem;
    color: #F1F5F9;
    letter-spacing: -0.02em;
}}
[data-testid="stMetricDelta"] {{ font-size: 0.85rem; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid #2A3649; }}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px 8px 0 0;
    padding: 8px 14px;
    font-weight: 600;
    color: #94A3B8;
    background: transparent;
}}
.stTabs [aria-selected="true"] {{ background: #1E3A5F; color: #60A5FA; }}
.stButton > button, .stDownloadButton > button {{
    border: 1px solid #2A3649;
    background: #1A2436;
    color: #E2E8F0;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: #3B82F6;
    box-shadow: 0 2px 10px rgba(59, 130, 246, 0.2);
}}
[data-testid="stDataFrame"] {{ border: 1px solid #2A3649; }}
[data-testid="stExpander"] {{
    border: 1px solid #2A3649;
    background: #1A2436;
}}
[data-testid="stSidebar"] {{
    background: #0B1220;
    border-right: 1px solid #2A3649;
}}
[data-testid="stSidebar"] h2 {{ font-size: 1.1rem; color: #F1F5F9; }}
[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] label {{ color: #CBD5E1; }}
hr {{ background: #2A3649; }}
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
            "background_color": "#1A2436",
            "border_left_color": "#3B82F6",
            "border_color": "#2A3649",
            "box_shadow": "rgba(0,0,0,0.22)",
        }
    return {
        "background_color": "#FFFFFF",
        "border_left_color": "#2563EB",
        "border_color": "#E8EEF5",
        "box_shadow": "rgba(15, 23, 42, 0.04)",
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
        bg, border, accent, title, body = (
            "#1A2436",
            "#2A3649",
            "#3B82F6",
            "#F1F5F9",
            "#CBD5E1",
        )
    else:
        bg, border, accent, title, body = (
            "#FFFFFF",
            "#E8EEF5",
            "#2563EB",
            "#0F172A",
            "#475569",
        )
    term_html = term
    return f"""
        <div style="
            background:{bg};
            border:1px solid {border};
            border-left:3px solid {accent};
            border-radius:10px;
            padding:12px 16px;
            margin-bottom:10px;">
            <div style="font-weight:700;font-size:1.02rem;color:{title};">{term_html}</div>
            <div style="color:{body};font-size:0.92rem;margin-top:3px;line-height:1.45;">{definition}</div>
        </div>
        """


def section_header(title: str, subtitle: str | None = None) -> None:
    """Spójny nagłówek sekcji z akcentem i opcjonalnym podtytułem."""
    accent = accent_color()
    muted = muted_text_color()
    title_color = "#F1F5F9" if is_dark_theme() else "#0F172A"
    sub = (
        f'<div style="color:{muted};font-size:0.9rem;margin-top:3px;line-height:1.4;">'
        f"{subtitle}</div>"
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div style="
            margin:0.15rem 0 0.95rem 0;
            padding:2px 0 2px 12px;
            border-left:3px solid {accent};">
            <div style="
                font-weight:700;
                font-size:1.22rem;
                letter-spacing:-0.015em;
                color:{title_color};
                line-height:1.25;">{title}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )
