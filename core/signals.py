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


@dataclass(frozen=True)
class SignalProfile:
    name: str
    buy_threshold: float
    sell_threshold: float
    weight_tech: float
    weight_consensus: float
    weight_pl: float


SIGNAL_PROFILES: dict[str, SignalProfile] = {
    "Defensywny": SignalProfile(
        name="Defensywny",
        buy_threshold=7.5,
        sell_threshold=4.5,
        weight_tech=0.50,
        weight_consensus=0.35,
        weight_pl=0.15,
    ),
    "Zbalansowany": SignalProfile(
        name="Zbalansowany",
        buy_threshold=7.0,
        sell_threshold=4.0,
        weight_tech=0.40,
        weight_consensus=0.40,
        weight_pl=0.20,
    ),
    "Agresywny": SignalProfile(
        name="Agresywny",
        buy_threshold=6.5,
        sell_threshold=3.5,
        weight_tech=0.35,
        weight_consensus=0.40,
        weight_pl=0.25,
    ),
}


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


def signal_from_score_thresholds(
    score: float,
    *,
    buy_threshold: float,
    sell_threshold: float,
) -> tuple[str, str]:
    """Mapuje score na sygnał przy konfigurowalnych progach."""
    if score >= buy_threshold:
        return SIGNAL_BUY, SIGNAL_COLORS[SIGNAL_BUY]
    if score > sell_threshold:
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


def evaluate_signal_profiled(
    ticker_xtb: str,
    snapshot: dict,
    consensus: AnalystConsensus | None,
    upside_pct: float | None,
    roi_pct: float | None,
    profile: SignalProfile,
) -> SignalResult:
    """
    Wersja evaluate_signal z wagami/progami zależnymi od profilu decyzyjnego.
    """
    tech, trend, _, rsi = technical_score(snapshot)
    cons, rating = consensus_score(consensus, upside_pct)
    pl = pl_score(roi_pct)

    w_sum = max(profile.weight_tech + profile.weight_consensus + profile.weight_pl, 1e-9)
    total = (
        (tech / 4.0) * profile.weight_tech
        + (cons / 4.0) * profile.weight_consensus
        + (pl / 2.0) * profile.weight_pl
    ) / w_sum * 10.0
    signal, color = signal_from_score_thresholds(
        total,
        buy_threshold=profile.buy_threshold,
        sell_threshold=profile.sell_threshold,
    )
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


def compute_confidence_score(
    *,
    analyst_opinions: int | None,
    has_rsi: bool,
    has_ma50: bool,
    has_ma200: bool,
    interval_agreement: str | None,
) -> float:
    """
    Pewność sygnału 0–100.
    Składniki: jakość konsensusu, kompletność techniki, spójność interwałów.
    """
    opinions = int(analyst_opinions or 0)
    if opinions >= 20:
        analyst_component = 40.0
    elif opinions >= 10:
        analyst_component = 30.0
    elif opinions >= 5:
        analyst_component = 20.0
    elif opinions > 0:
        analyst_component = 10.0
    else:
        analyst_component = 0.0

    tech_component = (
        (10.0 if has_rsi else 0.0)
        + (15.0 if has_ma50 else 0.0)
        + (15.0 if has_ma200 else 0.0)
    )

    agreement = str(interval_agreement or "").strip()
    agreement_component_map = {
        "Spójny BUY": 20.0,
        "Spójny SELL/HOLD": 16.0,
        "Mieszany": 8.0,
        "Brak danych": 2.0,
    }
    agreement_component = agreement_component_map.get(agreement, 6.0)

    return round(min(100.0, analyst_component + tech_component + agreement_component), 1)


def compute_signal_momentum(
    ticker_xtb: str,
    current_score: float,
    snapshot_7d: dict | None,
    snapshot_30d: dict | None,
) -> dict[str, float | str | None]:
    """Zmiana score względem snapshotu sprzed 7 / 30 dni."""
    s7 = None
    s30 = None
    if snapshot_7d:
        s7 = (snapshot_7d.get("positions") or {}).get(ticker_xtb, {}).get("score_total")
    if snapshot_30d:
        s30 = (snapshot_30d.get("positions") or {}).get(ticker_xtb, {}).get("score_total")

    d7 = (float(current_score) - float(s7)) if s7 is not None and not pd.isna(s7) else None
    d30 = (float(current_score) - float(s30)) if s30 is not None and not pd.isna(s30) else None

    trend = "→"
    if d7 is not None and d30 is not None:
        if d7 > 0 and d30 > 0:
            trend = "↑"
        elif d7 < 0 and d30 < 0:
            trend = "↓"
    elif d7 is not None:
        trend = "↑" if d7 > 0 else ("↓" if d7 < 0 else "→")

    return {
        "delta_7d": round(d7, 2) if d7 is not None else None,
        "delta_30d": round(d30, 2) if d30 is not None else None,
        "trend_arrow": trend,
    }


def build_action_ranking(
    signal_df: pd.DataFrame,
    *,
    top_n: int = 5,
) -> pd.DataFrame:
    """
    Ranking „co zrobić dziś”: największe zmiany + czerwone sygnały z wysoką wagą.
    Oczekuje kolumn: ticker_xtb, score_total, signal, weight_pct, delta_7d, interval_agreement.
    """
    if signal_df is None or signal_df.empty:
        return pd.DataFrame()
    df = signal_df.copy()
    for col in ("weight_pct", "delta_7d", "score_total"):
        if col not in df.columns:
            df[col] = 0.0
    if "signal" not in df.columns:
        df["signal"] = SIGNAL_HOLD
    if "interval_agreement" not in df.columns:
        df["interval_agreement"] = "Brak danych"

    df["urgency"] = (
        df["delta_7d"].abs().fillna(0) * 1.8
        + df["weight_pct"].fillna(0) * 0.12
        + (df["signal"] == SIGNAL_SELL).astype(float) * 3.0
        + (df["interval_agreement"] == "Mieszany").astype(float) * 2.0
    )
    ranked = df.sort_values("urgency", ascending=False).head(top_n)
    return ranked


def build_sanity_checks(signal_df: pd.DataFrame) -> pd.DataFrame:
    """Wykrywa konflikty typu 'anty-sygnały'."""
    if signal_df is None or signal_df.empty:
        return pd.DataFrame(columns=["ticker_xtb", "issue", "severity"])
    rows: list[dict[str, str]] = []
    for _, r in signal_df.iterrows():
        ticker = str(r.get("ticker_xtb") or "")
        tech = float(r.get("score_tech", 0) or 0)
        cons = float(r.get("score_consensus", 0) or 0)
        total = float(r.get("score_total", 0) or 0)
        rsi = r.get("RSI")

        if cons >= 3.2 and tech <= 1.2:
            rows.append(
                {
                    "ticker_xtb": ticker,
                    "issue": "Bardzo dobry konsensus przy słabej technice",
                    "severity": "medium",
                }
            )
        if total >= 7.2 and rsi is not None and not pd.isna(rsi) and float(rsi) >= 75:
            rows.append(
                {
                    "ticker_xtb": ticker,
                    "issue": "Wysoki score przy ekstremalnie wysokim RSI",
                    "severity": "high",
                }
            )
        if total <= 3.8 and rsi is not None and not pd.isna(rsi) and float(rsi) <= 28:
            rows.append(
                {
                    "ticker_xtb": ticker,
                    "issue": "Niski score mimo silnego wyprzedania RSI",
                    "severity": "low",
                }
            )
    return pd.DataFrame(rows)
