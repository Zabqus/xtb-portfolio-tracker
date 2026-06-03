"""
Wykrywanie walut konta XTB oraz przeliczanie wartości portfela.
"""

from __future__ import annotations

import re

import pandas as pd

from core.market_data import fetch_fx_rate_to_pln_cached

# Waluta notowań wg sufiksu tickera XTB
SUFFIX_CURRENCY: dict[str, str] = {
    ".PL": "PLN",
    ".WA": "PLN",
    ".DE": "EUR",
    ".AS": "EUR",
    ".PA": "EUR",
    ".MI": "EUR",
    ".EU": "EUR",
    ".US": "USD",
    ".UK": "GBP",
    ".L": "GBP",
    ".SW": "CHF",
    ".ST": "SEK",
    ".CO": "DKK",
    ".HE": "EUR",
    ".MC": "EUR",
}

CONVERSION_RE = re.compile(
    r"Currency conversion,\s*(\w+)\s+to\s+(\w+)\s+from TA:\s*(\d+)\s+to:\s*(\d+)",
    re.IGNORECASE,
)

SUPPORTED_CURRENCIES = ("PLN", "EUR", "USD", "GBP")


def currency_from_ticker(ticker: str) -> str:
    """Przypisuje walutę notowań na podstawie sufiksu symbolu XTB."""
    normalized = str(ticker).strip().upper()
    for suffix, currency in sorted(SUFFIX_CURRENCY.items(), key=lambda x: -len(x[0])):
        if normalized.endswith(suffix):
            return currency
    if "." not in normalized:
        return "USD"
    return "EUR"


def read_account_number(meta_df: pd.DataFrame) -> str | None:
    """Numer konta z pierwszego wiersza eksportu XTB."""
    try:
        if str(meta_df.iloc[0, 0]).strip().lower() == "account number":
            val = meta_df.iloc[0, 1]
            return str(int(val)) if pd.notna(val) else None
    except (IndexError, ValueError, TypeError):
        pass
    return None


def detect_account_currency(
    cash_ops: pd.DataFrame,
    meta_df: pd.DataFrame | None = None,
    open_tickers: list[str] | None = None,
) -> str:
    """
    Wykrywa walutę konta rozliczeniowego XTB.

    Kolejność: konwersje walut w komentarzach → głosowanie po tickerach → EUR.
    """
    account_number = read_account_number(meta_df) if meta_df is not None else None

    if "Comment" in cash_ops.columns and account_number:
        for comment in cash_ops["Comment"].dropna().astype(str):
            match = CONVERSION_RE.search(comment)
            if not match:
                continue
            from_cur, to_cur, from_acc, to_acc = (
                match.group(1).upper(),
                match.group(2).upper(),
                match.group(3),
                match.group(4),
            )
            if to_acc == account_number:
                return to_cur
            if from_acc == account_number:
                return from_cur

    if open_tickers:
        votes: dict[str, int] = {}
        for ticker in open_tickers:
            cur = currency_from_ticker(ticker)
            votes[cur] = votes.get(cur, 0) + 1
        if votes:
            pln_weight = votes.get("PLN", 0)
            if pln_weight >= len(open_tickers) / 2:
                return "PLN"
            return max(votes, key=votes.get)

    return "EUR"


def _fx_rate(source: str, target: str, pln_cache: dict[str, float]) -> float:
    """Mnożnik: amount_in_source * rate = amount_in_target (via PLN hub)."""
    if source == target:
        return 1.0
    pln_per_src = fetch_fx_rate_to_pln_cached(source, pln_cache)
    pln_per_dst = fetch_fx_rate_to_pln_cached(target, pln_cache)
    return pln_per_src / pln_per_dst


def fetch_rates_to_currency(
    source_currencies: set[str],
    target_currency: str,
) -> dict[str, float]:
    """Pobiera kursy przeliczenia z każdej waluty źródłowej do waluty docelowej."""
    pln_cache: dict[str, float] = {}
    rates: dict[str, float] = {target_currency: 1.0}
    for currency in source_currencies:
        if currency not in rates:
            rates[currency] = _fx_rate(currency, target_currency, pln_cache)
    return rates


def convert_amount(
    amount: float,
    from_currency: str,
    to_currency: str,
    rates: dict[str, float],
) -> float:
    """Przelicza kwotę przy użyciu wcześniej pobranych kursów."""
    if pd.isna(amount):
        return float("nan")
    if from_currency == to_currency:
        return float(amount)
    return float(amount) * rates[from_currency]
