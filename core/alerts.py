"""
Alerty pozycji — próg ±X% względem średniej ceny zakupu (ROI %).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd

PRICE_ALERTS_FILE = Path("price_alerts.json")


@dataclass
class PriceAlert:
    ticker_xtb: str
    ticker_yahoo: str
    direction: str  # "above" | "below"
    target_price: float
    note: str = ""


def load_price_alerts() -> list[PriceAlert]:
    """Wczytuje alerty cenowe z lokalnego pliku JSON."""
    if not PRICE_ALERTS_FILE.exists():
        return []
    try:
        data = json.loads(PRICE_ALERTS_FILE.read_text(encoding="utf-8"))
        return [PriceAlert(**item) for item in data]
    except Exception:
        return []


def save_price_alerts(alerts: list[PriceAlert]) -> None:
    """Zapisuje alerty cenowe do lokalnego pliku JSON."""
    PRICE_ALERTS_FILE.write_text(
        json.dumps([vars(a) for a in alerts], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def check_price_alerts(
    alerts: list[PriceAlert],
    analyzed: pd.DataFrame,
) -> pd.DataFrame:
    """Sprawdza które alerty cenowe zostały wyzwolone."""
    price_map = dict(zip(analyzed["ticker_xtb"], analyzed["market_price"]))
    triggered = []
    for a in alerts:
        current = price_map.get(a.ticker_xtb)
        if current is None or pd.isna(current):
            continue
        hit = (a.direction == "above" and current >= a.target_price) or (
            a.direction == "below" and current <= a.target_price
        )
        triggered.append(
            {
                "ticker_xtb": a.ticker_xtb,
                "kierunek": "↑ Powyżej" if a.direction == "above" else "↓ Poniżej",
                "cel": a.target_price,
                "aktualna": round(float(current), 4),
                "różnica": round(float(current) - a.target_price, 4),
                "wyzwolony": hit,
                "notatka": a.note,
            }
        )
    return pd.DataFrame(triggered)


def compute_roi_alerts(
    analyzed: pd.DataFrame,
    threshold_pct: float,
    *,
    direction: str = "both",
) -> pd.DataFrame:
    """
    Zwraca pozycje przekraczające próg |ROI %| względem kosztu pozycji.

    direction: both | gain | loss
    """
    if analyzed is None or analyzed.empty:
        return pd.DataFrame()

    threshold = abs(float(threshold_pct))
    valid = analyzed.dropna(subset=["roi_pct", "ticker_xtb"]).copy()
    if valid.empty:
        return pd.DataFrame()

    roi = valid["roi_pct"].astype(float)
    if direction == "gain":
        mask = roi >= threshold
    elif direction == "loss":
        mask = roi <= -threshold
    else:
        mask = roi.abs() >= threshold

    triggered = valid.loc[mask].copy()
    if triggered.empty:
        return triggered

    triggered["alert_type"] = triggered["roi_pct"].map(
        lambda x: "Zysk" if float(x) >= 0 else "Strata"
    )
    triggered["przekroczenie_pp"] = triggered["roi_pct"].abs() - threshold
    return triggered.assign(_abs=triggered["roi_pct"].abs()).sort_values(
        "_abs", ascending=False
    ).drop(columns="_abs")


def compute_roi_deltas(
    analyzed: pd.DataFrame,
    snapshot: dict[str, float] | None,
    threshold_pct: float,
) -> pd.DataFrame:
    """
    Alerty na zmianę ROI od ostatniego odświeżenia (snapshot ticker_xtb → roi_pct).
    """
    if analyzed is None or analyzed.empty or not snapshot:
        return pd.DataFrame()

    threshold = abs(float(threshold_pct))
    rows: list[dict] = []
    for _, row in analyzed.dropna(subset=["roi_pct", "ticker_xtb"]).iterrows():
        key = str(row["ticker_xtb"])
        prev = snapshot.get(key)
        if prev is None or pd.isna(prev):
            continue
        curr = float(row["roi_pct"])
        delta = curr - float(prev)
        if abs(delta) < threshold:
            continue
        rows.append(
            {
                "ticker_xtb": key,
                "ticker_yahoo": row.get("ticker_yahoo"),
                "account_label": row.get("account_label"),
                "roi_pct": curr,
                "roi_delta_pp": delta,
                "alert_type": "Wzrost" if delta >= 0 else "Spadek",
            }
        )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.assign(_abs=df["roi_delta_pp"].abs()).sort_values("_abs", ascending=False).drop(
        columns="_abs"
    )


def build_roi_snapshot(analyzed: pd.DataFrame) -> dict[str, float]:
    """Stan ROI do porównania przy następnym odświeżeniu."""
    if analyzed is None or analyzed.empty:
        return {}
    snap: dict[str, float] = {}
    for _, row in analyzed.dropna(subset=["roi_pct", "ticker_xtb"]).iterrows():
        snap[str(row["ticker_xtb"])] = float(row["roi_pct"])
    return snap


def alert_row_keys(alerts: pd.DataFrame, mode: str = "roi") -> set[str]:
    """Klucze aktywnych alertów (do oznaczenia „nowych”)."""
    if alerts is None or alerts.empty:
        return set()
    keys: set[str] = set()
    for _, row in alerts.iterrows():
        ticker = str(row.get("ticker_xtb", ""))
        if mode == "delta":
            kind = "up" if float(row.get("roi_delta_pp", 0)) >= 0 else "down"
        else:
            kind = "up" if float(row.get("roi_pct", 0)) >= 0 else "down"
        keys.add(f"{ticker}:{kind}")
    return keys


def mark_new_alerts(alerts: pd.DataFrame, prev_keys: set[str] | None, mode: str = "roi") -> pd.DataFrame:
    """Dodaje kolumnę is_new dla alertów nieobecnych w poprzednim przebiegu."""
    if alerts is None or alerts.empty:
        return alerts
    prev = prev_keys or set()
    current_keys = alert_row_keys(alerts, mode=mode)
    out = alerts.copy()

    def _is_new(row: pd.Series) -> bool:
        ticker = str(row.get("ticker_xtb", ""))
        if mode == "delta":
            kind = "up" if float(row.get("roi_delta_pp", 0)) >= 0 else "down"
        else:
            kind = "up" if float(row.get("roi_pct", 0)) >= 0 else "down"
        key = f"{ticker}:{kind}"
        return key not in prev and key in current_keys

    out["is_new"] = out.apply(_is_new, axis=1)
    return out


def build_triggered_alerts_export(
    roi_alerts: pd.DataFrame | None = None,
    price_hits: pd.DataFrame | None = None,
    *,
    mode: str = "roi",
    threshold_pct: float | None = None,
) -> pd.DataFrame:
    """Jedna tabela do CSV: ROI + cenowe wyzwolone."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rows: list[dict] = []

    if roi_alerts is not None and not roi_alerts.empty:
        for _, r in roi_alerts.iterrows():
            rows.append(
                {
                    "exported_at": stamp,
                    "source": f"roi_{mode}",
                    "ticker_xtb": r.get("ticker_xtb"),
                    "ticker_yahoo": r.get("ticker_yahoo"),
                    "detail": r.get("alert_type"),
                    "roi_pct": r.get("roi_pct"),
                    "roi_delta_pp": r.get("roi_delta_pp"),
                    "threshold_pct": threshold_pct,
                    "is_new": r.get("is_new"),
                    "price": r.get("market_price"),
                    "target": None,
                    "note": "",
                }
            )

    if price_hits is not None and not price_hits.empty:
        hits = price_hits
        if "wyzwolony" in hits.columns:
            hits = hits[hits["wyzwolony"] == True]  # noqa: E712
        for _, r in hits.iterrows():
            rows.append(
                {
                    "exported_at": stamp,
                    "source": "price",
                    "ticker_xtb": r.get("ticker_xtb"),
                    "ticker_yahoo": "",
                    "detail": r.get("kierunek"),
                    "roi_pct": None,
                    "roi_delta_pp": None,
                    "threshold_pct": None,
                    "is_new": True,
                    "price": r.get("aktualna"),
                    "target": r.get("cel"),
                    "note": r.get("notatka", ""),
                }
            )

    return pd.DataFrame(rows)


