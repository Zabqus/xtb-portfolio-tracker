"""
Portfolio analytics – market prices, FX conversion, PnL metrics.
"""

from __future__ import annotations

import pandas as pd

from core.currencies import convert_amount, fetch_rates_to_currency
from core.market_data import fetch_last_prices


def _normalize_market_price_units(df: pd.DataFrame) -> pd.DataFrame:
    """
    Korekta jednostek cen Yahoo dla LSE.

    Dla tickerów `.L` Yahoo często zwraca cenę w GBp (pensach), podczas gdy
    XTB zapisuje średni koszt pozycji w GBP.
    """
    if "ticker_yahoo" not in df.columns or "currency" not in df.columns or "market_price" not in df.columns:
        return df
    out = df.copy()
    lse_mask = (
        out["ticker_yahoo"].astype(str).str.upper().str.endswith(".L")
        & out["currency"].astype(str).str.upper().eq("GBP")
    )
    if lse_mask.any():
        out.loc[lse_mask, "market_price"] = out.loc[lse_mask, "market_price"] / 100.0
    return out


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
    result = _normalize_market_price_units(result)

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
    if "account_label" in result.columns:
        result.attrs["account_labels"] = tuple(
            sorted(result["account_label"].dropna().unique())
        )
    return result


def portfolio_summary_by_account(analyzed: pd.DataFrame) -> pd.DataFrame | None:
    """Podsumowanie per konto (tylko gdy jest kolumna account_label)."""
    if "account_label" not in analyzed.columns:
        return None
    valid = analyzed.dropna(subset=["market_value", "position_cost"])
    if valid.empty:
        return None

    rows: list[dict] = []
    for label, grp in valid.groupby("account_label", sort=True):
        cost = float(grp["position_cost"].sum())
        value = float(grp["market_value"].sum())
        pnl = value - cost
        rows.append(
            {
                "account_label": label,
                "positions": len(grp),
                "market_value": value,
                "position_cost": cost,
                "pnl": pnl,
                "roi_pct": (pnl / cost * 100) if cost > 0 else 0.0,
            }
        )
    return pd.DataFrame(rows)


def portfolio_summary(analyzed: pd.DataFrame) -> dict[str, float | str]:
    """Zagregowane metryki portfela w walucie wyświetlania."""
    valid = analyzed.dropna(subset=["market_value", "position_cost"])
    total_value = valid["market_value"].sum()
    total_cost = valid["position_cost"].sum()
    total_pnl = total_value - total_cost
    total_roi = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    out: dict[str, float | str] = {
        "total_value": float(total_value),
        "total_cost": float(total_cost),
        "total_pnl": float(total_pnl),
        "total_roi_pct": float(total_roi),
        "display_currency": analyzed.attrs.get("display_currency", "PLN"),
        "account_currency": analyzed.attrs.get("account_currency", "PLN"),
    }
    if analyzed.attrs.get("account_labels"):
        out["account_labels"] = analyzed.attrs["account_labels"]
        out["is_merged"] = True
    return out


def closed_positions_summary(closed: pd.DataFrame) -> dict[str, float | int]:
    """Statystyki zamkniętych pozycji z arkusza XTB."""
    from core.closed_analysis import closed_positions_summary as _summary

    return _summary(closed)
