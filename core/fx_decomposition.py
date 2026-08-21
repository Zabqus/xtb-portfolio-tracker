"""
Dekompozycja niezrealizowanego PnL na efekt ceny i efekt waluty (FX).

Wzór (per pozycja, w walucie wyświetlania):
  kurs zakupu ≈ position_cost / cost_native  (albo z Amount w Cash Ops, gdy dostępne)
  efekt ceny  = pnl_native × kurs zakupu
  efekt FX    = PnL − efekt ceny

Gdy analyzer przelicza koszt i wartość tym samym bieżącym kursem, efekt FX z samego
position_cost jest ~0. Wtedy, jeśli są transakcje z Amount, szacujemy średni kurs
zakupu z FIFO otwartych lotów (Amount w walucie konta / koszt native) — bez zapytań sieciowych.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.currencies import convert_amount, fetch_rates_to_currency

MIN_QTY = 1e-9
MIN_COST = 1e-12


@dataclass
class FxDecompositionSummary:
    price_effect: float
    fx_effect: float
    total_pnl: float
    currency: str
    has_data: bool
    used_trade_rates: bool
    foreign_positions: int


def _implied_purchase_rates_from_trades(
    trades: pd.DataFrame,
    tickers: set[str],
    *,
    display_currency: str,
    rates: dict[str, float],
    default_account_currency: str,
) -> dict[str, float]:
    """
    Średni kurs zakupu (instrument → display) z pozostałych lotów FIFO.

    Amount z Cash Operations jest w walucie konta; price×qty w walucie instrumentu.
    """
    if trades is None or trades.empty or not tickers:
        return {}

    required = {"ticker_xtb", "side", "quantity", "price"}
    if not required.issubset(trades.columns):
        return {}

    has_amount = "amount" in trades.columns
    has_account_ccy = "account_currency" in trades.columns
    has_label = "account_label" in trades.columns

    sorted_trades = trades.sort_values("trade_time") if "trade_time" in trades.columns else trades
    lots: dict[str, list[dict[str, float | str]]] = {t: [] for t in tickers}

    for _, row in sorted_trades.iterrows():
        ticker = str(row["ticker_xtb"])
        if ticker not in lots:
            continue
        qty = float(row["quantity"])
        price = float(row["price"])
        if qty <= 0 or price < 0 or pd.isna(qty) or pd.isna(price):
            continue

        side = str(row["side"]).upper()
        native = qty * price

        if side == "OPEN":
            account_ccy = default_account_currency
            if has_account_ccy and pd.notna(row.get("account_currency")):
                account_ccy = str(row["account_currency"]).upper()
            elif has_label and pd.notna(row.get("account_label")):
                label = str(row["account_label"]).strip().upper()
                token = label.split()[0].split("(")[0].strip()
                if token in ("PLN", "EUR", "USD", "GBP", "CHF"):
                    account_ccy = token

            account_cost: float | None
            if has_amount and pd.notna(row.get("amount")):
                account_cost = abs(float(row["amount"]))
                if account_cost <= MIN_COST:
                    account_cost = None
            else:
                account_cost = None

            lots[ticker].append(
                {
                    "qty": qty,
                    "native": native,
                    "account_cost": account_cost,
                    "account_ccy": account_ccy,
                }
            )
        elif side in ("CLOSE", "SELL"):
            remaining = qty
            while remaining > MIN_QTY and lots[ticker]:
                lot = lots[ticker][0]
                lot_qty = float(lot["qty"])
                take = min(lot_qty, remaining)
                frac = take / lot_qty if lot_qty > MIN_QTY else 1.0
                lot["qty"] = lot_qty - take
                lot["native"] = float(lot["native"]) * (1.0 - frac)
                if lot["account_cost"] is not None:
                    lot["account_cost"] = float(lot["account_cost"]) * (1.0 - frac)
                remaining -= take
                if float(lot["qty"]) <= MIN_QTY:
                    lots[ticker].pop(0)

    out: dict[str, float] = {}
    for ticker, open_lots in lots.items():
        if not open_lots:
            continue
        # Wszystkie pozostałe loty muszą mieć Amount — inaczej nie szacujemy kursu zakupu.
        if any(lot["account_cost"] is None for lot in open_lots):
            continue
        native_sum = sum(float(l["native"]) for l in open_lots)
        if native_sum <= MIN_COST:
            continue

        cost_display = 0.0
        for lot in open_lots:
            acc_ccy = str(lot["account_ccy"])
            cost_display += convert_amount(
                float(lot["account_cost"]),
                acc_ccy,
                display_currency,
                rates,
            )
        out[ticker] = cost_display / native_sum
    return out


def compute_fx_decomposition(
    analyzed: pd.DataFrame,
    *,
    trades: pd.DataFrame | None = None,
    account_currency: str = "EUR",
) -> pd.DataFrame:
    """
    Zwraca kopię analyzed z kolumnami:
      fx_rate_purchase, pnl_price, pnl_fx, pnl_fx_total, fx_rate_source
    """
    if analyzed is None or analyzed.empty:
        return pd.DataFrame()

    display = str(analyzed.attrs.get("display_currency", account_currency)).upper()
    rates = dict(analyzed.attrs.get("fx_rates", {display: 1.0}))
    rates.setdefault(display, 1.0)

    result = analyzed.copy()
    tickers = set(result["ticker_xtb"].astype(str)) if "ticker_xtb" in result.columns else set()

    needed = {display, str(account_currency).upper()}
    if "account_currency" in result.columns:
        needed.update(
            str(c).upper()
            for c in result["account_currency"].dropna().unique()
            if str(c).upper() not in ("MULTI", "NAN", "NONE", "<NA>", "")
        )
    if "currency" in result.columns:
        needed.update(str(c).upper() for c in result["currency"].dropna().unique())
    missing = {c for c in needed if c not in rates}
    if missing:
        rates.update(fetch_rates_to_currency(needed, display))

    trade_rates = _implied_purchase_rates_from_trades(
        trades if trades is not None else pd.DataFrame(),
        tickers,
        display_currency=display,
        rates=rates,
        default_account_currency=str(account_currency).upper(),
    )

    fx_rate_purchase: list[float] = []
    pnl_price: list[float] = []
    pnl_fx: list[float] = []
    pnl_fx_total: list[float] = []
    fx_rate_source: list[str] = []

    for _, row in result.iterrows():
        cost_n = row.get("cost_native")
        pnl_n = row.get("pnl_native")
        position_cost = row.get("position_cost")
        market_value = row.get("market_value")
        analyzer_pnl = row.get("pnl")
        ticker = str(row.get("ticker_xtb", ""))
        instr_ccy = str(row.get("currency", display)).upper()

        if (
            pd.isna(cost_n)
            or pd.isna(pnl_n)
            or float(cost_n) <= MIN_COST
            or pd.isna(analyzer_pnl)
        ):
            fx_rate_purchase.append(float("nan"))
            pnl_price.append(float("nan"))
            pnl_fx.append(float("nan"))
            pnl_fx_total.append(float("nan"))
            fx_rate_source.append("missing")
            continue

        cost_n_f = float(cost_n)
        pnl_n_f = float(pnl_n)

        # Domyślnie: wzór z analyzera (kurs ≈ bieżący → efekt FX ~0).
        rate = float(position_cost) / cost_n_f if pd.notna(position_cost) else 1.0
        source = "analyzer"
        total = float(analyzer_pnl)

        trade_rate = trade_rates.get(ticker)
        if trade_rate is not None and trade_rate > 0 and pd.notna(market_value):
            # Kurs z Cash Ops — PnL ekonomiczny z kosztem zablokowanym na kursie zakupu.
            rate = float(trade_rate)
            source = "trades"
            total = float(market_value) - cost_n_f * rate
        elif instr_ccy == display:
            rate = 1.0
            source = "same_currency"
            total = float(analyzer_pnl)

        price = pnl_n_f * rate
        fx = total - price

        fx_rate_purchase.append(rate)
        pnl_price.append(price)
        pnl_fx.append(fx)
        pnl_fx_total.append(total)
        fx_rate_source.append(source)

    result["fx_rate_purchase"] = fx_rate_purchase
    result["pnl_price"] = pnl_price
    result["pnl_fx"] = pnl_fx
    result["pnl_fx_total"] = pnl_fx_total
    result["fx_rate_source"] = fx_rate_source
    result.attrs["display_currency"] = display
    result.attrs["fx_rates"] = rates
    return result


def summarize_fx_decomposition(decomposed: pd.DataFrame) -> FxDecompositionSummary:
    """Agregacja portfelowa efektu ceny vs FX."""
    currency = str(decomposed.attrs.get("display_currency", "PLN")) if decomposed is not None else "PLN"
    if decomposed is None or decomposed.empty:
        return FxDecompositionSummary(
            price_effect=0.0,
            fx_effect=0.0,
            total_pnl=0.0,
            currency=currency,
            has_data=False,
            used_trade_rates=False,
            foreign_positions=0,
        )

    valid = decomposed.dropna(subset=["pnl_price", "pnl_fx", "pnl_fx_total"])
    if valid.empty:
        return FxDecompositionSummary(
            price_effect=0.0,
            fx_effect=0.0,
            total_pnl=0.0,
            currency=currency,
            has_data=False,
            used_trade_rates=False,
            foreign_positions=0,
        )

    display = currency.upper()
    foreign = 0
    if "currency" in valid.columns:
        foreign = int((valid["currency"].astype(str).str.upper() != display).sum())

    used_trades = False
    if "fx_rate_source" in valid.columns:
        used_trades = bool((valid["fx_rate_source"] == "trades").any())

    return FxDecompositionSummary(
        price_effect=float(valid["pnl_price"].sum()),
        fx_effect=float(valid["pnl_fx"].sum()),
        total_pnl=float(valid["pnl_fx_total"].sum()),
        currency=currency,
        has_data=True,
        used_trade_rates=used_trades,
        foreign_positions=foreign,
    )
