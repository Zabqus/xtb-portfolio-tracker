"""
Rozkład całkowitego wyniku portfela na składniki wodospadowe P&L.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.currencies import convert_amount, fetch_rates_to_currency
from core.dividends import parse_dividends

BELKA_RATE = 0.19
_NON_FX_CURRENCIES = frozenset({"MULTI", "", "<NA>", "NAN", "NONE"})


def _resolve_fx_currency(raw: object, fallback: str) -> str:
    """Zwraca prawdziwą walutę FX (MULTI / NaN → fallback)."""
    # Nie używać `raw or ...` — pd.NA nie ma bool().
    if raw is None or raw is pd.NA or (isinstance(raw, float) and pd.isna(raw)):
        code = ""
    else:
        code = str(raw).strip().upper()
        if code in ("NAN", "NONE", "<NA>"):
            code = ""
    if code in _NON_FX_CURRENCIES:
        fb = str(fallback).strip().upper() if fallback is not None else ""
        return fb if fb not in _NON_FX_CURRENCIES else "PLN"
    return code


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
        # Profit/Loss w eksporcie XTB jest w walucie konta, nie instrumentu.
        ccy = _resolve_fx_currency(
            row.get("account_currency") or row.get("currency"),
            target_currency,
        )
        total += convert_amount(float(row["pnl"]), ccy, target_currency, rates)
    return total


def _sum_dividends(
    cash_ops: pd.DataFrame | None,
    target_currency: str,
    rates: dict[str, float],
    default_currency: str,
) -> float:
    div = parse_dividends(cash_ops) if cash_ops is not None else pd.DataFrame()
    if div.empty:
        return 0.0
    fallback = _resolve_fx_currency(default_currency, target_currency)
    total = 0.0
    for _, row in div.iterrows():
        amount = float(row["amount"])
        source_currency = _resolve_fx_currency(row.get("currency"), fallback)
        total += convert_amount(amount, source_currency, target_currency, rates)
    return float(total)


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
    currency = _resolve_fx_currency(
        analyzed.attrs.get("display_currency", account_currency),
        "PLN",
    )
    rates = dict(analyzed.attrs.get("fx_rates", {currency: 1.0}))
    rates.setdefault(currency, 1.0)
    needed_currencies: set[str] = {currency}
    needed_currencies.update(
        str(c).upper()
        for c in analyzed.get("currency", pd.Series(dtype="object")).dropna().unique()
    )
    if closed is not None:
        if "account_currency" in closed.columns:
            needed_currencies.update(
                str(c).upper() for c in closed["account_currency"].dropna().unique()
            )
        if "currency" in closed.columns:
            needed_currencies.update(str(c).upper() for c in closed["currency"].dropna().unique())
    if cash_ops is not None and "account_currency" in cash_ops.columns:
        needed_currencies.update(
            str(c).upper() for c in cash_ops["account_currency"].dropna().unique()
        )
    else:
        needed_currencies.add(str(account_currency).upper())

    supported = {c for c in needed_currencies if c not in _NON_FX_CURRENCIES}
    missing_rates = supported - set(rates.keys())
    if missing_rates:
        rates.update(fetch_rates_to_currency(supported, currency))

    dividend_default = _resolve_fx_currency(account_currency, currency)

    valid = analyzed.dropna(subset=["pnl"])
    unrealized = float(valid["pnl"].sum()) if not valid.empty else 0.0
    realized = _sum_closed_pnl(closed, currency, rates)
    dividends = _sum_dividends(cash_ops, currency, rates, dividend_default)
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
