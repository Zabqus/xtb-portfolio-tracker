"""Wspólne stylowanie wykresów Plotly pod jasny / ciemny motyw."""

from __future__ import annotations

import plotly.graph_objects as go

from ui.theme import is_dark_theme

_HEATMAP_SCALE_LIGHT = ["#3498db", "#ffffff", "#e74c3c"]
_HEATMAP_SCALE_DARK = ["#3498db", "#334155", "#e74c3c"]


def heatmap_color_scale() -> list[str]:
    return _HEATMAP_SCALE_DARK if is_dark_theme() else _HEATMAP_SCALE_LIGHT


def reference_line_color() -> str:
    return "#64748B" if is_dark_theme() else "#94A3B8"


def _palette() -> dict[str, str]:
    if is_dark_theme():
        return {
            "plot_bg": "#1E293B",
            "paper_bg": "rgba(0,0,0,0)",
            "font": "#E2E8F0",
            "grid": "#334155",
            "zeroline": "#475569",
        }
    return {
        "plot_bg": "#FFFFFF",
        "paper_bg": "rgba(0,0,0,0)",
        "font": "#0F172A",
        "grid": "#E2E8F0",
        "zeroline": "#CBD5E1",
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


def style_figure(fig: go.Figure, *, heatmap: bool = False) -> go.Figure:
    """Dopasowuje tło, osie, legendę i siatkę do aktywnego motywu aplikacji."""
    pal = _palette()
    ref = reference_line_color()
    axis_kwargs = dict(
        gridcolor=pal["grid"],
        linecolor=pal["grid"],
        zerolinecolor=pal["zeroline"],
        tickfont=dict(color=pal["font"]),
        title_font=dict(color=pal["font"]),
    )

    fig.update_layout(
        paper_bgcolor=pal["paper_bg"],
        plot_bgcolor=pal["plot_bg"],
        font=dict(color=pal["font"], family="sans-serif"),
        title_font=dict(color=pal["font"]),
        legend=dict(font=dict(color=pal["font"]), bgcolor="rgba(0,0,0,0)"),
        coloraxis_colorbar=dict(
            tickfont=dict(color=pal["font"]),
            title_font=dict(color=pal["font"]),
        ),
    )
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
            ann.font.color = pal["font"]

    return fig
