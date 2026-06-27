"""
Zaawansowana analityka zwrotów: atrybucja, rolling returns, scenariusze what-if, Monte Carlo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.allocation import classify_region, enrich_portfolio_allocation, fetch_allocation_metadata
from core.portfolio_benchmark import PORTFOLIO_BENCHMARKS, fetch_index_close_range
from core.timeline import MIN_POSITION_QTY, _apply_trade, fetch_close_matrix
from core.transactions import parse_cash_operations_trades

TRADING_DAYS = 252
ROLLING_WINDOWS: dict[str, int] = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}

MULTI_BENCHMARK_NAMES: tuple[str, ...] = (
    "S&P 500",
    "NASDAQ 100",
    "MSCI World",
    "WIG20",
)


@dataclass
class WhatIfResult:
    current_value: float
    shocked_value: float
    change_pct: float
    current_drawdown_pct: float
    shocked_drawdown_pct: float
    shocked_positions: list[dict]
    has_data: bool = True


@dataclass
class MonteCarloResult:
    paths: pd.DataFrame  # columns: day, p10, p50, p90, ...
    horizon_days: int
    n_simulations: int
    has_data: bool = True


# ───────────────────────── position values ─────────────────────────

def build_position_value_matrix(cash_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Dzienna wartość każdej pozycji (kolumny = tickery Yahoo, indeks = data).
    """
    trades = parse_cash_operations_trades(cash_ops)
    if trades.empty:
        return pd.DataFrame()

    start = trades["trade_date"].min()
    end = trades["trade_date"].max()
    calendar = pd.date_range(start, end, freq="D")

    holdings: dict[str, float] = {}
    costs: dict[str, float] = {}
    last_prices: dict[str, float] = {}
    daily_holdings: list[tuple[pd.Timestamp, dict[str, float]]] = []

    trade_by_date = trades.groupby("trade_date", sort=True)
    for day in calendar:
        if day in trade_by_date.groups:
            for _, row in trade_by_date.get_group(day).iterrows():
                _apply_trade(holdings, costs, row)
                last_prices[row["ticker_yahoo"]] = float(row["price"])

        active = {t: q for t, q in holdings.items() if q > MIN_POSITION_QTY}
        daily_holdings.append((day, active.copy()))

    all_tickers = sorted({t for _, h in daily_holdings for t in h})
    if not all_tickers:
        return pd.DataFrame()

    price_matrix = fetch_close_matrix(
        tuple(all_tickers),
        start_date=start.strftime("%Y-%m-%d"),
        end_date=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
    )

    rows: list[dict] = []
    for day, active in daily_holdings:
        if not active:
            rows.append({"date": day})
            continue
        row: dict = {"date": day}
        for ticker, qty in active.items():
            px = None
            if not price_matrix.empty and ticker in price_matrix.columns:
                available = price_matrix[ticker].loc[:day].dropna()
                if not available.empty:
                    px = float(available.iloc[-1])
            if px is None and ticker in last_prices:
                px = float(last_prices[ticker])
            if px is not None:
                row[ticker] = qty * px
        rows.append(row)

    df = pd.DataFrame(rows).set_index("date").sort_index()
    return df.fillna(0.0)


