"""
Sygnały kup / trzymaj / sprzedaj — heurystyka łącząca analizę techniczną,
konsensus analityków i bieżący P&L pozycji.

Składniki wyniku (skala 0–10):
* Technika  (waga 40%, 0–4)
* Konsensus (waga 40%, 0–4)
* P&L       (waga 20%, 0–2)

Sygnały to wyłącznie heurystyki pomocnicze, nie stanowią porady inwestycyjnej.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.analyst_consensus import AnalystConsensus, format_recommendation

SIGNAL_BUY = "Kup więcej"
SIGNAL_HOLD = "Trzymaj"
SIGNAL_SELL = "Rozważ sprzedaż"

SIGNAL_COLORS: dict[str, str] = {
    SIGNAL_BUY: "#2ecc71",
    SIGNAL_HOLD: "#f39c12",
    SIGNAL_SELL: "#e74c3c",
}


@dataclass
class SignalResult:
    ticker_xtb: str
    roi_pct: float | None
    technical_score: float
    consensus_score: float
    pl_score: float
    signal_score: float
    signal: str
    color: str
    trend_ma200: str
    rsi: float | None
    rating: str
    upside_pct: float | None
    comment: str


def _normalize(raw: float, raw_max: float, target_max: float) -> float:
    if raw_max <= 0:
        return 0.0
    return max(0.0, min(target_max, raw / raw_max * target_max))


def technical_score(snapshot: dict) -> tuple[float, str, str, float | None]:
    """
    Zwraca (score 0–4, opis MA200, opis RSI, wartość RSI).

    Surowy wynik (max 7): MA200 (1–3) + MA50 (0.5–2) + RSI (0.5–2.5),
    znormalizowany do 0–4.
    """
    if not snapshot:
        return 2.0, "—", "—", None

    close = snapshot.get("close")
    ma50 = snapshot.get("ma50")
    ma200 = snapshot.get("ma200")
    rsi = snapshot.get("rsi")

    raw = 0.0

    if close is not None and ma200 is not None:
        raw += 3.0 if close > ma200 else 1.0
        trend = "MA200 ▲" if close > ma200 else "MA200 ▼"
    else:
        raw += 2.0
        trend = "MA200 —"

    if close is not None and ma50 is not None:
        raw += 2.0 if close > ma50 else 0.5

    if rsi is None:
        raw += 1.0
        rsi_desc = "RSI —"
    else:
        if rsi < 30:
            raw += 2.5
        elif rsi < 40:
            raw += 1.5
        elif rsi <= 60:
            raw += 2.0
        elif rsi <= 70:
            raw += 1.5
        else:
            raw += 0.5
        rsi_desc = f"RSI {rsi:.0f}"

    return _normalize(raw, 7.0, 4.0), trend, rsi_desc, rsi


def consensus_score(
    consensus: AnalystConsensus | None,
    upside_pct: float | None,
) -> tuple[float, str]:
    """
    Zwraca (score 0–4, etykieta ratingu).

    Surowy wynik (max ~5): baza z rekomendacji (0–4) + bonus/kara z upside,
    znormalizowany do 0–4.
    """
    key = (consensus.recommendation_key if consensus else None) or ""
    k = key.strip().lower().replace(" ", "_")

    base_map = {
        "strong_buy": 4.0,
        "buy": 3.0,
        "hold": 2.0,
        "underperform": 1.0,
        "sell": 1.0,
        "strong_sell": 0.0,
    }
    raw = base_map.get(k, 2.0)  # brak danych → neutralnie

    if upside_pct is not None:
        if upside_pct > 20:
            raw += 1.0
        elif upside_pct > 10:
            raw += 0.5
        elif upside_pct < 0:
            raw -= 1.0

    rating = format_recommendation(consensus.recommendation_key if consensus else None)
    return _normalize(raw, 5.0, 4.0), rating


def pl_score(roi_pct: float | None) -> float:
    """Wynik z bieżącego P&L pozycji (max 2)."""
    if roi_pct is None or pd.isna(roi_pct):
        return 1.5
    if roi_pct > 15:
        return 2.0
    if roi_pct >= 0:
        return 2.0
    if roi_pct >= -10:
        return 1.5
    return 1.0


def signal_from_score(score: float) -> tuple[str, str]:
    """Mapuje wynik 0–10 na sygnał + kolor."""
    if score >= 7.0:
        return SIGNAL_BUY, SIGNAL_COLORS[SIGNAL_BUY]
    if score >= 4.5:
        return SIGNAL_HOLD, SIGNAL_COLORS[SIGNAL_HOLD]
    return SIGNAL_SELL, SIGNAL_COLORS[SIGNAL_SELL]


def _build_comment(
    signal: str,
    trend: str,
    rsi: float | None,
    rating: str,
    upside_pct: float | None,
    roi_pct: float | None,
) -> str:
    parts: list[str] = []
    parts.append("powyżej MA200" if "▲" in trend else ("poniżej MA200" if "▼" in trend else "trend MA200 nieznany"))
    if rsi is not None:
        if rsi < 30:
            parts.append(f"RSI {rsi:.0f} (wyprzedanie)")
        elif rsi > 70:
            parts.append(f"RSI {rsi:.0f} (wykupienie)")
        else:
            parts.append(f"RSI {rsi:.0f}")
    if rating and rating != "—":
        if upside_pct is not None:
            parts.append(f"konsensus {rating.lower()} ({upside_pct:+.0f}% do celu)")
        else:
            parts.append(f"konsensus {rating.lower()}")
    if roi_pct is not None and not pd.isna(roi_pct):
        parts.append(f"Twój P&L {roi_pct:+.0f}%")
    return f"{signal}: " + ", ".join(parts) + "."


def evaluate_signal(
    ticker_xtb: str,
    snapshot: dict,
    consensus: AnalystConsensus | None,
    upside_pct: float | None,
    roi_pct: float | None,
) -> SignalResult:
    """Składa pełny wynik sygnału z trzech komponentów."""
    tech, trend, rsi_desc, rsi = technical_score(snapshot)
    cons, rating = consensus_score(consensus, upside_pct)
    pl = pl_score(roi_pct)
    total = tech + cons + pl
    signal, color = signal_from_score(total)
    comment = _build_comment(signal, trend, rsi, rating, upside_pct, roi_pct)

    return SignalResult(
        ticker_xtb=ticker_xtb,
        roi_pct=roi_pct,
        technical_score=round(tech, 2),
        consensus_score=round(cons, 2),
        pl_score=round(pl, 2),
        signal_score=round(total, 1),
        signal=signal,
        color=color,
        trend_ma200=trend,
        rsi=rsi,
        rating=rating,
        upside_pct=upside_pct,
        comment=comment,
    )
