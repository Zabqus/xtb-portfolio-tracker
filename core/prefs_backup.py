"""
Backup / restore lokalnych plików preferencji (zip, bez chmury).
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BACKUP_FILENAMES: tuple[str, ...] = (
    "watchlist.json",
    "price_alerts.json",
    "trade_tags.json",
    "snapshots.json",
    "ticker_overrides.json",
    "tax_loss_carry.json",
    "user_preferences.json",
    "ike_ikze_contributions.json",
    "consensus_snapshots.json",
    "signal_snapshots.json",
)


def list_existing_pref_files() -> list[Path]:
    return [PROJECT_ROOT / name for name in BACKUP_FILENAMES if (PROJECT_ROOT / name).exists()]


def export_prefs_zip() -> bytes:
    """Pakuje istniejące pliki preferencji do ZIP (w pamięci)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in list_existing_pref_files():
            zf.write(path, arcname=path.name)
        meta = (
            f"exported_utc={datetime.now(timezone.utc).isoformat()}\n"
            f"files={','.join(p.name for p in list_existing_pref_files())}\n"
        )
        zf.writestr("backup_meta.txt", meta)
    return buf.getvalue()


def default_backup_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"xtb_prefs_backup_{stamp}.zip"


def import_prefs_zip(data: bytes, *, overwrite: bool = True) -> list[str]:
    """
    Przywraca pliki z ZIP. Zwraca listę przywróconych nazw.

    Ignoruje ścieżki poza korzeniem projektu (tylko basename z allowlisty).
    """
    restored: list[str] = []
    allowed = set(BACKUP_FILENAMES)
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if name not in allowed or info.is_dir():
                continue
            target = PROJECT_ROOT / name
            if target.exists() and not overwrite:
                continue
            target.write_bytes(zf.read(info))
            restored.append(name)
    return restored
