"""
Analiza zamkniętych pozycji – najlepsze i najgorsze transakcje.
"""

from __future__ import annotations

import pandas as pd


def closed_positions_summary(closed: pd.DataFrame) -> dict[str, float | int]:
    if closed is None or closed.empty or "pnl" not in closed.columns:
        return {
            "count": 0,
            "total_pnl": 0.0,
            "winners": 0,
            "losers": 0,
            "win_rate_pct": 0.0,
            "avg_pnl": 0.0,
        }

    pnl = closed["pnl"].dropna()
    winners = int((pnl > 0).sum())
    losers = int((pnl < 0).sum())

    return {
        "count": len(closed),
        "total_pnl": float(pnl.sum()),
        "winners": winners,
        "losers": losers,
        "win_rate_pct": float(winners / len(pnl) * 100) if len(pnl) else 0.0,
        "avg_pnl": float(pnl.mean()) if len(pnl) else 0.0,
    }


def get_top_trades(closed: pd.DataFrame, n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Zwraca (najlepsze, najgorsze) transakcje wg kolumny pnl."""
    if closed is None or closed.empty or "pnl" not in closed.columns:
        return pd.DataFrame(), pd.DataFrame()

    valid = closed.dropna(subset=["pnl", "ticker_xtb"]).copy()
    if valid.empty:
        return pd.DataFrame(), pd.DataFrame()

    best = valid.nlargest(n, "pnl")
    worst = valid.nsmallest(n, "pnl")
    return best, worst
