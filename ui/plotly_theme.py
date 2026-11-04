"""Wspólne stylowanie wykresów Plotly pod jasny / ciemny motyw."""

from __future__ import annotations

import plotly.graph_objects as go

from ui.theme import is_dark_theme

_HEATMAP_SCALE_LIGHT = ["#3498db", "#F8FAFC", "#e74c3c"]
_HEATMAP_SCALE_DARK = ["#3498db", "#2A3649", "#e74c3c"]


def heatmap_color_scale() -> list[str]:
    return _HEATMAP_SCALE_DARK if is_dark_theme() else _HEATMAP_SCALE_LIGHT


def reference_line_color() -> str:
    return "#64748B" if is_dark_theme() else "#94A3B8"


def _palette() -> dict[str, str]:
    if is_dark_theme():
        return {
            "plot_bg": "#1A2436",
            "paper_bg": "#1A2436",
            "font": "#E2E8F0",
            "muted": "#94A3B8",
            "grid": "#2A3649",
            "zeroline": "#3A4A63",
            "hover_bg": "#0F172A",
        }
    return {
        "plot_bg": "#FFFFFF",
        "paper_bg": "#FFFFFF",
        "font": "#0F172A",
        "muted": "#64748B",
        "grid": "#EEF2F7",
        "zeroline": "#D6DEE8",
        "hover_bg": "#FFFFFF",
    }


def _retarget_reference_lines(fig: go.Figure, ref_color: str) -> None:
    for shape in fig.layout.shapes or []:
        line = getattr(shape, "line", None)
        if line is None:
            continue
        color = getattr(line, "color", None)
        if color in (None, "gray", "grey", "#808080", "#grey"):
            shape.line.color = ref_color

    for ann in fig.layout.annotations or []:
        font = getattr(ann, "font", None)
        if font is not None and getattr(font, "color", None) in (None, "gray", "grey"):
            ann.font.color = ref_color


def _has_tight_margins(fig: go.Figure) -> bool:
    """Sparklines / mini-charty z margin≈0 — nie nadpisujemy ich odstępów."""
    margin = fig.layout.margin
    if margin is None:
        return False
    vals = [getattr(margin, side, None) for side in ("l", "r", "t", "b")]
    numeric = [v for v in vals if isinstance(v, (int, float))]
    return bool(numeric) and max(numeric) <= 8


def style_figure(fig: go.Figure, *, heatmap: bool = False) -> go.Figure:
    """Dopasowuje tło, osie, legendę, marginesy i hover do aktywnego motywu."""
    pal = _palette()
    ref = reference_line_color()
    axis_kwargs = dict(
        gridcolor=pal["grid"],
        linecolor=pal["grid"],
        zerolinecolor=pal["zeroline"],
        tickfont=dict(color=pal["muted"], size=11),
        title_font=dict(color=pal["muted"], size=12),
        showline=False,
        zerolinewidth=1,
    )

    layout_kwargs: dict = {
        "paper_bgcolor": pal["paper_bg"],
        "plot_bgcolor": pal["plot_bg"],
        "font": dict(color=pal["font"], family="sans-serif", size=12),
        "title": dict(
            font=dict(color=pal["font"], size=15, family="sans-serif"),
            x=0.01,
            xanchor="left",
            pad=dict(t=4, b=8),
        ),
        "legend": dict(
            font=dict(color=pal["font"], size=11),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
        "hoverlabel": dict(
            bgcolor=pal["hover_bg"],
            font=dict(size=12, family="sans-serif", color=pal["font"]),
            bordercolor=pal["grid"],
        ),
        "coloraxis_colorbar": dict(
            tickfont=dict(color=pal["muted"]),
            title_font=dict(color=pal["muted"]),
        ),
        "separators": ", ",
    }

    if not _has_tight_margins(fig):
        layout_kwargs["margin"] = dict(l=48, r=28, t=56, b=44, pad=2)

    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(**axis_kwargs)
    fig.update_yaxes(**axis_kwargs)

    if heatmap and fig.data:
        fig.update_traces(
            colorscale=heatmap_color_scale(),
            selector=dict(type="heatmap"),
        )

    _retarget_reference_lines(fig, ref)

    for ann in fig.layout.annotations or []:
        font = getattr(ann, "font", None)
        if font is not None:
            # Tytuły subplotów nieco wyraźniejsze, reszta w kolorze tekstu
            size = getattr(font, "size", None) or 12
            ann.font.color = pal["font"] if size >= 13 else pal["muted"]

    return fig
