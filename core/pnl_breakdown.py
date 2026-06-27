"""
Rozkład całkowitego wyniku portfela na składniki wodospadowe P&L.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.currencies import convert_amount
from core.dividends import parse_dividends

BELKA_RATE = 0.19


@dataclass
class PnLBreakdown:
    unrealized_pnl: float
    realized_pnl: float
    dividends: float
    estimated_tax: float
    total_result: float
    currency: str
    has_data: bool


def _sum_closed_pnl(
    closed: pd.DataFrame | None,
    target_currency: str,
    rates: dict[str, float],
) -> float:
    if closed is None or closed.empty or "pnl" not in closed.columns:
        return 0.0
    total = 0.0
    for _, row in closed.dropna(subset=["pnl"]).iterrows():
        ccy = str(row.get("currency", target_currency))
        total += convert_amount(float(row["pnl"]), ccy, target_currency, rates)
    return total


def _sum_dividends(
    cash_ops: pd.DataFrame | None,
    target_currency: str,
    rates: dict[str, float],
    account_currency: str,
) -> float:
    div = parse_dividends(cash_ops) if cash_ops is not None else pd.DataFrame()
    if div.empty:
        return 0.0
    return float(
        sum(
            convert_amount(float(a), account_currency, target_currency, rates)
            for a in div["amount"]
        )
    )


def _estimate_tax(realized_pnl: float, dividends: float) -> float:
    """Szacunek podatku Belki 19% od dodatnich zysków kapitałowych i dywidend."""
    taxable = max(0.0, realized_pnl) + max(0.0, dividends)
    return taxable * BELKA_RATE


def compute_pnl_breakdown(
    analyzed: pd.DataFrame,
    *,
    closed: pd.DataFrame | None = None,
    cash_ops: pd.DataFrame | None = None,
    account_currency: str = "EUR",
) -> PnLBreakdown:
    """
    Składniki: niezrealizowany + zrealizowany + dywidendy − podatek = całkowity wynik.

    Wszystkie kwoty w walucie wyświetlania portfela.
    """
    currency = str(analyzed.attrs.get("display_currency", account_currency))
    rates = analyzed.attrs.get("fx_rates", {currency: 1.0})

    valid = analyzed.dropna(subset=["pnl"])
    unrealized = float(valid["pnl"].sum()) if not valid.empty else 0.0
    realized = _sum_closed_pnl(closed, currency, rates)
    dividends = _sum_dividends(cash_ops, currency, rates, account_currency)
    tax = _estimate_tax(realized, dividends)
    total = unrealized + realized + dividends - tax

    has_data = bool(valid.shape[0]) or realized != 0 or dividends != 0

    return PnLBreakdown(
        unrealized_pnl=unrealized,
        realized_pnl=realized,
        dividends=dividends,
        estimated_tax=tax,
        total_result=total,
        currency=currency,
        has_data=has_data,
    )
