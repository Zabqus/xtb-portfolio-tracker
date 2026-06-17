"""Wykresy metryk ryzyka — macierz korelacji portfela."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_correlation_heatmap(corr: pd.DataFrame) -> go.Figure:
    """Heatmap korelacji: niebieski (−1) → biały (0) → czerwony (+1)."""
    if corr is None or corr.empty:
        fig = go.Figure()
        fig.update_layout(title="Brak danych do macierzy korelacji")
        return fig

    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale=["#3498db", "#ffffff", "#e74c3c"],
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    fig.update_layout(
        title="Macierz korelacji dziennych zwrotów",
        height=max(380, 60 * len(corr.columns)),
        margin=dict(t=60),
    )
    fig.update_xaxes(side="bottom")
    return fig
