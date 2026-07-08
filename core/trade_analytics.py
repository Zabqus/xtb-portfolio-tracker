"""
Statystyki tradingowe: czas trzymania, win rate, avg win/loss, round-tripy.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MIN_QTY = 1e-9


@dataclass
class TradeAnalyticsSummary:
    closed_trades: int
    win_rate_pct: float
    avg_holding_days: float
    median_holding_days: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_realized_pnl: float
    best_trade_pnl: float
    worst_trade_pnl: float


def _holding_days_from_closed(closed: pd.DataFrame) -> pd.Series:
    if closed is None or closed.empty:
        return pd.Series(dtype=float)
    if "open_time" not in closed.columns or "close_time" not in closed.columns:
        return pd.Series(dtype=float)
    df = closed.dropna(subset=["open_time", "close_time"]).copy()
    delta = df["close_time"] - df["open_time"]
    return delta.dt.total_seconds() / 86400


def build_round_trips_from_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """
    FIFO matching OPEN → CLOSE: zrealizowane round-tripy z Cash Operations.

    Kolumny: ticker_xtb, open_time, close_time, quantity, open_price, close_price,
             holding_days, realized_pnl, pnl_pct
    """
    if trades.empty:
        return pd.DataFrame()

    trips: list[dict] = []
    lots: dict[str, list[dict]] = {}

    for _, row in trades.sort_values("trade_time").iterrows():
        ticker = row["ticker_xtb"]
        yahoo = row["ticker_yahoo"]
        side = row["side"]
        qty = float(row["quantity"])
        price = float(row["price"])
        t = row["trade_time"]

        if ticker not in lots:
            lots[ticker] = []

        if side == "OPEN":
            lots[ticker].append(
                {"open_time": t, "qty": qty, "price": price, "yahoo": yahoo}
            )
            continue

        remaining = qty
        while remaining > MIN_QTY and lots[ticker]:
            lot = lots[ticker][0]
            take = min(remaining, lot["qty"])
            cost = take * lot["price"]
            proceeds = take * price
            pnl = proceeds - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
            holding = (t - lot["open_time"]).total_seconds() / 86400

            trips.append(
                {
                    "ticker_xtb": ticker,
                    "ticker_yahoo": lot["yahoo"],
                    "open_time": lot["open_time"],
                    "close_time": t,
                    "quantity": take,
                    "open_price": lot["price"],
                    "close_price": price,
                    "holding_days": holding,
                    "realized_pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "is_win": pnl > 0,
                }
            )

            lot["qty"] -= take
            remaining -= take
            if lot["qty"] <= MIN_QTY:
                lots[ticker].pop(0)

    return pd.DataFrame(trips)


def compute_trade_analytics(
    trades: pd.DataFrame,
    closed: pd.DataFrame | None = None,
) -> tuple[TradeAnalyticsSummary, pd.DataFrame]:
    """
    Zwraca podsumowanie statystyk oraz tabelę round-tripów (FIFO z transakcji).

    Win rate i avg win/loss liczone z round-tripów; holding period z closed
    (jeśli dostępny) lub z round-tripów.
    """
    round_trips = build_round_trips_from_trades(trades)

    if round_trips.empty and (closed is None or closed.empty or "pnl" not in closed.columns):
        empty = TradeAnalyticsSummary(
            closed_trades=0,
            win_rate_pct=0.0,
            avg_holding_days=0.0,
            median_holding_days=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            total_realized_pnl=0.0,
            best_trade_pnl=0.0,
            worst_trade_pnl=0.0,
        )
        return empty, round_trips

    if not round_trips.empty:
        pnl_series = round_trips["realized_pnl"]
    elif closed is not None and not closed.empty and "pnl" in closed.columns:
        pnl_series = closed["pnl"].dropna()
    else:
        pnl_series = pd.Series(dtype=float)

    wins = pnl_series[pnl_series > 0]
    losses = pnl_series[pnl_series < 0]

    win_rate = float((pnl_series > 0).mean() * 100) if len(pnl_series) else 0.0
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = abs(float(losses.sum())) if len(losses) else 0.0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0

    holding_closed = _holding_days_from_closed(closed) if closed is not None else pd.Series(dtype=float)
    if not holding_closed.empty:
        avg_hold = float(holding_closed.mean())
        median_hold = float(holding_closed.median())
    elif not round_trips.empty:
        avg_hold = float(round_trips["holding_days"].mean())
        median_hold = float(round_trips["holding_days"].median())
    else:
        avg_hold = median_hold = 0.0

    total_pnl = float(pnl_series.sum()) if len(pnl_series) else 0.0
    if closed is not None and not closed.empty and "pnl" in closed.columns:
        total_pnl = float(closed["pnl"].sum())

    closed_count = int(len(closed)) if closed is not None else 0

    summary = TradeAnalyticsSummary(
        closed_trades=len(round_trips) if not round_trips.empty else closed_count,
        win_rate_pct=win_rate,
        avg_holding_days=avg_hold,
        median_holding_days=median_hold,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor if profit_factor != float("inf") else 999.0,
        total_realized_pnl=total_pnl,
        best_trade_pnl=float(pnl_series.max()) if len(pnl_series) else 0.0,
        worst_trade_pnl=float(pnl_series.min()) if len(pnl_series) else 0.0,
    )
    return summary, round_trips


def backtest_threshold_heuristic(
    closed_or_round_trips: pd.DataFrame,
    signal_scores: pd.Series,
    *,
    buy_threshold: float = 7.0,
    sell_threshold: float = 4.0,
) -> dict[str, float]:
    """
    Uproszczony backtest heurystyki:
    „gdyby sprzedawać przy score <4 i kupować przy >7”
    na zamkniętych pozycjach.

    Założenia (celowo proste):
    * analizujemy tylko zamknięte transakcje (round-tripy),
    * dla każdej transakcji mamy przypisany wynik sygnału `signal_scores`
      (w tej samej kolejności indexu, co `closed_or_round_trips`),
    * BUY oznacza „strategia pozwalała na zajęcie pozycji”
      (score ≥ buy_threshold),
    * SELL/HOLD oznacza „strategia nie pozwalała na wejście”
      (score < buy_threshold); SELL dodatkowo identyfikujemy,
      gdy score <= sell_threshold, ale w tym uproszczeniu
      sprowadzamy to do decyzji „nie wchodź”.

    Zwraca słownik z metrykami:
        * trades_total         – liczba wszystkich transakcji,
        * trades_taken         – liczba transakcji, które strategia by wzięła,
        * hit_rate_baseline    – win rate wszystkich transakcji,
        * hit_rate_strategy    – win rate tylko „wziętych”,
        * pnl_baseline         – suma P&L wszystkich,
        * pnl_strategy         – suma P&L tylko „wziętych”.

    Wymagane kolumny w `closed_or_round_trips`:
        * 'realized_pnl' lub 'pnl' (zł / waluta konta).
    """
    if closed_or_round_trips is None or closed_or_round_trips.empty:
        return {
            "trades_total": 0,
            "trades_taken": 0,
            "hit_rate_baseline": 0.0,
            "hit_rate_strategy": 0.0,
            "pnl_baseline": 0.0,
            "pnl_strategy": 0.0,
        }

    if signal_scores is None or signal_scores.empty:
        return {
            "trades_total": len(closed_or_round_trips),
            "trades_taken": 0,
            "hit_rate_baseline": 0.0,
            "hit_rate_strategy": 0.0,
            "pnl_baseline": 0.0,
            "pnl_strategy": 0.0,
        }

    df = closed_or_round_trips.copy()
    df = df.reset_index(drop=True)
    scores = signal_scores.reset_index(drop=True)

    if len(df) != len(scores):
        # Bez 1:1 dopasowania nie ma sensu liczyć backtestu.
        return {
            "trades_total": len(df),
            "trades_taken": 0,
            "hit_rate_baseline": 0.0,
            "hit_rate_strategy": 0.0,
            "pnl_baseline": 0.0,
            "pnl_strategy": 0.0,
        }

    if "realized_pnl" in df.columns:
        pnl = df["realized_pnl"].astype(float)
    elif "pnl" in df.columns:
        pnl = df["pnl"].astype(float)
    else:
        return {
            "trades_total": len(df),
            "trades_taken": 0,
            "hit_rate_baseline": 0.0,
            "hit_rate_strategy": 0.0,
            "pnl_baseline": 0.0,
            "pnl_strategy": 0.0,
        }

    mask_taken = scores >= buy_threshold
    baseline_wins = pnl > 0
    strategy_wins = baseline_wins & mask_taken

    trades_total = int(len(df))
    trades_taken = int(mask_taken.sum())

    hit_rate_baseline = float(baseline_wins.mean() * 100) if trades_total else 0.0
    hit_rate_strategy = (
        float(strategy_wins[mask_taken].mean() * 100) if trades_taken else 0.0
    )

    pnl_baseline = float(pnl.sum())
    pnl_strategy = float(pnl[mask_taken].sum()) if trades_taken else 0.0

    return {
        "trades_total": trades_total,
        "trades_taken": trades_taken,
        "hit_rate_baseline": hit_rate_baseline,
        "hit_rate_strategy": hit_rate_strategy,
        "pnl_baseline": pnl_baseline,
        "pnl_strategy": pnl_strategy,
    }


def backtest_score_series(
    history_df: pd.DataFrame,
    score_series: pd.Series,
    *,
    buy_threshold: float = 7.0,
    sell_threshold: float = 4.0,
) -> pd.DataFrame:
    """
    Backtest dzienny (krok 2): equity curve strategii sygnałowej vs buy&hold.

    Wejście:
    - history_df z kolumną `Close`
    - score_series (score 0–10) o tym samym indeksie czasu

    Reguła:
    - jeśli score >= buy_threshold -> pozycja = 1
    - jeśli score <= sell_threshold -> pozycja = 0
    - w przeciwnym razie utrzymanie poprzedniego stanu.
    """
    if history_df is None or history_df.empty or "Close" not in history_df.columns:
        return pd.DataFrame()
    if score_series is None or score_series.empty:
        return pd.DataFrame()

    df = history_df.copy()
    if "Date" in df.columns:
        df = df.set_index("Date")
    df = df.sort_index()
    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    if close.empty:
        return pd.DataFrame()

    scores = pd.to_numeric(score_series, errors="coerce")
    scores.index = pd.to_datetime(scores.index)
    scores = scores.sort_index()

    merged = pd.DataFrame({"Close": close}).join(scores.rename("score"), how="inner").dropna()
    if merged.empty or len(merged) < 3:
        return pd.DataFrame()

    position: list[int] = []
    state = 0
    for score in merged["score"]:
        if float(score) >= buy_threshold:
            state = 1
        elif float(score) <= sell_threshold:
            state = 0
        position.append(state)
    merged["position"] = position

    merged["ret"] = merged["Close"].pct_change().fillna(0.0)
    merged["ret_strategy"] = merged["ret"] * merged["position"].shift(1).fillna(0.0)
    merged["equity_buy_hold"] = (1.0 + merged["ret"]).cumprod()
    merged["equity_strategy"] = (1.0 + merged["ret_strategy"]).cumprod()
    merged["active_days"] = merged["position"].rolling(5, min_periods=1).mean()
    return merged.reset_index().rename(columns={"index": "Date"})