def _filter_period(
    twr_index: pd.DataFrame,
    period: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Zwraca (start, end) dla wybranego okresu."""
    df = twr_index.dropna(subset=["date"]).sort_values("date")
    end = pd.Timestamp(df["date"].iloc[-1]).normalize()
    if period == "Cały okres":
        start = pd.Timestamp(df["date"].iloc[0]).normalize()
    elif period == "YTD":
        start = pd.Timestamp(end.year, 1, 1)
    elif period == "1 rok":
        start = end - pd.Timedelta(days=365)
    elif period == "6 miesięcy":
        start = end - pd.Timedelta(days=183)
    elif period == "3 miesiące":
        start = end - pd.Timedelta(days=92)
    else:
        start = pd.Timestamp(df["date"].iloc[0]).normalize()
    return start, end


# ───────────────────────── return attribution ─────────────────────────

def compute_return_attribution(
    cash_ops: pd.DataFrame,
    twr_index: pd.DataFrame,
    *,
    group_by: str = "position",
    period: str = "Cały okres",
    analyzed: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Atrybucja zwrotu TWR: wkład pozycji / sektorów / regionów (w pp).

    Metoda: suma dziennych wag × zwrotów pozycji (link effect).
    """
    pos_matrix = build_position_value_matrix(cash_ops)
    if pos_matrix.empty or twr_index is None or twr_index.empty:
        return pd.DataFrame()

    start, end = _filter_period(twr_index, period)
    pos = pos_matrix.loc[(pos_matrix.index >= start) & (pos_matrix.index <= end)].copy()
    if len(pos) < 2:
        return pd.DataFrame()

    totals = pos.sum(axis=1)
    pos = pos[totals > 0]
    totals = totals[totals > 0]
    if len(pos) < 2:
        return pd.DataFrame()

    weights = pos.div(totals, axis=0)
    returns = pos.pct_change()
    contrib = (weights.shift(1) * returns).iloc[1:].sum(axis=0) * 100.0

    if group_by != "position":
        meta: dict[str, dict] = {}
        if analyzed is not None and not analyzed.empty:
            enriched = enrich_portfolio_allocation(analyzed)
            for _, r in enriched.iterrows():
                meta[str(r["ticker_yahoo"])] = {
                    "sector": r.get("sector", "Brak sektora"),
                    "region": r.get("region", "Inne"),
                }
        else:
            tickers = tuple(sorted(contrib.index.astype(str)))
            fetched = fetch_allocation_metadata(tickers)
            for t in tickers:
                m = fetched.get(t, {})
                meta[t] = {
                    "sector": m.get("sector", "Brak sektora"),
                    "region": classify_region(m.get("country"), t),
                }

        key = "sector" if group_by == "sector" else "region"
        grouped: dict[str, float] = {}
        for ticker, val in contrib.items():
            label = meta.get(str(ticker), {}).get(key, "Inne")
            grouped[label] = grouped.get(label, 0.0) + float(val)
        contrib = pd.Series(grouped)

    sorted_contrib = contrib.sort_values(ascending=True)
    return pd.DataFrame(
        {"label": sorted_contrib.index.astype(str), "contribution_pp": sorted_contrib.values}
    )


# ───────────────────────── rolling returns heatmap ─────────────────────────

def compute_rolling_returns_heatmap(
    twr_index: pd.DataFrame,
    *,
    freq: str = "month",
) -> pd.DataFrame:
    """
    Heatmapa rolling returns: wiersze = okresy (miesiące/kwartały),
    kolumny = 1M/3M/6M/1Y.
    """
    if twr_index is None or twr_index.empty:
        return pd.DataFrame()

    df = twr_index.dropna(subset=["date", "twr_index"]).sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.set_index("date")

    if freq == "quarter":
        period_ends = df.resample("QE").last().dropna(subset=["twr_index"])
        period_labels = [f"{d.year} Q{(d.month - 1) // 3 + 1}" for d in period_ends.index]
    else:
        period_ends = df.resample("ME").last().dropna(subset=["twr_index"])
        period_labels = [d.strftime("%Y-%m") for d in period_ends.index]

    rows: list[dict] = []
    for label, end_date in zip(period_labels, period_ends.index):
        row: dict = {"period": label}
        idx_slice = df.loc[:end_date, "twr_index"]
        for win_name, win_days in ROLLING_WINDOWS.items():
            if len(idx_slice) < win_days + 1:
                row[win_name] = np.nan
                continue
            start_val = float(idx_slice.iloc[-win_days - 1])
            end_val = float(idx_slice.iloc[-1])
            if start_val > 0:
                row[win_name] = (end_val / start_val - 1.0) * 100.0
            else:
                row[win_name] = np.nan
        rows.append(row)

    return pd.DataFrame(rows)


# ───────────────────────── calendar returns ─────────────────────────

def compute_calendar_returns(twr_index: pd.DataFrame) -> pd.DataFrame:
    """Dzienne zwroty TWR z metadanymi do kalendarza (GitHub-style)."""
    if twr_index is None or twr_index.empty:
        return pd.DataFrame()

    df = twr_index.dropna(subset=["date", "twr_index"]).sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["return_pct"] = df["twr_index"].pct_change() * 100.0
    df = df.dropna(subset=["return_pct"])
    df["year"] = df["date"].dt.year
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["weekday"] = df["date"].dt.weekday  # 0=Mon
    df["month"] = df["date"].dt.month
    return df


# ───────────────────────── multi-benchmark ─────────────────────────

def build_portfolio_vs_multi_benchmark(
    twr_index: pd.DataFrame,
    benchmark_names: tuple[str, ...] | list[str] | None = None,
) -> pd.DataFrame:
    """Indeks TWR portfela + wiele benchmarków (rebazowane do 100)."""
    if twr_index is None or twr_index.empty:
        return pd.DataFrame()

    names = list(benchmark_names or MULTI_BENCHMARK_NAMES)
    port = twr_index.dropna(subset=["date", "twr_index"]).copy()
    port["date"] = pd.to_datetime(port["date"]).dt.normalize()
    port = port.sort_values("date")
    if port.empty:
        return pd.DataFrame()

    merged = port.rename(columns={"twr_index": "portfolio"})[["date", "portfolio"]]
    start = port["date"].iloc[0]
    end = port["date"].iloc[-1]
    end_str = (end + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
    start_str = start.strftime("%Y-%m-%d")

    for name in names:
        if name not in PORTFOLIO_BENCHMARKS:
            continue
        bench = fetch_index_close_range(name, start_str, end_str)
        col = f"bench_{name}"
        if bench.empty:
            merged[col] = np.nan
            continue
        bench_on_dates = bench.reindex(pd.DatetimeIndex(port["date"])).ffill()
        first_valid = bench_on_dates.dropna()
        if first_valid.empty:
            merged[col] = np.nan
            continue
        base = float(first_valid.iloc[0])
        merged[col] = (bench_on_dates / base * 100.0).values if base > 0 else np.nan

    return merged.reset_index(drop=True)


# ───────────────────────── what-if stress test ─────────────────────────

def compute_whatif_scenario(
    analyzed: pd.DataFrame,
    *,
    top_n: int = 3,
    shock_pct: float = -10.0,
    twr_index: pd.DataFrame | None = None,
) -> WhatIfResult:
    """
    Stress test: spadek top-N pozycji o shock_pct % → nowa wartość i drawdown.
    """
    empty = WhatIfResult(0, 0, 0, 0, 0, [], has_data=False)
    if analyzed is None or analyzed.empty or "market_value" not in analyzed.columns:
        return empty

    valid = analyzed.dropna(subset=["market_value"]).copy()
    valid = valid[valid["market_value"] > 0].sort_values("market_value", ascending=False)
    if valid.empty:
        return empty

    current_value = float(valid["market_value"].sum())
    top = valid.head(top_n)
    rest_value = current_value - float(top["market_value"].sum())

    shocked_positions: list[dict] = []
    shocked_top_total = 0.0
    factor = 1.0 + shock_pct / 100.0
    for _, row in top.iterrows():
        old = float(row["market_value"])
        new = old * factor
        shocked_top_total += new
        label = str(row.get("ticker_xtb") or row.get("ticker_yahoo", ""))
        shocked_positions.append(
            {"ticker": label, "old_value": old, "new_value": new, "weight_pct": old / current_value * 100}
        )

    shocked_value = rest_value + shocked_top_total
    change_pct = (shocked_value / current_value - 1.0) * 100.0 if current_value > 0 else 0.0

    current_dd = 0.0
    shocked_dd = 0.0
    if twr_index is not None and not twr_index.empty:
        idx = twr_index.dropna(subset=["twr_index"]).sort_values("date")["twr_index"]
        peak = float(idx.cummax().iloc[-1])
        current_dd = (float(idx.iloc[-1]) / peak - 1.0) * 100.0 if peak > 0 else 0.0
        shocked_idx = float(idx.iloc[-1]) * (shocked_value / current_value)
        shocked_dd = (shocked_idx / peak - 1.0) * 100.0 if peak > 0 else 0.0

    return WhatIfResult(
        current_value=current_value,
        shocked_value=shocked_value,
        change_pct=change_pct,
        current_drawdown_pct=current_dd,
        shocked_drawdown_pct=shocked_dd,
        shocked_positions=shocked_positions,
        has_data=True,
    )


# ───────────────────────── Monte Carlo ─────────────────────────

def run_monte_carlo(
    twr_index: pd.DataFrame,
    *,
    horizon_years: float = 3.0,
    n_simulations: int = 500,
    seed: int = 42,
) -> MonteCarloResult:
    """
    Symulacja Monte Carlo na historycznych dziennych zwrotach TWR (bootstrap).
    Zwraca percentyle 10/50/90 wartości portfela (start = 100).
    """
    empty = MonteCarloResult(pd.DataFrame(), 0, 0, has_data=False)
    if twr_index is None or twr_index.empty:
        return empty

    df = twr_index.dropna(subset=["twr_index"]).sort_values("date")
    rets = df["twr_index"].pct_change().dropna()
    rets = rets[np.isfinite(rets)]
    if len(rets) < 30:
        return empty

    horizon_days = int(horizon_years * TRADING_DAYS)
    rng = np.random.default_rng(seed)
    rets_arr = rets.values

    paths = np.zeros((n_simulations, horizon_days + 1))
    paths[:, 0] = 100.0
    for sim in range(n_simulations):
        sampled = rng.choice(rets_arr, size=horizon_days, replace=True)
        for d in range(horizon_days):
            paths[sim, d + 1] = paths[sim, d] * (1.0 + sampled[d])

    days = np.arange(horizon_days + 1)
    p10 = np.percentile(paths, 10, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p90 = np.percentile(paths, 90, axis=0)

    result_df = pd.DataFrame(
        {"day": days, "p10": p10, "p50": p50, "p90": p90, "months": days / 21.0}
    )
    return MonteCarloResult(
        paths=result_df,
        horizon_days=horizon_days,
        n_simulations=n_simulations,
        has_data=True,
    )
