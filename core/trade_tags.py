"""
Trwały zapis tagów round-tripów (entry/exit) — plik lokalny trade_tags.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRADE_TAGS_PATH = PROJECT_ROOT / "trade_tags.json"

DEFAULT_ENTRY_TAG = "other"
DEFAULT_EXIT_TAG = "other"


def make_trip_id(row: pd.Series) -> str:
    """Stabilny identyfikator round-tripu do mapowania tagów między sesjami."""
    open_t = pd.Timestamp(row["open_time"]).isoformat()
    close_t = pd.Timestamp(row["close_time"]).isoformat()
    qty = float(row["quantity"])
    return f"{row['ticker_xtb']}|{open_t}|{close_t}|{qty:.8f}"


def load_trade_tags() -> dict[str, dict[str, str]]:
    if not TRADE_TAGS_PATH.exists():
        return {}
    try:
        data = json.loads(TRADE_TAGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    tags = data.get("tags", data) if isinstance(data, dict) else {}
    return tags if isinstance(tags, dict) else {}


def save_trade_tags(tags: dict[str, dict[str, str]]) -> None:
    payload = {"tags": tags, "saved_at": datetime.now(timezone.utc).isoformat()}
    TRADE_TAGS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def merge_tags_into_round_trips(
    round_trips: pd.DataFrame,
    *,
    default_entry_tag: str = DEFAULT_ENTRY_TAG,
    default_exit_tag: str = DEFAULT_EXIT_TAG,
) -> pd.DataFrame:
    """Łączy round-tripy z tagami wczytanymi z pliku."""
    if round_trips is None or round_trips.empty:
        return pd.DataFrame()

    df = round_trips.copy()
    df["trip_id"] = df.apply(make_trip_id, axis=1)
    saved = load_trade_tags()

    entry_tags: list[str] = []
    exit_tags: list[str] = []
    for trip_id in df["trip_id"]:
        meta = saved.get(trip_id, {})
        entry_tags.append(str(meta.get("entry_tag", default_entry_tag) or default_entry_tag))
        exit_tags.append(str(meta.get("exit_tag", default_exit_tag) or default_exit_tag))

    df["entry_tag"] = entry_tags
    df["exit_tag"] = exit_tags
    return df


def persist_tags_from_dataframe(
    edited: pd.DataFrame,
    *,
    trip_id_col: str = "trip_id",
    entry_col: str = "entry_tag",
    exit_col: str = "exit_tag",
) -> int:
    """Zapisuje tagi z edytowanej tabeli. Zwraca liczbę zaktualizowanych wpisów."""
    if edited is None or edited.empty or trip_id_col not in edited.columns:
        return 0

    saved = load_trade_tags()
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for _, row in edited.iterrows():
        trip_id = str(row[trip_id_col])
        if not trip_id:
            continue
        entry = str(row.get(entry_col, DEFAULT_ENTRY_TAG)).strip() or DEFAULT_ENTRY_TAG
        exit_tag = str(row.get(exit_col, DEFAULT_EXIT_TAG)).strip() or DEFAULT_EXIT_TAG
        prev = saved.get(trip_id, {})
        if prev.get("entry_tag") == entry and prev.get("exit_tag") == exit_tag:
            continue
        saved[trip_id] = {
            "entry_tag": entry,
            "exit_tag": exit_tag,
            "updated_at": now,
        }
        updated += 1

    if updated:
        save_trade_tags(saved)
    return updated
