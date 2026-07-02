"""
Snapshoty konsensusu analityków — porównanie ratingów w czasie (momentum, rozkład).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from core.analyst_consensus import normalize_rating_key, rating_bucket

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONSENSUS_SNAPSHOTS_PATH = PROJECT_ROOT / "consensus_snapshots.json"


def load_consensus_snapshots() -> list[dict]:
    if not CONSENSUS_SNAPSHOTS_PATH.exists():
        return []
    try:
        return json.loads(CONSENSUS_SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_consensus_snapshots(snapshots: list[dict]) -> None:
    CONSENSUS_SNAPSHOTS_PATH.write_text(
        json.dumps(snapshots, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_consensus_snapshot(consensus_df: pd.DataFrame) -> dict[str, dict]:
    """Stan konsensusu: ticker → rating_key, bucket, upside, waga."""
    if consensus_df is None or consensus_df.empty:
        return {}

    snap: dict[str, dict] = {}
    for _, row in consensus_df.iterrows():
        ticker = str(row.get("Ticker", ""))
        if not ticker:
            continue
        rating_key = normalize_rating_key(row.get("_rating_key") or row.get("rating_key"))
        snap[ticker] = {
            "rating_key": rating_key or None,
            "rating_bucket": rating_bucket(rating_key),
            "upside_pct": row.get("Upside %"),
            "weight_pct": row.get("weight_pct"),
        }
    return snap


def add_consensus_snapshot(
    consensus_df: pd.DataFrame,
    *,
    snapshot_date: str | None = None,
) -> tuple[bool, str]:
    """Dodaje lub nadpisuje snapshot z danego dnia."""
    today = snapshot_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    positions = build_consensus_snapshot(consensus_df)
    if not positions:
        return False, "Brak danych konsensusu do zapisania."

    record = {"date": today, "positions": positions}
    snapshots = load_consensus_snapshots()
    existing_idx = next(
        (i for i, s in enumerate(snapshots) if s.get("date") == today),
        None,
    )
    if existing_idx is not None:
        snapshots[existing_idx] = record
        save_consensus_snapshots(snapshots)
        return False, f"Zaktualizowano snapshot konsensusu z dnia {today}."

    snapshots.append(record)
    snapshots.sort(key=lambda s: s.get("date", ""))
    save_consensus_snapshots(snapshots)
    return True, f"Zapisano snapshot konsensusu z dnia {today}."


def latest_consensus_snapshot() -> dict | None:
    snapshots = load_consensus_snapshots()
    if not snapshots:
        return None
    return snapshots[-1]


def consensus_snapshot_days_ago(days: int = 30) -> dict | None:
    """Najbliższy snapshot sprzed co najmniej `days` dni (do porównania m/m)."""
    snapshots = load_consensus_snapshots()
    if not snapshots:
        return None

    target = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=days)
    candidates = [
        s for s in snapshots
        if pd.Timestamp(s.get("date", "1970-01-01")) <= target
    ]
    if not candidates:
        return snapshots[0] if len(snapshots) > 1 else None
    return candidates[-1]


def rating_distribution_weights(
    consensus_df: pd.DataFrame,
    *,
    weight_col: str = "weight_pct",
) -> dict[str, float]:
    """Udział wagowy portfela wg bucketu ratingu (Kupno / Trzymaj / Sprzedaj)."""
    if consensus_df is None or consensus_df.empty:
        return {}

    df = consensus_df.dropna(subset=[weight_col]).copy()
    if df.empty:
        return {}

    if "rating_bucket" not in df.columns:
        df["rating_bucket"] = df["_rating_key"].map(
            lambda k: rating_bucket(k) if pd.notna(k) else None
        )

    grouped = (
        df.dropna(subset=["rating_bucket"])
        .groupby("rating_bucket", as_index=False)[weight_col]
        .sum()
    )
    total = float(grouped[weight_col].sum())
    if total <= 0:
        return {}
    return {
        str(row["rating_bucket"]): float(row[weight_col]) / total * 100
        for _, row in grouped.iterrows()
    }


def snapshot_rating_distribution(snapshot: dict | None) -> dict[str, float]:
    if not snapshot:
        return {}
    positions = snapshot.get("positions") or {}
    buckets: dict[str, float] = {"Kupno": 0.0, "Trzymaj": 0.0, "Sprzedaj": 0.0}
    for data in positions.values():
        bucket = data.get("rating_bucket")
        weight = data.get("weight_pct")
        if bucket and weight is not None and not pd.isna(weight):
            buckets[bucket] = buckets.get(bucket, 0.0) + float(weight)

    total = sum(buckets.values())
    if total <= 0:
        return {}
    return {k: v / total * 100 for k, v in buckets.items() if v > 0}