def triggered_alerts_to_csv(export_df: pd.DataFrame) -> str:
    """CSV (UTF-8 z BOM dla Excela)."""
    if export_df is None or export_df.empty:
        return "exported_at,source,ticker_xtb\n"
    buf = StringIO()
    export_df.to_csv(buf, index=False)
    return "\ufeff" + buf.getvalue()


def default_alerts_csv_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
    return f"xtb_triggered_alerts_{stamp}.csv"


def summarize_new_alerts_for_toast(
    roi_alerts: pd.DataFrame | None,
    price_hits: pd.DataFrame | None,
) -> tuple[str, str] | None:
    """Tytuł + treść toastu dla *nowych* alertów; None gdy brak nowości."""
    parts: list[str] = []
    n_roi = 0
    if roi_alerts is not None and not roi_alerts.empty and "is_new" in roi_alerts.columns:
        new_roi = roi_alerts[roi_alerts["is_new"] == True]  # noqa: E712
        n_roi = len(new_roi)
        for _, r in new_roi.head(5).iterrows():
            roi = r.get("roi_pct")
            roi_s = f"{float(roi):+.1f}%" if pd.notna(roi) else ""
            parts.append(f"{r.get('ticker_xtb')} ROI {roi_s}".strip())

    n_price = 0
    if price_hits is not None and not price_hits.empty:
        hits = price_hits
        if "wyzwolony" in hits.columns:
            hits = hits[hits["wyzwolony"] == True]  # noqa: E712
        n_price = len(hits)
        for _, r in hits.head(5).iterrows():
            parts.append(f"{r.get('ticker_xtb')} {r.get('kierunek')} @ {r.get('cel')}")

    # Toast tylko gdy są nowe ROI; cenowe zawsze gdy wyzwolone (brak is_new w pliku)
    if n_roi == 0 and n_price == 0:
        return None
    if n_roi == 0 and n_price > 0:
        # cenowe: caller powinien filtrować po session keys
        pass

    title = "XTB Portfolio — alerty"
    if n_roi and n_price:
        title = f"XTB: {n_roi} ROI + {n_price} cenowe"
    elif n_roi:
        title = f"XTB: {n_roi} alert(y) ROI"
    elif n_price:
        title = f"XTB: {n_price} alert(y) cenowe"

    body = "; ".join(parts) if parts else "Nowe alerty aktywne"
    return title, body
