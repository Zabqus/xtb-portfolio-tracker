"""
Wpływ prowizji (fee drag) na wynik z Closed Positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class FeeDragSummary:
    currency_note: str
    trade_count: int
    gross_pnl: float
    commission_total: float  # wartość dodatnia = koszt
    net_pnl: float
    fee_drag_pct: float | None  # |commission| / |gross| * 100 gdy gross ≠ 0
    tax_shield_estimate: float  # commission * 0.19 (koszt obniża podstawę Belki)
    by_year: pd.DataFrame = field(default_factory=pd.DataFrame)
    by_ticker: pd.DataFrame = field(default_factory=pd.DataFrame)
    has_data: bool = False


def _commission_cost(series: pd.Series) -> pd.Series:
    """XTB bywa ujemne lub dodatnie — traktujemy |commission| jako koszt."""
    return pd.to_numeric(series, errors="coerce").fillna(0.0).abs()


def compute_fee_drag(
    closed: pd.DataFrame | None,
    *,
    tax_year: int | None = None,
) -> FeeDragSummary:
    empty = FeeDragSummary(
        currency_note="waluta konta (Closed Positions)",
        trade_count=0,
        gross_pnl=0.0,
        commission_total=0.0,
        net_pnl=0.0,
        fee_drag_pct=None,
        tax_shield_estimate=0.0,
        has_data=False,
    )
    if closed is None or closed.empty or "commission" not in closed.columns:
        return empty

    df = closed.copy()
    if "pnl" not in df.columns:
        return empty

    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    df["fee"] = _commission_cost(df["commission"])
    df = df.dropna(subset=["pnl"])
    if df.empty:
        return empty

    if "close_time" in df.columns:
        df["close_dt"] = pd.to_datetime(df["close_time"], errors="coerce")
        df["tax_year"] = df["close_dt"].dt.year
    else:
        df["tax_year"] = pd.NA

    if tax_year is not None and "tax_year" in df.columns:
        df = df[df["tax_year"] == int(tax_year)].copy()
        if df.empty:
            return empty

    gross = float(df["pnl"].sum())
    fees = float(df["fee"].sum())
    net = gross - fees
    drag = (fees / abs(gross) * 100.0) if abs(gross) > 1e-9 else None

    by_year = pd.DataFrame()
    if df["tax_year"].notna().any():
        by_year = (
            df.groupby("tax_year", as_index=False)
            .agg(trades=("pnl", "count"), gross_pnl=("pnl", "sum"), commission=("fee", "sum"))
            .sort_values("tax_year", ascending=False)
        )
        by_year["net_pnl"] = by_year["gross_pnl"] - by_year["commission"]
        by_year["fee_drag_pct"] = by_year.apply(
            lambda r: (r["commission"] / abs(r["gross_pnl"]) * 100.0)
            if abs(r["gross_pnl"]) > 1e-9
            else None,
            axis=1,
        )

    by_ticker = pd.DataFrame()
    ticker_col = "ticker_xtb" if "ticker_xtb" in df.columns else None
    if ticker_col:
        by_ticker = (
            df.groupby(ticker_col, as_index=False)
            .agg(trades=("pnl", "count"), gross_pnl=("pnl", "sum"), commission=("fee", "sum"))
            .sort_values("commission", ascending=False)
        )
        by_ticker["net_pnl"] = by_ticker["gross_pnl"] - by_ticker["commission"]

    return FeeDragSummary(
        currency_note="waluta konta (Closed Positions)",
        trade_count=int(len(df)),
        gross_pnl=gross,
        commission_total=fees,
        net_pnl=net,
        fee_drag_pct=drag,
        tax_shield_estimate=fees * 0.19,
        by_year=by_year,
        by_ticker=by_ticker,
        has_data=True,
    )
