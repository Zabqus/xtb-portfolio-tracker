"""Trwałe preferencje użytkownika (motyw itd.) — plik lokalny jak watchlist.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREFERENCES_PATH = PROJECT_ROOT / "user_preferences.json"


def load_preferences() -> dict[str, Any]:
    if not PREFERENCES_PATH.exists():
        return {}
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_preference(key: str, value: Any) -> None:
    prefs = load_preferences()
    prefs[key] = value
    PREFERENCES_PATH.write_text(
        json.dumps(prefs, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
