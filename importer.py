"""
Moduł importu raportów pozycji z brokera XTB.
Obsługuje pliki CSV oraz Excel z uproszczonym formatem portfela.
"""

from __future__ import annotations

import io
from typing import BinaryIO, Union

import pandas as pd

# Mapowanie tickerów XTB → Yahoo Finance (rozszerz według własnego portfela)
TICKER_MAP: dict[str, str] = {
    "VWCE": "VWCE.DE",
    "IWDA": "IWDA.AS",
    "EIMI": "EIMI.L",
    "SXR8": "SXR8.DE",
    "VUAA": "VUAA.L",
    "CSPX": "CSPX.L",
    "AGGH": "AGGH.L",
    "PKN": "PKN.WA",
    "KGH": "KGH.WA",
    "CDR": "CDR.WA",
    "PEO": "PEO.WA",
    "ALE": "ALE.WA",
    "DNP": "DNP.WA",
    "PZU": "PZU.WA",
    "PKO": "PKO.WA",
    "MBK": "MBK.WA",
}

# Aliasy nazw kolumn w plikach eksportowych (wielkość liter ignorowana)
COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": ["ticker", "symbol", "instrument", "akcja", "papier"],
    "ilosc": ["ilosc", "ilość", "quantity", "qty", "szt", "sztuki", "volume"],
    "srednia_cena": [
        "srednia cena zakupu",
        "średnia cena zakupu",
        "srednia_cena",
        "avg price",
        "average price",
        "cena zakupu",
        "purchase price",
        "open price",
    ],
}

REQUIRED_COLUMNS = ("ticker", "ilosc", "srednia_cena")


def map_ticker_to_yahoo(ticker: str) -> str:
    """
    Konwertuje symbol z XTB na format rozpoznawany przez Yahoo Finance.

    Jeśli ticker już zawiera sufiks giełdy (np. VWCE.DE), zwraca go bez zmian.
    W przeciwnym razie szuka w słowniku TICKER_MAP lub zwraca oryginał.
    """
    normalized = str(ticker).strip().upper()
    if not normalized:
        raise ValueError("Pusty symbol instrumentu.")

    # Ticker już w formacie Yahoo (np. VWCE.DE, AAPL)
    if "." in normalized:
        return normalized

    return TICKER_MAP.get(normalized, normalized)


def _normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Dopasowuje nazwy kolumn pliku do standardowych pól portfela."""
    rename_map: dict[str, str] = {}
    lower_cols = {str(col).strip().lower(): col for col in df.columns}

    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                rename_map[lower_cols[alias]] = target
                break

    missing = [col for col in REQUIRED_COLUMNS if col not in rename_map.values()]
    if missing:
        raise ValueError(
            f"Brak wymaganych kolumn: {', '.join(missing)}. "
            f"Oczekiwane pola: Ticker, Ilość, Średnia cena zakupu."
        )

    return df.rename(columns=rename_map)[list(REQUIRED_COLUMNS)]


def _read_file(source: Union[str, BinaryIO, io.BytesIO], filename: str) -> pd.DataFrame:
    """Wczytuje DataFrame z pliku CSV lub Excel na podstawie rozszerzenia."""
    name = filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(source)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(source)
    raise ValueError("Obsługiwane formaty: .csv, .xlsx, .xls")


def parse_xtb_report(
    file_source: Union[str, BinaryIO, io.BytesIO],
    filename: str,
) -> pd.DataFrame:
    """
    Parsuje raport XTB i zwraca ustandaryzowany DataFrame portfela.

    Kolumny wyjściowe:
        - ticker_xtb: symbol z raportu
        - ticker_yahoo: symbol dla yfinance
        - ilosc: liczba jednostek
        - srednia_cena: średnia cena zakupu (koszt jednostkowy)
    """
    raw_df = _read_file(file_source, filename)
    df = _normalize_column_names(raw_df)

    df["ticker_xtb"] = df["ticker"].astype(str).str.strip().str.upper()
    df["ticker_yahoo"] = df["ticker_xtb"].apply(map_ticker_to_yahoo)
    df["ilosc"] = pd.to_numeric(df["ilosc"], errors="coerce")
    df["srednia_cena"] = pd.to_numeric(df["srednia_cena"], errors="coerce")

    if df[["ilosc", "srednia_cena"]].isna().any().any():
        raise ValueError("Kolumny Ilość i Średnia cena muszą zawierać wartości liczbowe.")

    if (df["ilosc"] <= 0).any():
        raise ValueError("Ilość każdej pozycji musi być większa od zera.")

    return df[["ticker_xtb", "ticker_yahoo", "ilosc", "srednia_cena"]].reset_index(drop=True)
