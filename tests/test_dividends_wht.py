"""Parsowanie dywidend i WHT z Cash Operations."""

from __future__ import annotations

import pandas as pd

from core.dividends import (
    parse_dividends,
    parse_withholding_tax,
    withholding_by_year,
    withholding_summary,
)


def _ops(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_parse_dividends_and_wht_separate():
    cash = _ops(
        [
            {
                "Type": "Dividend",
                "Time": "2024-03-15",
                "Ticker": "AAPL.US",
                "Amount": 100.0,
                "Currency": "USD",
                "Comment": "Dividend",
            },
            {
                "Type": "Withholding tax",
                "Time": "2024-03-15",
                "Ticker": "AAPL.US",
                "Amount": -15.0,
                "Currency": "USD",
                "Comment": "WHT 15%",
            },
            {
                "Type": "Podatek u źródła",
                "Time": "2023-06-01",
                "Ticker": "MSFT.US",
                "Amount": -8.0,
                "Currency": "USD",
                "Comment": "",
            },
        ]
    )
    div = parse_dividends(cash)
    wht = parse_withholding_tax(cash)
    assert len(div) == 1
    assert float(div.iloc[0]["amount"]) == 100.0
    assert len(wht) == 2
    by_year = withholding_by_year(wht)
    assert list(by_year["year"]) == [2023, 2024]
    assert float(by_year.loc[by_year["year"] == 2024, "amount"].iloc[0]) == 15.0
    summary = withholding_summary(wht, current_year=2024)
    assert summary["total"] == 23.0
    assert summary["current_year"] == 15.0
    assert summary["count"] == 2


def test_empty_cash_ops():
    assert parse_dividends(pd.DataFrame()).empty
    assert parse_withholding_tax(None).empty
    assert withholding_by_year(pd.DataFrame()).empty
