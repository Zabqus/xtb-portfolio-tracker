"""
Moduł importu raportów pozycji z brokera XTB.

Obsługiwane formaty:
1. Natywny eksport XTB (Excel) – arkusz „Cash Operations” z historią transakcji.
2. Uproszczony CSV/Excel – kolumny: Ticker, Ilość, Średnia cena zakupu.
"""

from __future__ import annotations

import io
import re
from typing import BinaryIO, Union

import pandas as pd

# Mapowanie tickerów XTB → Yahoo Finance (gdy brak sufiksu giełdy w pliku)
TICKER_MAP: dict[str, str] = {
    "VWCE": "VWCE.DE",
    "IWDA": "IWDA.AS",
    "EIMI": "EIMI.L",
    "SXR8": "SXR8.DE",
    "EUNK": "EUNK.DE",
    "XAIX": "XAIX.DE",
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

# Aliasy nazw kolumn w uproszczonym formacie (wielkość liter ignorowana)
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

# Arkusz i typy operacji w natywnym eksporcie XTB
XTB_CASH_OPERATIONS_SHEET = "Cash Operations"
XTB_CASH_HEADER_ROW = 4  # wiersz z nagłówkami Type, Ticker, Comment…
XTB_TRADE_TYPES = ("Stock purchase", "Stock sell")

# OPEN BUY 9 @ 0.7919  |  OPEN BUY 0.6021/1.6021 @ 162.24  |  CLOSE BUY 11/50 @ 0.9690
XTB_TRADE_COMMENT_RE = re.compile(
    r"^(OPEN|CLOSE)\s+BUY\s+([\d.]+)(?:/[\d.]+)?\s+@\s+([\d.]+)",
    re.IGNORECASE,
)

MIN_POSITION_QTY = 1e-6


def map_ticker_to_yahoo(ticker: str) -> str:
    """
    Konwertuje symbol z XTB na format rozpoznawany przez Yahoo Finance.

    - Akcje USA z XTB (np. AKBA.US) → AKBA
    - ETF/akcje europejskie (np. VWCE.DE) → bez zmian
    - Sam symbol bez sufiksu → TICKER_MAP
    """
    normalized = str(ticker).strip().upper()
    if not normalized:
        raise ValueError("Pusty symbol instrumentu.")

    # XTB: akcje z USA mają sufiks .US; Yahoo używa samego symbolu
    if normalized.endswith(".US"):
        return normalized[:-3]

    if "." in normalized:
        return normalized

    return TICKER_MAP.get(normalized, normalized)


def _is_xtb_native_excel(sheet_names: list[str]) -> bool:
    """Sprawdza, czy plik Excel pochodzi z platformy XTB."""
    return XTB_CASH_OPERATIONS_SHEET in sheet_names


def _parse_trade_comment(comment: str) -> tuple[str, float, float] | None:
    """
    Wyciąga z komentarza XTB stronę transakcji, ilość i cenę.

    Zwraca (OPEN|CLOSE, ilość, cena) lub None, gdy komentarz nie dotyczy handlu.
    """
    if not isinstance(comment, str):
        return None
    match = XTB_TRADE_COMMENT_RE.match(comment.strip())
    if not match:
        return None
    side = match.group(1).upper()
    quantity = float(match.group(2))
    price = float(match.group(3))
    return side, quantity, price


def _aggregate_open_positions_from_cash_ops(df: pd.DataFrame) -> pd.DataFrame:
    """
    Buduje otwarte pozycje na podstawie operacji Stock purchase / Stock sell.

    Średnia cena zakupu liczona jest metodą średniej ważonej; sprzedaż
    pomniejsza pozycję proporcjonalnie do dotychczasowego kosztu.
    """
    required_cols = {"Type", "Ticker", "Comment", "Time"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Arkusz Cash Operations – brak kolumn: {', '.join(sorted(missing))}")

    trades = df[df["Type"].isin(XTB_TRADE_TYPES)].copy()
    trades = trades.dropna(subset=["Ticker"])
    trades["Time"] = pd.to_datetime(trades["Time"], errors="coerce")
    trades = trades.sort_values("Time")

    # ticker -> {qty, cost}
    positions: dict[str, dict[str, float]] = {}

    for _, row in trades.iterrows():
        parsed = _parse_trade_comment(row["Comment"])
        if parsed is None:
            continue

        side, quantity, price = parsed
        ticker = str(row["Ticker"]).strip().upper()
        if not ticker or ticker == "NAN":
            continue

        if ticker not in positions:
            positions[ticker] = {"qty": 0.0, "cost": 0.0}
        pos = positions[ticker]

        if side == "OPEN":
            pos["cost"] += quantity * price
            pos["qty"] += quantity
        else:
            if pos["qty"] <= MIN_POSITION_QTY:
                continue
            avg_price = pos["cost"] / pos["qty"]
            close_qty = min(quantity, pos["qty"])
            pos["cost"] -= close_qty * avg_price
            pos["qty"] -= close_qty

    rows: list[dict[str, float | str]] = []
    for ticker, pos in sorted(positions.items()):
        if pos["qty"] > MIN_POSITION_QTY:
            rows.append(
                {
                    "ticker": ticker,
                    "ilosc": pos["qty"],
                    "srednia_cena": pos["cost"] / pos["qty"],
                }
            )

    if not rows:
        raise ValueError(
            "Nie znaleziono otwartych pozycji w arkuszu Cash Operations. "
            "Upewnij się, że eksport obejmuje okres z aktywnymi zakupami."
        )

    return pd.DataFrame(rows)


def _read_xtb_cash_operations(source: Union[str, BinaryIO, io.BytesIO]) -> pd.DataFrame:
    """Wczytuje arkusz Cash Operations z natywnego eksportu XTB."""
    return pd.read_excel(
        source,
        sheet_name=XTB_CASH_OPERATIONS_SHEET,
        header=XTB_CASH_HEADER_ROW,
    )


def _normalize_simple_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Dopasowuje nazwy kolumn uproszczonego pliku do standardowych pól portfela."""
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


def _finalize_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje mapowanie Yahoo i waliduje wartości liczbowe."""
    result = df.copy()
    result["ticker_xtb"] = result["ticker"].astype(str).str.strip().str.upper()
    result["ticker_yahoo"] = result["ticker_xtb"].apply(map_ticker_to_yahoo)
    result["ilosc"] = pd.to_numeric(result["ilosc"], errors="coerce")
    result["srednia_cena"] = pd.to_numeric(result["srednia_cena"], errors="coerce")

    if result[["ilosc", "srednia_cena"]].isna().any().any():
        raise ValueError("Kolumny ilość i średnia cena muszą zawierać wartości liczbowe.")

    if (result["ilosc"] <= 0).any():
        raise ValueError("Ilość każdej pozycji musi być większa od zera.")

    return result[["ticker_xtb", "ticker_yahoo", "ilosc", "srednia_cena"]].reset_index(drop=True)


def parse_xtb_report(
    file_source: Union[str, BinaryIO, io.BytesIO],
    filename: str,
) -> pd.DataFrame:
    """
    Parsuje raport XTB i zwraca ustandaryzowany DataFrame portfela.

    Automatycznie wykrywa:
    - natywny Excel XTB (arkusz „Cash Operations”),
    - uproszczony CSV/Excel z kolumnami Ticker, Ilość, Średnia cena zakupu.

    Kolumny wyjściowe:
        - ticker_xtb, ticker_yahoo, ilosc, srednia_cena
    """
    name = filename.lower()

    if name.endswith((".xlsx", ".xls")):
        excel = pd.ExcelFile(file_source)
        if _is_xtb_native_excel(excel.sheet_names):
            cash_ops = _read_xtb_cash_operations(file_source)
            portfolio = _aggregate_open_positions_from_cash_ops(cash_ops)
            return _finalize_portfolio(portfolio)

        raw_df = pd.read_excel(file_source)
        return _finalize_portfolio(_normalize_simple_columns(raw_df))

    if name.endswith(".csv"):
        raw_df = pd.read_csv(file_source)
        return _finalize_portfolio(_normalize_simple_columns(raw_df))

    raise ValueError("Obsługiwane formaty: .csv, .xlsx, .xls")
