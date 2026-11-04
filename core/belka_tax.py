"""
Szacunek podatku Belki (19%) z Closed Positions + dywidend + WHT + przeniesienia strat.

Kwoty przeliczane na PLN kursem NBP z daty zdarzenia (fallback: bez przeliczenia,
gdy konto już w PLN lub kurs niedostępny).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.dividends import parse_dividends, parse_withholding_tax
from core.nbp_fx import nbp_amount_to_pln
from core.tax_harvest import BELKA_RATE
from core.tax_loss_carry import CarryApplication, CarryEntry, apply_carry_forward, load_carry_entries

FX_NBP = "nbp"
FX_ACCOUNT = "account"
FX_MIXED = "mixed"


@dataclass
class BelkaYearSummary:
    tax_year: int
    currency: str  # zawsze "PLN" gdy udało się NBP; inaczej waluta konta
    fx_method: str

    capital_gains: float
    capital_losses: float
    capital_net: float
    carry_applied: float
    capital_base: float
    capital_tax: float

    dividends_gross: float
    withholding_tax: float  # zapłacony u źródła (kwota dodatnia)
    dividend_tax_gross: float
    dividend_tax_credit: float
    dividend_tax_after_wht: float

    total_tax: float
    nbp_converted_rows: int = 0
    nbp_failed_rows: int = 0
    closed_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    dividends_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    wht_detail: pd.DataFrame = field(default_factory=pd.DataFrame)
    carry: CarryApplication | None = None


def _row_account_currency(row: pd.Series, fallback: str) -> str:
    for key in ("account_currency", "AccountCurrency"):
        if key in row.index and pd.notna(row[key]):
            code = str(row[key]).strip().upper()
            if code and code not in {"MULTI", "NAN", "NONE", "<NA>"}:
                return code
    return str(fallback).strip().upper() or "PLN"


def _to_pln_series(
    amounts: pd.Series,
    currencies: pd.Series,
    dates: pd.Series,
) -> tuple[pd.Series, int, int]:
    """Zwraca (pln_amounts, converted_ok, failed)."""
    cache: dict = {}
    values: list[float] = []
    ok = 0
    failed = 0
    for amount, ccy, dt in zip(amounts, currencies, dates, strict=False):
        if pd.isna(amount) or pd.isna(dt):
            values.append(float("nan"))
            failed += 1
            continue
        code = str(ccy).strip().upper() if pd.notna(ccy) else "PLN"
        if code == "PLN":
            values.append(float(amount))
            ok += 1
            continue
        converted = nbp_amount_to_pln(float(amount), code, dt, rate_cache=cache)
        if converted is None:
            values.append(float(amount))  # fallback: zostaw w walucie źródłowej
            failed += 1
        else:
            values.append(float(converted))
            ok += 1
    return pd.Series(values, index=amounts.index, dtype=float), ok, failed


def prepare_closed_for_tax(
    closed: pd.DataFrame,
    account_currency: str,
) -> pd.DataFrame:
    """Dodaje tax_year oraz pnl_pln (NBP)."""
    if closed is None or closed.empty:
        return pd.DataFrame()
    df = closed.copy()
    if "close_time" not in df.columns or "pnl" not in df.columns:
        return pd.DataFrame()
    df["close_dt"] = pd.to_datetime(df["close_time"], errors="coerce")
    df = df.dropna(subset=["close_dt", "pnl"])
    if df.empty:
        return pd.DataFrame()
    df["tax_year"] = df["close_dt"].dt.year.astype(int)
    df["pnl_ccy"] = df.apply(lambda r: _row_account_currency(r, account_currency), axis=1)
    pln, ok, failed = _to_pln_series(df["pnl"], df["pnl_ccy"], df["close_dt"])
    df["pnl_pln"] = pln
    df.attrs["nbp_ok"] = ok
    df.attrs["nbp_failed"] = failed
    return df


def compute_belka_year(
    closed: pd.DataFrame | None,
    cash_ops: pd.DataFrame | None,
    tax_year: int,
    account_currency: str,
    *,
    carry_entries: list[CarryEntry] | None = None,
    apply_persist_carry: bool = False,
) -> BelkaYearSummary:
    """Pełny szacunek Belki dla wskazanego roku podatkowego (w PLN)."""
    year = int(tax_year)
    acc = str(account_currency or "PLN").upper()
    if acc == "MULTI":
        acc = "PLN"

    closed_year = pd.DataFrame()
    nbp_ok = 0
    nbp_fail = 0
    if closed is not None and not closed.empty:
        prepared = prepare_closed_for_tax(closed, acc)
        if not prepared.empty:
            closed_year = prepared[prepared["tax_year"] == year].copy()
            nbp_ok = int(prepared.attrs.get("nbp_ok", 0))
            nbp_fail = int(prepared.attrs.get("nbp_failed", 0))

    gains = float(closed_year.loc[closed_year["pnl_pln"] > 0, "pnl_pln"].sum()) if not closed_year.empty else 0.0
    losses = float(closed_year.loc[closed_year["pnl_pln"] < 0, "pnl_pln"].sum()) if not closed_year.empty else 0.0
    capital_net = gains + losses

    entries = carry_entries if carry_entries is not None else load_carry_entries()
    carry = apply_carry_forward(
        year, capital_net, entries, persist=apply_persist_carry
    )
    capital_base = max(0.0, capital_net - carry.applied) if capital_net > 0 else 0.0
    if capital_net <= 0:
        capital_base = 0.0
    capital_tax = capital_base * BELKA_RATE

    # Dywidendy + WHT
    div = parse_dividends(cash_ops) if cash_ops is not None else pd.DataFrame()
    wht = parse_withholding_tax(cash_ops) if cash_ops is not None else pd.DataFrame()

    div_year = pd.DataFrame()
    dividends_gross = 0.0
    if not div.empty:
        div_year = div[div["year"] == year].copy()
        if not div_year.empty:
            ccy = div_year["currency"].fillna(acc) if "currency" in div_year.columns else acc
            if isinstance(ccy, str):
                ccy = pd.Series(acc, index=div_year.index)
            pln, ok, fail = _to_pln_series(div_year["amount"], ccy, div_year["date"])
            div_year["amount_pln"] = pln
            dividends_gross = float(pln.sum())
            nbp_ok += ok
            nbp_fail += fail

    wht_year = pd.DataFrame()
    withholding = 0.0
    if not wht.empty:
        wht_year = wht[wht["year"] == year].copy()
        if not wht_year.empty:
            ccy = wht_year["currency"].fillna(acc) if "currency" in wht_year.columns else acc
            if isinstance(ccy, str):
                ccy = pd.Series(acc, index=wht_year.index)
            # WHT w Cash Ops zwykle ujemne — bierzemy wartość bezwzględną jako kredyt
            abs_amt = wht_year["amount"].abs()
            pln, ok, fail = _to_pln_series(abs_amt, ccy, wht_year["date"])
            wht_year["amount_pln"] = pln
            withholding = float(pln.sum())
            nbp_ok += ok
            nbp_fail += fail

    dividend_tax_gross = max(0.0, dividends_gross) * BELKA_RATE
    # Kredyt WHT nie może przekroczyć polskiego podatku od tych dywidend
    dividend_tax_credit = min(withholding, dividend_tax_gross)
    dividend_tax_after = max(0.0, dividend_tax_gross - dividend_tax_credit)

    if nbp_fail == 0 and (nbp_ok > 0 or acc == "PLN"):
        fx_method = FX_NBP if acc != "PLN" or nbp_ok > 0 else FX_ACCOUNT
        if acc == "PLN" and nbp_fail == 0:
            fx_method = FX_NBP if nbp_ok > 0 else FX_ACCOUNT
    elif nbp_ok > 0 and nbp_fail > 0:
        fx_method = FX_MIXED
    else:
        fx_method = FX_ACCOUNT

    # Upraszczamy etykietę: przy czystym PLN bez konwersji nadal mówimy NBP/PLN
    if acc == "PLN" and nbp_fail == 0:
        fx_method = FX_NBP

    return BelkaYearSummary(
        tax_year=year,
        currency="PLN",
        fx_method=fx_method,
        capital_gains=gains,
        capital_losses=losses,
        capital_net=capital_net,
        carry_applied=float(carry.applied),
        capital_base=capital_base,
        capital_tax=capital_tax,
        dividends_gross=dividends_gross,
        withholding_tax=withholding,
        dividend_tax_gross=dividend_tax_gross,
        dividend_tax_credit=dividend_tax_credit,
        dividend_tax_after_wht=dividend_tax_after,
        total_tax=capital_tax + dividend_tax_after,
        nbp_converted_rows=nbp_ok,
        nbp_failed_rows=nbp_fail,
        closed_detail=closed_year.sort_values("close_dt") if not closed_year.empty else closed_year,
        dividends_detail=div_year,
        wht_detail=wht_year,
        carry=carry,
    )
