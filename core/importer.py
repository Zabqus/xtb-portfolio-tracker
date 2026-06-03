"""
Import XTB reports (Cash Operations, Closed Positions) and simplified CSV/Excel.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import BinaryIO, Union

import pandas as pd

from core.currencies import currency_from_ticker, detect_account_currency, read_account_number
from core.importer_maps import map_ticker_to_yahoo
from core.transactions import parse_cash_operations_trades

XTB_CASH_OPERATIONS_SHEET = "Cash Operations"
XTB_CLOSED_POSITIONS_SHEET = "Closed Positions"
XTB_HEADER_ROW = 4

XTB_TRADE_TYPES = ("Stock purchase", "Stock sell")

MIN_POSITION_QTY = 1e-6

COLUMN_ALIASES: dict[str, list[str]] = {
    "ticker": ["ticker", "symbol", "instrument", "akcja", "papier"],
    "quantity": ["ilosc", "ilość", "quantity", "qty", "szt", "sztuki", "volume"],
    "avg_price": [
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

REQUIRED_SIMPLE_COLUMNS = ("ticker", "quantity", "avg_price")


@dataclass
class XTBReport:
    """Parsed XTB export."""

    open_positions: pd.DataFrame
    closed_positions: pd.DataFrame | None
    cash_operations: pd.DataFrame | None
    account_currency: str
    account_number: str | None
    filename: str


def _is_xtb_native_excel(sheet_names: list[str]) -> bool:
    return XTB_CASH_OPERATIONS_SHEET in sheet_names


def _aggregate_open_positions_from_cash_ops(df: pd.DataFrame) -> pd.DataFrame:
    """Buduje otwarte pozycje z operacji Stock purchase / Stock sell."""
    trades = parse_cash_operations_trades(df)
    if trades.empty:
        raise ValueError(
            "No open positions found in Cash Operations. "
            "Ensure the export covers a period with active purchases."
        )

    positions: dict[str, dict[str, float]] = {}

    for _, row in trades.iterrows():
        ticker = row["ticker_xtb"]
        quantity = float(row["quantity"])
        price = float(row["price"])
        side = row["side"]

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
                    "quantity": pos["qty"],
                    "avg_price": pos["cost"] / pos["qty"],
                }
            )

    if not rows:
        raise ValueError(
            "No open positions found in Cash Operations. "
            "Ensure the export covers a period with active purchases."
        )

    return pd.DataFrame(rows)


def _parse_closed_positions_sheet(source: Union[str, BinaryIO, io.BytesIO]) -> pd.DataFrame | None:
    """Parsuje arkusz Closed Positions z natywnego eksportu XTB."""
    try:
        raw = pd.read_excel(
            source,
            sheet_name=XTB_CLOSED_POSITIONS_SHEET,
            header=XTB_HEADER_ROW,
        )
    except ValueError:
        return None

    if "Ticker" not in raw.columns:
        return None

    df = raw.copy()
    df = df[df["Ticker"].notna()]
    df = df[~df["Instrument"].astype(str).str.contains("Profit", case=False, na=False)]

    if df.empty:
        return None

    df["ticker_xtb"] = df["Ticker"].astype(str).str.strip().str.upper()
    df["ticker_yahoo"] = df["ticker_xtb"].apply(map_ticker_to_yahoo)
    df["currency"] = df["ticker_xtb"].apply(currency_from_ticker)

    numeric_map = {
        "Volume": "quantity",
        "Open Price": "open_price",
        "Close Price": "close_price",
        "Profit/Loss": "pnl",
        "Gross Profit": "gross_pnl",
        "Purchase Value": "purchase_value",
        "Sale Value": "sale_value",
        "Commission": "commission",
    }
    for src, dst in numeric_map.items():
        if src in df.columns:
            df[dst] = pd.to_numeric(df[src], errors="coerce")

    if "Open Time (UTC)" in df.columns:
        df["open_time"] = pd.to_datetime(df["Open Time (UTC)"], errors="coerce")
    if "Close Time (UTC)" in df.columns:
        df["close_time"] = pd.to_datetime(df["Close Time (UTC)"], errors="coerce")

    rename_static = {
        "Instrument": "instrument",
        "Category": "category",
        "Type": "position_type",
        "Product": "product",
        "Position ID": "position_id",
    }
    df = df.rename(columns={k: v for k, v in rename_static.items() if k in df.columns})

    output_cols = [
        "ticker_xtb",
        "ticker_yahoo",
        "currency",
        "instrument",
        "category",
        "position_type",
        "quantity",
        "open_price",
        "close_price",
        "open_time",
        "close_time",
        "pnl",
        "gross_pnl",
        "purchase_value",
        "sale_value",
        "commission",
        "product",
        "position_id",
    ]
    existing = [c for c in output_cols if c in df.columns]
    return df[existing].reset_index(drop=True)


def _read_cash_operations(source: Union[str, BinaryIO, io.BytesIO]) -> pd.DataFrame:
    return pd.read_excel(
        source,
        sheet_name=XTB_CASH_OPERATIONS_SHEET,
        header=XTB_HEADER_ROW,
    )


def _read_metadata(source: Union[str, BinaryIO, io.BytesIO]) -> pd.DataFrame:
    return pd.read_excel(
        source,
        sheet_name=XTB_CASH_OPERATIONS_SHEET,
        header=None,
        nrows=5,
    )


def _normalize_simple_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    lower_cols = {str(col).strip().lower(): col for col in df.columns}

    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                rename_map[lower_cols[alias]] = target
                break

    missing = [c for c in REQUIRED_SIMPLE_COLUMNS if c not in rename_map.values()]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}. "
            "Expected: Ticker, Quantity, Average purchase price."
        )

    return df.rename(columns=rename_map)[list(REQUIRED_SIMPLE_COLUMNS)]


def _finalize_open_positions(
    df: pd.DataFrame,
    account_currency: str = "EUR",
    account_number: str | None = None,
) -> pd.DataFrame:
    result = df.copy()
    result["ticker_xtb"] = result["ticker"].astype(str).str.strip().str.upper()
    result["ticker_yahoo"] = result["ticker_xtb"].apply(map_ticker_to_yahoo)
    result["currency"] = result["ticker_xtb"].apply(currency_from_ticker)
    result["quantity"] = pd.to_numeric(result["quantity"], errors="coerce")
    result["avg_price"] = pd.to_numeric(result["avg_price"], errors="coerce")

    if result[["quantity", "avg_price"]].isna().any().any():
        raise ValueError("Quantity and avg_price must be numeric.")

    if (result["quantity"] <= 0).any():
        raise ValueError("Each position quantity must be greater than zero.")

    result = result[
        ["ticker_xtb", "ticker_yahoo", "currency", "quantity", "avg_price"]
    ].reset_index(drop=True)
    result.attrs["account_currency"] = account_currency
    if account_number:
        result.attrs["account_number"] = account_number
    return result


def parse_xtb_report(
    file_source: Union[str, BinaryIO, io.BytesIO],
    filename: str,
) -> XTBReport:
    """
    Parsuje raport XTB (natywny Excel lub uproszczony CSV/Excel).

    Zwraca otwarte pozycje, zamknięte pozycje (jeśli arkusz istnieje) i metadane konta.
    """
    name = filename.lower()
    closed_positions: pd.DataFrame | None = None
    account_currency = "PLN"
    account_number: str | None = None

    if name.endswith((".xlsx", ".xls")):
        excel = pd.ExcelFile(file_source)
        if _is_xtb_native_excel(excel.sheet_names):
            meta = _read_metadata(file_source)
            cash_ops = _read_cash_operations(file_source)
            open_raw = _aggregate_open_positions_from_cash_ops(cash_ops)
            tickers = open_raw["ticker"].astype(str).tolist()
            account_number = read_account_number(meta)
            account_currency = detect_account_currency(cash_ops, meta, tickers)
            open_positions = _finalize_open_positions(
                open_raw,
                account_currency=account_currency,
                account_number=account_number,
            )

            if XTB_CLOSED_POSITIONS_SHEET in excel.sheet_names:
                if hasattr(file_source, "seek"):
                    file_source.seek(0)
                closed_positions = _parse_closed_positions_sheet(file_source)

            return XTBReport(
                open_positions=open_positions,
                closed_positions=closed_positions,
                cash_operations=cash_ops,
                account_currency=account_currency,
                account_number=account_number,
                filename=filename,
            )

        raw_df = pd.read_excel(file_source)
        open_positions = _finalize_open_positions(
            _normalize_simple_columns(raw_df),
            account_currency="PLN",
        )
        return XTBReport(
            open_positions=open_positions,
            closed_positions=None,
            cash_operations=None,
            account_currency="PLN",
            account_number=None,
            filename=filename,
        )

    if name.endswith(".csv"):
        raw_df = pd.read_csv(file_source)
        open_positions = _finalize_open_positions(
            _normalize_simple_columns(raw_df),
            account_currency="PLN",
        )
        return XTBReport(
            open_positions=open_positions,
            closed_positions=None,
            cash_operations=None,
            account_currency="PLN",
            account_number=None,
            filename=filename,
        )

    raise ValueError("Supported formats: .csv, .xlsx, .xls")
