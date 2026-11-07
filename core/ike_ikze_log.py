"""
Dziennik wpłat IKE / IKZE vs limity roczne (plik lokalny).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from core.ike_ikze import IKE_LIMIT_2025, IKZE_LIMIT_2025

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "ike_ikze_contributions.json"
ACCOUNT_TYPES = ("IKE", "IKZE")


@dataclass
class ContributionEntry:
    entry_id: str
    account: str  # IKE | IKZE
    amount: float
    date: str  # YYYY-MM-DD
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "account": self.account,
            "amount": float(self.amount),
            "date": self.date,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ContributionEntry | None:
        try:
            account = str(raw.get("account", "")).strip().upper()
            amount = float(raw.get("amount", 0))
            day = str(raw.get("date", ""))[:10]
            if account not in ACCOUNT_TYPES or amount <= 0 or not day:
                return None
            eid = str(raw.get("entry_id") or f"{account}-{day}-{amount}")
            return cls(
                entry_id=eid,
                account=account,
                amount=amount,
                date=day,
                note=str(raw.get("note") or ""),
            )
        except (TypeError, ValueError):
            return None


@dataclass
class YearLimitStatus:
    year: int
    ike_contributed: float
    ikze_contributed: float
    ike_limit: float
    ikze_limit: float

    @property
    def ike_remaining(self) -> float:
        return max(0.0, self.ike_limit - self.ike_contributed)

    @property
    def ikze_remaining(self) -> float:
        return max(0.0, self.ikze_limit - self.ikze_contributed)

    @property
    def ike_pct(self) -> float:
        return (self.ike_contributed / self.ike_limit * 100.0) if self.ike_limit > 0 else 0.0

    @property
    def ikze_pct(self) -> float:
        return (self.ikze_contributed / self.ikze_limit * 100.0) if self.ikze_limit > 0 else 0.0


def load_contributions() -> list[ContributionEntry]:
    if not LOG_PATH.exists():
        return []
    try:
        data = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    out: list[ContributionEntry] = []
    for item in raw:
        if isinstance(item, dict):
            entry = ContributionEntry.from_dict(item)
            if entry:
                out.append(entry)
    return sorted(out, key=lambda e: e.date, reverse=True)


def save_contributions(entries: list[ContributionEntry]) -> None:
    payload = {"entries": [e.to_dict() for e in entries]}
    LOG_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def add_contribution(
    account: str,
    amount: float,
    on_date: date | str | None = None,
    note: str = "",
) -> list[ContributionEntry]:
    day = _as_day(on_date) if on_date is not None else date.today().isoformat()
    acc = str(account).strip().upper()
    if acc not in ACCOUNT_TYPES:
        raise ValueError(f"Konto musi być IKE lub IKZE, dostano: {account}")
    amt = float(amount)
    if amt <= 0:
        raise ValueError("Kwota musi być dodatnia.")

    entries = load_contributions()
    eid = f"{acc}-{day}-{amt:.2f}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    entries.insert(
        0,
        ContributionEntry(entry_id=eid, account=acc, amount=amt, date=day, note=note),
    )
    save_contributions(entries)
    return entries


def delete_contribution(entry_id: str) -> list[ContributionEntry]:
    entries = [e for e in load_contributions() if e.entry_id != entry_id]
    save_contributions(entries)
    return entries


def contributions_dataframe(entries: list[ContributionEntry] | None = None) -> pd.DataFrame:
    rows = entries if entries is not None else load_contributions()
    if not rows:
        return pd.DataFrame(columns=["date", "account", "amount", "note", "entry_id"])
    return pd.DataFrame([e.to_dict() for e in rows])


def year_status(
    year: int,
    *,
    ike_limit: float = IKE_LIMIT_2025,
    ikze_limit: float = IKZE_LIMIT_2025,
    entries: list[ContributionEntry] | None = None,
) -> YearLimitStatus:
    rows = entries if entries is not None else load_contributions()
    ike = 0.0
    ikze = 0.0
    for e in rows:
        try:
            y = int(str(e.date)[:4])
        except ValueError:
            continue
        if y != int(year):
            continue
        if e.account == "IKE":
            ike += e.amount
        elif e.account == "IKZE":
            ikze += e.amount
    return YearLimitStatus(
        year=int(year),
        ike_contributed=ike,
        ikze_contributed=ikze,
        ike_limit=float(ike_limit),
        ikze_limit=float(ikze_limit),
    )


def _as_day(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]
