"""Belka: NBP (mock), WHT credit, carry-forward."""

from __future__ import annotations

import pandas as pd

from core.belka_tax import compute_belka_year
from core.tax_loss_carry import CarryEntry


def test_belka_pln_with_wht_and_carry(monkeypatch):
    monkeypatch.setattr(
        "core.belka_tax.nbp_amount_to_pln",
        lambda amount, currency, on_date, rate_cache=None: float(amount),
    )

    closed = pd.DataFrame(
        {
            "ticker_xtb": ["AAA.US", "BBB.US"],
            "close_time": [pd.Timestamp("2024-05-10"), pd.Timestamp("2024-08-01")],
            "pnl": [10_000.0, -2_000.0],
            "account_currency": ["PLN", "PLN"],
        }
    )
    cash = pd.DataFrame(
        {
            "Type": ["Dividend", "Withholding tax"],
            "Time": ["2024-06-01", "2024-06-01"],
            "Ticker": ["AAA.US", "AAA.US"],
            "Amount": [1_000.0, -150.0],
            "Currency": ["PLN", "PLN"],
            "Comment": ["", ""],
        }
    )
    carry = [CarryEntry(origin_year=2023, original_loss=4_000.0)]

    summary = compute_belka_year(
        closed,
        cash,
        2024,
        "PLN",
        carry_entries=carry,
    )

    assert summary.capital_gains == 10_000.0
    assert summary.capital_losses == -2_000.0
    assert summary.capital_net == 8_000.0
    # 50% of 4000 = 2000 carry
    assert summary.carry_applied == 2_000.0
    assert summary.capital_base == 6_000.0
    assert abs(summary.capital_tax - 6_000.0 * 0.19) < 1e-9

    assert summary.dividends_gross == 1_000.0
    assert summary.withholding_tax == 150.0
    assert abs(summary.dividend_tax_gross - 190.0) < 1e-9
    assert summary.dividend_tax_credit == 150.0
    assert abs(summary.dividend_tax_after_wht - 40.0) < 1e-9
    assert abs(summary.total_tax - (summary.capital_tax + 40.0)) < 1e-9


def test_belka_eur_uses_nbp_mock(monkeypatch):
    def fake_nbp(amount, currency, on_date, rate_cache=None):
        assert str(currency).upper() == "EUR"
        return float(amount) * 4.0

    monkeypatch.setattr("core.belka_tax.nbp_amount_to_pln", fake_nbp)

    closed = pd.DataFrame(
        {
            "ticker_xtb": ["VWCE"],
            "close_time": [pd.Timestamp("2024-01-15")],
            "pnl": [100.0],
        }
    )
    summary = compute_belka_year(closed, None, 2024, "EUR", carry_entries=[])
    assert summary.capital_gains == 400.0
    assert summary.currency == "PLN"
    assert abs(summary.capital_tax - 400.0 * 0.19) < 1e-9


def test_wht_credit_capped_at_pl_tax(monkeypatch):
    monkeypatch.setattr(
        "core.belka_tax.nbp_amount_to_pln",
        lambda amount, currency, on_date, rate_cache=None: float(amount),
    )
    closed = pd.DataFrame(
        {
            "ticker_xtb": ["X"],
            "close_time": [pd.Timestamp("2024-01-01")],
            "pnl": [0.0],
        }
    )
    cash = pd.DataFrame(
        {
            "Type": ["Dividend", "Withholding tax"],
            "Time": ["2024-02-01", "2024-02-01"],
            "Ticker": ["X", "X"],
            "Amount": [100.0, -50.0],  # WHT > 19%
            "Currency": ["PLN", "PLN"],
            "Comment": ["", ""],
        }
    )
    summary = compute_belka_year(closed, cash, 2024, "PLN", carry_entries=[])
    assert summary.dividend_tax_gross == 19.0
    assert summary.dividend_tax_credit == 19.0
    assert summary.dividend_tax_after_wht == 0.0
