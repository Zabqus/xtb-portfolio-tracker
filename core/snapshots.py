"""
Lokalne snapshoty portfela – własny timeline wartości niezależny od Cash Operations.

Każdy zapis to stan portfela w danym dniu (wartość, koszt, PnL, pozycje), trzymany
w `snapshots.json` obok `watchlist.json`. Pozwala śledzić wartość w czasie nawet
dla uproszczonego importu CSV (bez arkusza Cash Operations).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_PATH = PROJECT_ROOT / "snapshots.json"


def load_snapshots() -> list[dict]:
    """Wczytuje listę snapshotów (puste, gdy brak pliku lub błąd)."""
    if not SNAPSHOTS_PATH.exists():
        return []
    try:
        data = json.loads(SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def save_snapshots(snapshots: list[dict]) -> None:
    SNAPSHOTS_PATH.write_text(
        json.dumps(snapshots, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _positions_payload(analyzed: pd.DataFrame | None) -> list[dict]:
    if analyzed is None or analyzed.empty:
        return []
    cols = {
        "ticker_xtb": "ticker",
        "market_value": "value",
        "pnl": "pnl",
        "roi_pct": "roi_pct",
    }
    present = {k: v for k, v in cols.items() if k in analyzed.columns}
    out: list[dict] = []
    for _, row in analyzed.iterrows():
        rec: dict = {}
        for src, dst in present.items():
            val = row.get(src)
            if pd.isna(val):
                rec[dst] = None
            else:
                rec[dst] = float(val) if dst != "ticker" else str(val)
        out.append(rec)
    return out


def add_snapshot(
    summary: dict,
    currency: str,
    analyzed: pd.DataFrame | None = None,
    *,
    snapshot_date: str | None = None,
) -> tuple[bool, str]:
    """
    Dodaje (lub nadpisuje istniejący z tego samego dnia) snapshot portfela.

    summary: wynik core.analyzer.portfolio_summary.
    Zwraca (czy_nowy, komunikat).
    """
    today = snapshot_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    record = {
        "date": today,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "currency": currency,
        "total_value": float(summary.get("total_value", 0.0) or 0.0),
        "total_cost": float(summary.get("total_cost", 0.0) or 0.0),
        "total_pnl": float(summary.get("total_pnl", 0.0) or 0.0),
        "roi_pct": float(summary.get("total_roi_pct", 0.0) or 0.0),
        "positions": _positions_payload(analyzed),
    }

    snapshots = load_snapshots()
    existing_idx = next(
        (i for i, s in enumerate(snapshots) if s.get("date") == today and s.get("currency") == currency),
        None,
    )
    if existing_idx is not None:
        snapshots[existing_idx] = record
        save_snapshots(snapshots)
        return False, f"Zaktualizowano snapshot z dnia {today} ({currency})."

    snapshots.append(record)
    snapshots.sort(key=lambda s: s.get("date", ""))
    save_snapshots(snapshots)
    return True, f"Zapisano snapshot z dnia {today} ({currency})."


def delete_snapshot(date: str, currency: str) -> None:
    snapshots = [
        s for s in load_snapshots()
        if not (s.get("date") == date and s.get("currency") == currency)
    ]
    save_snapshots(snapshots)


def clear_snapshots() -> None:
    save_snapshots([])


def snapshots_to_df(currency: str | None = None) -> pd.DataFrame:
    """
    Snapshoty jako DataFrame (date, total_value, total_cost, total_pnl, roi_pct,
    currency, positions_count). Opcjonalnie filtruje po walucie.
    """
    snapshots = load_snapshots()
    if not snapshots:
        return pd.DataFrame()

    rows: list[dict] = []
    for s in snapshots:
        if currency is not None and s.get("currency") != currency:
            continue
        rows.append(
            {
                "date": pd.to_datetime(s.get("date"), errors="coerce"),
                "total_value": s.get("total_value"),
                "total_cost": s.get("total_cost"),
                "total_pnl": s.get("total_pnl"),
                "roi_pct": s.get("roi_pct"),
                "currency": s.get("currency"),
                "positions_count": len(s.get("positions", [])),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def available_currencies() -> list[str]:
    """Waluty występujące w zapisanych snapshotach."""
    return sorted({str(s.get("currency")) for s in load_snapshots() if s.get("currency")})
