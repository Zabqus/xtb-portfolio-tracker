"""
Snapshoty sygnałów — score, sygnał i zgoda interwałów w czasie.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIGNAL_SNAPSHOTS_PATH = PROJECT_ROOT / "signal_snapshots.json"


def load_signal_snapshots() -> list[dict]:
    if not SIGNAL_SNAPSHOTS_PATH.exists():
        return []
    try:
        return json.loads(SIGNAL_SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_signal_snapshots(snapshots: list[dict]) -> None:
    SIGNAL_SNAPSHOTS_PATH.write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_signal_snapshot(signal_df: pd.DataFrame) -> dict[str, dict]:
    """
    Stan sygnałów: ticker -> score/sygnał/zgoda interwałów.
    """
    if signal_df is None or signal_df.empty:
        return {}
    snap: dict[str, dict] = {}
    for _, row in signal_df.iterrows():
        ticker = str(row.get("ticker_xtb") or row.get("Ticker") or "")
        if not ticker:
            continue
        snap[ticker] = {
            "score_total": row.get("score_total"),
            "signal": row.get("signal") or row.get("Sygnał"),
            "interval_agreement": row.get("interval_agreement"),
        }
    return snap


def add_signal_snapshot(
    signal_df: pd.DataFrame,
    *,
    snapshot_date: str | None = None,
) -> tuple[bool, str]:
    today = snapshot_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    positions = build_signal_snapshot(signal_df)
    if not positions:
        return False, "Brak danych sygnałów do zapisania."

    record = {"date": today, "positions": positions}
    snapshots = load_signal_snapshots()
    existing_idx = next((i for i, s in enumerate(snapshots) if s.get("date") == today), None)
    if existing_idx is not None:
        snapshots[existing_idx] = record
        save_signal_snapshots(snapshots)
        return False, f"Zaktualizowano snapshot sygnałów z dnia {today}."

    snapshots.append(record)
    snapshots.sort(key=lambda s: s.get("date", ""))
    save_signal_snapshots(snapshots)
    return True, f"Zapisano snapshot sygnałów z dnia {today}."


def latest_signal_snapshot() -> dict | None:
    snaps = load_signal_snapshots()
    return snaps[-1] if snaps else None


def signal_snapshot_days_ago(days: int) -> dict | None:
    snaps = load_signal_snapshots()
    if not snaps:
        return None
    target = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=days)
    candidates = [s for s in snaps if pd.Timestamp(s.get("date", "1970-01-01")) <= target]
    if not candidates:
        return None
    return candidates[-1]


def detect_signal_alerts(current_df: pd.DataFrame, previous_snapshot: dict | None) -> pd.DataFrame:
    """
    Alerty przekroczeń:
    - zmiana sygnału (np. HOLD -> SELL),
    - przekroczenie 7.0,
    - zmiana zgody interwałów na Mieszany.
    """
    if current_df is None or current_df.empty:
        return pd.DataFrame()
    prev_positions = (previous_snapshot or {}).get("positions") or {}
    rows: list[dict] = []
    for _, row in current_df.iterrows():
        ticker = str(row.get("ticker_xtb") or "")
        if not ticker:
            continue
        prev = prev_positions.get(ticker, {})
        curr_score = row.get("score_total")
        prev_score = prev.get("score_total")
        curr_signal = row.get("signal")
        prev_signal = prev.get("signal")
        curr_agree = row.get("interval_agreement")
        prev_agree = prev.get("interval_agreement")

        if prev_signal and curr_signal and prev_signal != curr_signal:
            rows.append(
                {
                    "ticker_xtb": ticker,
                    "typ": "Zmiana sygnału",
                    "alert": f"{prev_signal} → {curr_signal}",
                }
            )
        if (
            curr_score is not None
            and prev_score is not None
            and not pd.isna(curr_score)
            and not pd.isna(prev_score)
            and float(prev_score) < 7.0 <= float(curr_score)
        ):
            rows.append(
                {
                    "ticker_xtb": ticker,
                    "typ": "Przebicie progu",
                    "alert": "Score przebił 7.0",
                }
            )
        if prev_agree and curr_agree and prev_agree != "Mieszany" and curr_agree == "Mieszany":
            rows.append(
                {
                    "ticker_xtb": ticker,
                    "typ": "Zgoda interwałów",
                    "alert": f"{prev_agree} → Mieszany",
                }
            )
    return pd.DataFrame(rows)
