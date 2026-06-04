"""
Łączenie wielu raportów XTB (np. konto PLN + EUR) w jeden widok majątku.
"""

from __future__ import annotations

import pandas as pd

from core.importer import XTBReport

MULTI_ACCOUNT_CURRENCY = "MULTI"


def account_label_for_report(report: XTBReport) -> str:
    """Etykieta konta do UI (waluta lub numer konta)."""
    if report.account_number:
        return f"{report.account_currency} ({report.account_number})"
    return report.account_currency


def _short_label(report: XTBReport, index: int) -> str:
    """Krótka etykieta (PLN / EUR) — z waluty konta."""
    return report.account_currency.upper()


def _disambiguate_ticker_xtb(ticker_xtb: str, label: str) -> str:
    suffix = f" [{label}]"
    if ticker_xtb.endswith(suffix):
        return ticker_xtb
    return f"{ticker_xtb}{suffix}"


def _tag_open_positions(df: pd.DataFrame, report: XTBReport, label: str) -> pd.DataFrame:
    out = df.copy()
    out["account_label"] = label
    out["account_currency"] = report.account_currency
    if report.account_number:
        out["account_number"] = report.account_number
    out["ticker_xtb"] = out["ticker_xtb"].map(lambda t: _disambiguate_ticker_xtb(str(t), label))
    return out


def _tag_closed_positions(df: pd.DataFrame | None, label: str) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    out = df.copy()
    out["account_label"] = label
    if "ticker_xtb" in out.columns:
        out["ticker_xtb"] = out["ticker_xtb"].map(lambda t: _disambiguate_ticker_xtb(str(t), label))
    return out


def _tag_cash_operations(df: pd.DataFrame | None, label: str) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    out = df.copy()
    out["account_label"] = label
    return out


def merge_timelines(timelines: list[pd.DataFrame]) -> pd.DataFrame:
    """Sumuje wartość i koszt z timeline poszczególnych kont (wspólna oś dat)."""
    valid = [tl for tl in timelines if tl is not None and not tl.empty]
    if not valid:
        return pd.DataFrame()
    if len(valid) == 1:
        return valid[0].copy()

    merged: pd.DataFrame | None = None
    for tl in valid:
        part = tl.copy()
        if "date" not in part.columns:
            continue
        part["date"] = pd.to_datetime(part["date"]).dt.normalize()
        part = part.set_index("date")
        for col in ("market_value", "cost_basis", "unrealized_pnl"):
            if col not in part.columns:
                part[col] = 0.0
        agg = part[["market_value", "cost_basis"]].copy()
        if "unrealized_pnl" in part.columns:
            agg["unrealized_pnl"] = part["unrealized_pnl"]
        else:
            agg["unrealized_pnl"] = agg["market_value"] - agg["cost_basis"]

        if merged is None:
            merged = agg
        else:
            merged = merged.add(agg, fill_value=0.0)

    if merged is None or merged.empty:
        return pd.DataFrame()

    out = merged.reset_index()
    out["unrealized_pnl"] = out["market_value"] - out["cost_basis"]
    if "position_count" not in out.columns:
        out["position_count"] = pd.NA
    return out.sort_values("date").reset_index(drop=True)


def merge_reports(reports: list[XTBReport]) -> XTBReport:
    """
    Scala listę raportów XTB w jeden (wspólny portfel + historia).

    Wymaga co najmniej 2 raportów.
    """
    if len(reports) < 2:
        raise ValueError("merge_reports wymaga co najmniej dwóch raportów.")

    labels: list[str] = []
    seen_short: dict[str, int] = {}
    open_parts: list[pd.DataFrame] = []
    closed_parts: list[pd.DataFrame] = []
    cash_parts: list[pd.DataFrame] = []
    filenames: dict[str, str] = {}

    for idx, report in enumerate(reports):
        short = _short_label(report, idx)
        if short in seen_short:
            seen_short[short] += 1
            short = f"{short}-{seen_short[short]}"
        else:
            seen_short[short] = 1
        labels.append(short)
        filenames[short] = report.filename

        open_parts.append(_tag_open_positions(report.open_positions, report, short))
        closed_parts.append(_tag_closed_positions(report.closed_positions, short))
        cash_parts.append(_tag_cash_operations(report.cash_operations, short))

    open_merged = pd.concat(open_parts, ignore_index=True)
    open_merged.attrs["account_currency"] = MULTI_ACCOUNT_CURRENCY
    open_merged.attrs["account_labels"] = tuple(labels)

    closed_merged: pd.DataFrame | None = None
    closed_valid = [c for c in closed_parts if c is not None and not c.empty]
    if closed_valid:
        closed_merged = pd.concat(closed_valid, ignore_index=True)

    cash_merged: pd.DataFrame | None = None
    cash_valid = [c for c in cash_parts if c is not None and not c.empty]
    if cash_valid:
        cash_merged = pd.concat(cash_valid, ignore_index=True)

    filename = " + ".join(f"{lbl}: {fn}" for lbl, fn in filenames.items())
    numbers = [r.account_number for r in reports if r.account_number]
    account_number = ", ".join(numbers) if numbers else None

    return XTBReport(
        open_positions=open_merged,
        closed_positions=closed_merged,
        cash_operations=cash_merged,
        account_currency=MULTI_ACCOUNT_CURRENCY,
        account_number=account_number,
        filename=filename,
        account_labels=tuple(labels),
        source_filenames=filenames,
        is_merged=True,
    )
