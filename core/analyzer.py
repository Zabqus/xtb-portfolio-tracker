"""
Portfolio analytics – market prices, FX conversion, PnL metrics.
"""

from __future__ import annotations

import pandas as pd

from core.currencies import convert_amount, fetch_rates_to_currency
from core.market_data import fetch_last_prices


def analyze_portfolio(
    portfolio: pd.DataFrame,
    display_currency: str | None = None,
) -> pd.DataFrame:
    """
    Wzbogaca portfel o ceny rynkowe oraz metryki zysku/straty.

    Kolumny w walucie instrumentu: cost_native, value_native, pnl_native.
    Po przeliczeniu FX: position_cost, market_value, pnl (w display_currency).
    """
    required = {"ticker_yahoo", "quantity", "avg_price"}
    if not required.issubset(portfolio.columns):
        raise ValueError(f"Missing portfolio columns: {required - set(portfolio.columns)}")

    account_currency = portfolio.attrs.get("account_currency", "EUR")
    target = (display_currency or account_currency).upper()

    result = portfolio.copy()
    if "currency" not in result.columns:
        result["currency"] = account_currency

    tickers_tuple = tuple(sorted(result["ticker_yahoo"].unique()))
    price_map = fetch_last_prices(tickers_tuple)
    result["market_price"] = result["ticker_yahoo"].map(price_map)

    result["cost_native"] = result["quantity"] * result["avg_price"]
    result["value_native"] = result["quantity"] * result["market_price"]
    result["pnl_native"] = result["value_native"] - result["cost_native"]

    currencies = set(result["currency"].dropna().unique()) | {target}
    rates = fetch_rates_to_currency(currencies, target)

    result["position_cost"] = result.apply(
        lambda r: convert_amount(r["cost_native"], r["currency"], target, rates),
        axis=1,
    )
    result["market_value"] = result.apply(
        lambda r: convert_amount(r["value_native"], r["currency"], target, rates),
        axis=1,
    )
    result["pnl"] = result["market_value"] - result["position_cost"]
    result["roi_pct"] = (result["pnl"] / result["position_cost"] * 100).where(
        result["position_cost"] > 0
    )

    result.attrs["account_currency"] = account_currency
    result.attrs["display_currency"] = target
    result.attrs["fx_rates"] = rates
    return result


def portfolio_summary(analyzed: pd.DataFrame) -> dict[str, float | str]:
    """Zagregowane metryki portfela w walucie wyświetlania."""
    valid = analyzed.dropna(subset=["market_value", "position_cost"])
    total_value = valid["market_value"].sum()
    total_cost = valid["position_cost"].sum()
    total_pnl = total_value - total_cost
    total_roi = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "total_value": float(total_value),
        "total_cost": float(total_cost),
        "total_pnl": float(total_pnl),
        "total_roi_pct": float(total_roi),
        "display_currency": analyzed.attrs.get("display_currency", "PLN"),
        "account_currency": analyzed.attrs.get("account_currency", "PLN"),
    }


def closed_positions_summary(closed: pd.DataFrame) -> dict[str, float | int]:
    """Statystyki zamkniętych pozycji z arkusza XTB."""
    if closed is None or closed.empty or "pnl" not in closed.columns:
        return {
            "count": 0,
            "total_pnl": 0.0,
            "winners": 0,
            "losers": 0,
            "win_rate_pct": 0.0,
        }

    pnl = closed["pnl"].dropna()
    winners = int((pnl > 0).sum())
    losers = int((pnl < 0).sum())

    return {
        "count": len(closed),
        "total_pnl": float(pnl.sum()),
        "winners": winners,
        "losers": losers,
        "win_rate_pct": float(winners / len(pnl) * 100) if len(pnl) else 0.0,
    }
