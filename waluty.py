"""
Wykrywanie walut konta XTB oraz przeliczanie wartości portfela.
"""

from __future__ import annotations

import re
from typing import BinaryIO, Union

import io

import pandas as pd
import yfinance as yf

# Waluta notowań wg sufiksu tickera XTB (na podstawie ticker_xtb)
SUFIKS_WALUTA: dict[str, str] = {
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

# Kursy względem PLN (ile PLN za 1 jednostkę waluty) – Yahoo Finance
YAHOO_PLN_PAIR: dict[str, str] = {
    "EUR": "EURPLN=X",
    "USD": "USDPLN=X",
    "GBP": "GBPPLN=X",
    "CHF": "CHFPLN=X",
}

CONVERSION_RE = re.compile(
    r"Currency conversion,\s*(\w+)\s+to\s+(\w+)\s+from TA:\s*(\d+)\s+to:\s*(\d+)",
    re.IGNORECASE,
)

WALUTY_WSPIERANE = ("PLN", "EUR", "USD", "GBP")


def waluta_z_tickera(ticker: str) -> str:
    """Przypisuje walutę notowań na podstawie sufiksu symbolu XTB."""
    normalized = str(ticker).strip().upper()
    for suffix, currency in sorted(SUFIKS_WALUTA.items(), key=lambda x: -len(x[0])):
        if normalized.endswith(suffix):
            return currency
    # Akcje USA bez sufiksu po mapowaniu – domyślnie USD
    if "." not in normalized:
        return "USD"
    return "EUR"


def _odczytaj_numer_konta(meta_df: pd.DataFrame) -> str | None:
    """Numer konta z pierwszego wiersza eksportu XTB."""
    try:
        if str(meta_df.iloc[0, 0]).strip().lower() == "account number":
            val = meta_df.iloc[0, 1]
            return str(int(val)) if pd.notna(val) else None
    except (IndexError, ValueError, TypeError):
        pass
    return None


def wykryj_walute_konta(
    cash_ops: pd.DataFrame,
    meta_df: pd.DataFrame | None = None,
    tickery_otwarte: list[str] | None = None,
) -> str:
    """
    Wykrywa walutę konta rozliczeniowego XTB.

    Kolejność: konwersje walut w komentarzach → głosowanie po tickerach → EUR.
    """
    numer_konta = _odczytaj_numer_konta(meta_df) if meta_df is not None else None

    if "Comment" in cash_ops.columns and numer_konta:
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
            if to_acc == numer_konta:
                return to_cur
            if from_acc == numer_konta:
                return from_cur

    # Heurystyka: dominująca waluta instrumentów na koncie PLN
    if tickery_otwarte:
        votes: dict[str, int] = {}
        for ticker in tickery_otwarte:
            cur = waluta_z_tickera(ticker)
            votes[cur] = votes.get(cur, 0) + 1
        if votes:
            pln_weight = votes.get("PLN", 0)
            if pln_weight >= len(tickery_otwarte) / 2:
                return "PLN"
            return max(votes, key=votes.get)

    return "EUR"


def _kurs_do_pln(waluta: str, cache: dict[str, float]) -> float:
    """Ile PLN za 1 jednostkę danej waluty."""
    if waluta == "PLN":
        return 1.0
    if waluta in cache:
        return cache[waluta]
    symbol = YAHOO_PLN_PAIR.get(waluta)
    if not symbol:
        raise ValueError(f"Brak pary kursowej do PLN dla waluty: {waluta}")
    hist = yf.Ticker(symbol).history(period="5d")
    if hist.empty:
        raise ValueError(f"Brak kursu FX: {symbol}")
    close = hist["Close"]
    rate = float(close.iloc[-1]) if hasattr(close.iloc[-1], "__float__") else float(close.iloc[-1].item())
    cache[waluta] = rate
    return rate


def _pobierz_kurs_fx(zrodlo: str, cel: str, cache: dict[str, float]) -> float:
    """Zwraca mnożnik: kwota_w_zrodle * kurs = kwota_w_celu (przeliczenie przez PLN)."""
    if zrodlo == cel:
        return 1.0
    pln_per_src = _kurs_do_pln(zrodlo, cache)
    pln_per_dst = _kurs_do_pln(cel, cache)
    return pln_per_src / pln_per_dst


def pobierz_kursy_do_waluty(
    waluty_zrodlowe: set[str],
    waluta_docelowa: str,
) -> dict[str, float]:
    """Pobiera kursy przeliczenia z każdej waluty źródłowej do waluty docelowej."""
    cache: dict[str, float] = {}
    rates: dict[str, float] = {waluta_docelowa: 1.0}
    for waluta in waluty_zrodlowe:
        if waluta not in rates:
            rates[waluta] = _pobierz_kurs_fx(waluta, waluta_docelowa, cache)
    return rates


def przelicz_kwote(kwota: float, z_waluty: str, na_walute: str, kursy: dict[str, float]) -> float:
    """Przelicza kwotę przy użyciu wcześniej pobranych kursów."""
    if pd.isna(kwota):
        return float("nan")
    if z_waluty == na_walute:
        return float(kwota)
    return float(kwota) * kursy[z_waluty]
