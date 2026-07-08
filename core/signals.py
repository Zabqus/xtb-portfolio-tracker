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


def build_signal_matrix(results: list[SignalResult]) -> pd.DataFrame:
    """
    Macierz sygnałów (heatmapa) w układzie:
    wiersze = tickery, kolumny = RSI / trend MA / konsensus / P&L / wynik końcowy.
    """
    if not results:
        return pd.DataFrame(
            columns=[
                "ticker_xtb",
                "RSI",
                "trend_MA200",
                "konsensus",
                "P&L_%",  # bieżący ROI %
                "score_tech",
                "score_consensus",
                "score_pl",
                "score_total",
                "signal",
                "color",
            ]
        )

    rows: list[dict] = []
    for r in results:
        rows.append(
            {
                "ticker_xtb": r.ticker_xtb,
                "RSI": r.rsi,
                "trend_MA200": r.trend_ma200,
                "konsensus": r.rating,
                "P&L_%": r.roi_pct,
                "score_tech": r.technical_score,
                "score_consensus": r.consensus_score,
                "score_pl": r.pl_score,
                "score_total": r.signal_score,
                "signal": r.signal,
                "color": r.color,
            }
        )
    df = pd.DataFrame(rows)
    # Kolejność kolumn pod heatmapę
    cols = [
        "ticker_xtb",
        "RSI",
        "trend_MA200",
        "konsensus",
        "P&L_%",
        "score_tech",
        "score_consensus",
        "score_pl",
        "score_total",
        "signal",
        "color",
    ]
    return df[cols]


def build_stacked_components(results: list[SignalResult]) -> pd.DataFrame:
    """
    Dane pod wykres skumulowanych składowych sygnału (stacked bar 0–10).

    Dla każdego tickera zwraca:
    * technical_score
    * consensus_score
    * pl_score
    * signal_score (suma 0–10)
    """
    if not results:
        return pd.DataFrame(
            columns=[
                "ticker_xtb",
                "technical_score",
                "consensus_score",
                "pl_score",
                "signal_score",
            ]
        )

    data = [
        {
            "ticker_xtb": r.ticker_xtb,
            "technical_score": r.technical_score,
            "consensus_score": r.consensus_score,
            "pl_score": r.pl_score,
            "signal_score": r.signal_score,
        }
        for r in results
    ]
    return pd.DataFrame(data)


def interval_agreement_table(
    scores_by_interval: dict[str, dict[str, float]],
    *,
    buy_threshold: float = 7.0,
    sell_threshold: float = 4.0,
) -> pd.DataFrame:
    """
    Tabela zgodności sygnałów między horyzontami (np. 3M / 6M / 1Y).

    Parametr `scores_by_interval`:
        {
          "3M": {"AAPL": 8.1, "MSFT": 6.5, ...},
          "6M": {"AAPL": 7.9, "MSFT": 5.0, ...},
          "1Y": {"AAPL": 7.2, "MSFT": 4.2, ...},
        }

    Zwraca DataFrame:
        ticker_xtb, score_3M, score_6M, score_1Y, zgoda_interwałów
    gdzie zgoda_interwałów ∈ {"Spójny BUY", "Spójny SELL/HOLD", "Mieszany"}.
    """
    if not scores_by_interval:
        return pd.DataFrame(
            columns=[
                "ticker_xtb",
                "score_3M",
                "score_6M",
                "score_1Y",
                "zgoda_interwałów",
            ]
        )

    all_tickers: set[str] = set()
    for interval_scores in scores_by_interval.values():
        all_tickers.update(interval_scores.keys())

    def _interval_label(interval_key: str) -> str:
        key = interval_key.strip().upper()
        if key in {"3M", "6M", "1Y"}:
            return key
        return interval_key

    normalized_keys = {_interval_label(k): k for k in scores_by_interval.keys()}

    rows: list[dict] = []
    for ticker in sorted(all_tickers):
        row: dict[str, float | str | None] = {"ticker_xtb": ticker}
        interval_flags: list[str] = []

        for label, original_key in normalized_keys.items():
            col_name = f"score_{label}"
            score = scores_by_interval.get(original_key, {}).get(ticker)
            row[col_name] = score

            if score is None or pd.isna(score):
                continue
            if score >= buy_threshold:
                interval_flags.append("BUY")
            elif score <= sell_threshold:
                interval_flags.append("SELL")
            else:
                interval_flags.append("HOLD")

        unique_flags = set(interval_flags)
        if not interval_flags:
            agreement = "Brak danych"
        elif unique_flags == {"BUY"}:
            agreement = "Spójny BUY"
        elif unique_flags <= {"SELL", "HOLD"}:
            agreement = "Spójny SELL/HOLD"
        else:
            agreement = "Mieszany"

        row["zgoda_interwałów"] = agreement
        rows.append(row)

    df = pd.DataFrame(rows)

    ordered_cols = ["ticker_xtb", "score_3M", "score_6M", "score_1Y", "zgoda_interwałów"]
    for c in ordered_cols:
        if c not in df.columns:
            df[c] = None
    return df[ordered_cols]
