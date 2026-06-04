"""
Alerty pozycji — próg ±X% względem średniej ceny zakupu (ROI %).
"""

from __future__ import annotations

import pandas as pd


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
