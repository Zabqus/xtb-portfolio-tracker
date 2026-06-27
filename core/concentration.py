"""
Metryki koncentracji portfela: HHI, Top-N, effective number of positions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.snapshots import load_snapshots


@dataclass
class ConcentrationMetrics:
    hhi: float
    top5_pct: float
    top10_pct: float
    effective_n: float
    position_count: int
    top_weights: pd.DataFrame  # ticker, weight_pct


def _hhi_from_fractions(fractions: list[float]) -> float:
    if not fractions:
        return 0.0
    return float(sum(f * f for f in fractions))


def compute_concentration_metrics(enriched: pd.DataFrame, top_n: int = 10) -> ConcentrationMetrics:
    """
    HHI i udziały Top-N z wzbogaconego DataFrame (kolumny: ticker_xtb, weight_pct).
    """
    empty = ConcentrationMetrics(
        hhi=0.0,
        top5_pct=0.0,
        top10_pct=0.0,
        effective_n=0.0,
        position_count=0,
        top_weights=pd.DataFrame(columns=["ticker", "weight_pct"]),
    )
    if enriched is None or enriched.empty or "weight_pct" not in enriched.columns:
        return empty

    df = enriched.dropna(subset=["weight_pct"]).copy()
    df = df[df["weight_pct"] > 0].sort_values("weight_pct", ascending=False)
    if df.empty:
        return empty

    fractions = (df["weight_pct"] / 100.0).tolist()
    hhi = _hhi_from_fractions(fractions)
    top5 = float(df["weight_pct"].head(5).sum())
    top10 = float(df["weight_pct"].head(10).sum())
    eff_n = 1.0 / hhi if hhi > 0 else float(len(df))

    label = "ticker_xtb" if "ticker_xtb" in df.columns else "ticker_yahoo"
    top_weights = df.head(top_n)[[label, "weight_pct"]].rename(
        columns={label: "ticker"}
    ).reset_index(drop=True)

    return ConcentrationMetrics(
        hhi=hhi,
        top5_pct=top5,
        top10_pct=top10,
        effective_n=eff_n,
        position_count=len(df),
        top_weights=top_weights,
    )


def concentration_history_from_snapshots(
    currency: str | None = None,
) -> pd.DataFrame:
    """
    HHI i Top-5 w czasie na podstawie zapisanych snapshotów.

    Kolumny: date, hhi, top5_pct, top10_pct, effective_n, position_count.
    """
    snapshots = load_snapshots()
    rows: list[dict] = []
    for snap in snapshots:
        if currency is not None and snap.get("currency") != currency:
            continue
        positions = snap.get("positions") or []
        values = [float(p["value"]) for p in positions if p.get("value") is not None]
        if not values:
            continue
        total = sum(values)
        if total <= 0:
            continue
        fractions = sorted((v / total for v in values), reverse=True)
        hhi = _hhi_from_fractions(fractions)
        top5 = sum(fractions[:5]) * 100
        top10 = sum(fractions[:10]) * 100
        rows.append(
            {
                "date": pd.to_datetime(snap.get("date"), errors="coerce"),
                "hhi": hhi,
                "top5_pct": top5,
                "top10_pct": top10,
                "effective_n": 1.0 / hhi if hhi > 0 else len(fractions),
                "position_count": len(fractions),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
