"""
Przenoszenie straty kapitałowej (PL): do 5 lat, max 50% danej straty rocznie.

Ledżer lokalny: tax_loss_carry.json (jak watchlist / preferencje).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARRY_PATH = PROJECT_ROOT / "tax_loss_carry.json"
MAX_CARRY_YEARS = 5
MAX_ANNUAL_FRACTION = 0.50


@dataclass
class CarryEntry:
    """Strata powstała w origin_year (kwota dodatnia = wielkość straty)."""

    origin_year: int
    original_loss: float
    used_so_far: float = 0.0
    note: str = ""

    @property
    def remaining(self) -> float:
        return max(0.0, float(self.original_loss) - float(self.used_so_far))

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin_year": int(self.origin_year),
            "original_loss": float(self.original_loss),
            "used_so_far": float(self.used_so_far),
            "note": str(self.note or ""),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CarryEntry | None:
        try:
            origin = int(raw["origin_year"])
            loss = float(raw["original_loss"])
        except (KeyError, TypeError, ValueError):
            return None
        if loss <= 0:
            return None
        used = float(raw.get("used_so_far") or 0.0)
        return cls(
            origin_year=origin,
            original_loss=loss,
            used_so_far=max(0.0, min(used, loss)),
            note=str(raw.get("note") or ""),
        )


@dataclass
class CarryApplication:
    tax_year: int
    positive_gain: float
    applied: float
    base_after: float
    details: list[dict[str, float | int]] = field(default_factory=list)
    updated_entries: list[CarryEntry] = field(default_factory=list)


def load_carry_entries() -> list[CarryEntry]:
    if not CARRY_PATH.exists():
        return []
    try:
        data = json.loads(CARRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    raw_list = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        return []
    out: list[CarryEntry] = []
    for item in raw_list:
        if isinstance(item, dict):
            entry = CarryEntry.from_dict(item)
            if entry is not None:
                out.append(entry)
    return sorted(out, key=lambda e: e.origin_year)


def save_carry_entries(entries: list[CarryEntry]) -> None:
    payload = {"entries": [e.to_dict() for e in entries]}
    CARRY_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def upsert_carry_loss(origin_year: int, loss_amount: float, note: str = "") -> list[CarryEntry]:
    """Dodaje lub nadpisuje stratę z danego roku (kwota dodatnia)."""
    loss = abs(float(loss_amount))
    entries = load_carry_entries()
    replaced = False
    for entry in entries:
        if entry.origin_year == int(origin_year):
            entry.original_loss = loss
            entry.used_so_far = min(entry.used_so_far, loss)
            if note:
                entry.note = note
            replaced = True
            break
    if not replaced:
        entries.append(
            CarryEntry(origin_year=int(origin_year), original_loss=loss, note=note)
        )
    entries = sorted(entries, key=lambda e: e.origin_year)
    save_carry_entries(entries)
    return entries


def delete_carry_year(origin_year: int) -> list[CarryEntry]:
    entries = [e for e in load_carry_entries() if e.origin_year != int(origin_year)]
    save_carry_entries(entries)
    return entries


def eligible_for_year(entry: CarryEntry, tax_year: int) -> bool:
    """Strata z origin_year rozliczana w latach origin+1 … origin+5."""
    delta = int(tax_year) - int(entry.origin_year)
    return 1 <= delta <= MAX_CARRY_YEARS and entry.remaining > 0


def max_deductible_this_year(entry: CarryEntry) -> float:
    """Max 50% oryginalnej straty w jednym roku, nie więcej niż pozostało."""
    annual_cap = float(entry.original_loss) * MAX_ANNUAL_FRACTION
    return min(entry.remaining, annual_cap)


def apply_carry_forward(
    tax_year: int,
    capital_net: float,
    entries: list[CarryEntry] | None = None,
    *,
    persist: bool = False,
) -> CarryApplication:
    """
    Pomniejsza dodatnią podstawę zysków kapitałowych o straty z lat ubiegłych.

    Nie mutuje pliku, chyba że persist=True (zapisuje updated used_so_far).
    """
    source: list[CarryEntry] = []
    for e in (entries if entries is not None else load_carry_entries()):
        source.append(
            CarryEntry(
                origin_year=e.origin_year,
                original_loss=e.original_loss,
                used_so_far=e.used_so_far,
                note=e.note,
            )
        )

    positive = max(0.0, float(capital_net))
    remaining_gain = positive
    applied_total = 0.0
    details: list[dict[str, float | int]] = []

    for entry in sorted(source, key=lambda e: e.origin_year):
        if remaining_gain <= 0:
            break
        if not eligible_for_year(entry, tax_year):
            continue
        take = min(max_deductible_this_year(entry), remaining_gain)
        if take <= 0:
            continue
        entry.used_so_far += take
        remaining_gain -= take
        applied_total += take
        details.append(
            {
                "origin_year": entry.origin_year,
                "applied": round(take, 2),
                "remaining_after": round(entry.remaining, 2),
            }
        )

    if persist:
        save_carry_entries(source)

    return CarryApplication(
        tax_year=int(tax_year),
        positive_gain=positive,
        applied=applied_total,
        base_after=float(capital_net) - applied_total if capital_net > 0 else float(capital_net),
        details=details,
        updated_entries=source,
    )
