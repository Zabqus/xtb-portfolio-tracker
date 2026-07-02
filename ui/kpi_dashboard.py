"""Renderowanie ścianki KPI ze sparkline'ami."""

from __future__ import annotations

import streamlit as st

from core.dashboard_kpis import DashboardKpis, compute_dashboard_kpis
from core.importer import XTBReport
from ui.sparklines import build_sparkline


def render_kpi_wall(
    report: XTBReport,
    analyzed,
    timeline,
    currency: str,
    *,
    title: str = "Dashboard analityczny",
    show_sparkline_toggle: bool = True,
) -> DashboardKpis | None:
    """Renderuje siatkę KPI; zwraca obliczone metryki."""
    if analyzed is None or analyzed.empty:
        return None

    st.subheader(title)
    spark_days = 30
    if show_sparkline_toggle:
        spark_choice = st.radio(
            "Trend sparkline",
            ["30 dni", "90 dni"],
            horizontal=True,
            key="kpi_sparkline_days",
            label_visibility="collapsed",
        )
        spark_days = 90 if spark_choice == "90 dni" else 30
        st.caption(f"Mini-wykresy pokazują trend z ostatnich **{spark_days}** dni.")

    threshold = float(st.session_state.get("alert_threshold_pct", 10.0))
    kpis = compute_dashboard_kpis(
        report,
        analyzed,
        timeline,
        currency=currency,
        sparkline_days=spark_days,
        alert_threshold_pct=threshold,
    )

    if not kpis.has_timeline:
        st.caption(
            "TWR, drawdown i Sharpe wymagają arkusza **Cash Operations** w eksporcie XTB."
        )

    cols_per_row = 4
    for row_start in range(0, len(kpis.metrics), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, metric in zip(cols, kpis.metrics[row_start : row_start + cols_per_row]):
            with col:
                st.metric(
                    metric.label,
                    metric.value,
                    delta=metric.delta,
                    delta_color=metric.delta_color,
                    help=metric.help_text,
                )
                spark_fig = build_sparkline(metric.sparkline)
                if spark_fig is not None:
                    st.plotly_chart(
                        spark_fig,
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key=f"kpi_spark_{metric.label}_{row_start}",
                    )

    return kpis
