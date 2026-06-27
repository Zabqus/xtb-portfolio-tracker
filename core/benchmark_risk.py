"""
Beta, tracking error i information ratio portfela względem benchmarku (rolling).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.portfolio_benchmark import build_portfolio_vs_benchmark
from core.risk_metrics import TRADING_DAYS

ROLLING_BETA_WINDOW = 252  # ~1 rok handlowy


@dataclass
class BenchmarkRiskSummary:
    beta: float | None
    tracking_error_pct: float | None
    information_ratio: float | None
    has_data: bool


    twr_index: pd.DataFrame,
    benchmark_name: str,
    window: int = ROLLING_BETA_WINDOW,
) -> pd.DataFrame:
    """
    Rolling beta, tracking error (roczny %) i information ratio.

    Kolumny: date, beta, tracking_error_pct, information_ratio.
    """
    merged = build_portfolio_vs_benchmark(twr_index, benchmark_name)
    if merged.empty or "benchmark" not in merged.columns:
        return pd.DataFrame()

    df = merged.dropna(subset=["portfolio", "benchmark"]).copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if len(df) < window + 5:
        return pd.DataFrame()

    port_ret = df["portfolio"].pct_change()
    bench_ret = df["benchmark"].pct_change()
    aligned = pd.DataFrame(
        {"date": df["date"], "port": port_ret, "bench": bench_ret}
    ).dropna(subset=["port", "bench"])
    if len(aligned) < window:
        return pd.DataFrame()

    betas: list[float] = []
    tes: list[float] = []
    irs: list[float] = []
    dates: list = []

    for i in range(len(aligned)):
        if i < window - 1:
            continue
        chunk = aligned.iloc[i - window + 1 : i + 1]
        cov = chunk["port"].cov(chunk["bench"])
        var_b = chunk["bench"].var()
        beta = float(cov / var_b) if var_b and var_b > 0 else np.nan

        exc = chunk["port"] - chunk["bench"]
        te = float(exc.std() * np.sqrt(TRADING_DAYS) * 100) if len(exc) > 1 else np.nan
        ir = (
            float(exc.mean() * TRADING_DAYS / (exc.std() * np.sqrt(TRADING_DAYS)))
            if exc.std() and exc.std() > 0
            else np.nan
        )

        betas.append(beta)
        tes.append(te)
        irs.append(ir)
        dates.append(chunk["date"].iloc[-1])

    if not dates:
        return pd.DataFrame()

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "beta": betas,
            "tracking_error_pct": tes,
            "information_ratio": irs,
        }
    )
    return out


def summarize_benchmark_risk(risk_series: pd.DataFrame) -> BenchmarkRiskSummary:
    """Ostatnie dostępne wartości rolling beta / TE / IR."""
    empty = BenchmarkRiskSummary(
        beta=None, tracking_error_pct=None, information_ratio=None, has_data=False
    )
    if risk_series is None or risk_series.empty:
        return empty

    last = risk_series.dropna(subset=["beta"]).iloc[-1] if "beta" in risk_series.columns else None
    if last is None:
        return empty

    return BenchmarkRiskSummary(
        beta=float(last["beta"]) if pd.notna(last.get("beta")) else None,
        tracking_error_pct=(
            float(last["tracking_error_pct"])
            if pd.notna(last.get("tracking_error_pct"))
            else None
        ),
        information_ratio=(
            float(last["information_ratio"])
            if pd.notna(last.get("information_ratio"))
            else None
        ),
        has_data=True,
    )
