"""
Uproszczony eksport pomocniczy pod PIT-38 (edukacyjny, nie e-Deklaracje).

Arkusze: Podsumowanie, Zyski_straty, Dywidendy, WHT, Straty_przeniesione.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font

from core.belka_tax import BelkaYearSummary, compute_belka_year
from core.excel_export import (
    _autosize_columns,
    _write_dataframe,
    _write_key_values,
    _write_section_title,
)
from core.importer import XTBReport
from core.tax_harvest import BELKA_RATE
from core.tax_loss_carry import load_carry_entries


class Pit38ExportError(RuntimeError):
    """Błąd generowania arkusza PIT-38."""


def default_pit38_filename(tax_year: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"pit38_helper_{tax_year}_{stamp}.xlsx"


def generate_pit38_excel_bytes(
    report: XTBReport,
    tax_year: int,
    *,
    summary: BelkaYearSummary | None = None,
) -> bytes:
    """Generuje .xlsx z danymi pomocniczymi do PIT-38 dla wskazanego roku."""
    year = int(tax_year)
    belka = summary or compute_belka_year(
        report.closed_positions,
        report.cash_operations,
        year,
        report.account_currency or "PLN",
    )

    wb = Workbook()

    # --- Podsumowanie ---
    ws = wb.active
    ws.title = "Podsumowanie"
    ws.cell(row=1, column=1, value=f"PIT-38 helper — rok {year}").font = Font(bold=True, size=14)
    row = 3
    row = _write_key_values(
        ws,
        row,
        [
            ("Plik źródłowy", report.filename),
            ("Wygenerowano (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Waluta (po NBP)", belka.currency),
            ("Metoda FX", belka.fx_method),
            ("Stawka Belki", f"{BELKA_RATE:.0%}"),
            (
                "Uwaga",
                "Szacunek edukacyjny — nie zastępuje PIT-38 / doradcy podatkowego.",
            ),
        ],
    )
    row = _write_section_title(ws, row, "Zyski i straty kapitałowe (sugerowane C)")
    row = _write_key_values(
        ws,
        row,
        [
            ("Zrealizowane zyski", round(belka.capital_gains, 2)),
            ("Zrealizowane straty", round(belka.capital_losses, 2)),
            ("Wynik netto", round(belka.capital_net, 2)),
            ("Straty z lat ubiegłych (zastosowane)", round(belka.carry_applied, 2)),
            ("Podstawa po przeniesieniu", round(belka.capital_base, 2)),
            ("Podatek od zysków kapitałowych", round(belka.capital_tax, 2)),
        ],
    )
    row = _write_section_title(ws, row, "Dywidendy / WHT (sugerowane G)")
    row = _write_key_values(
        ws,
        row,
        [
            ("Dywidendy brutto", round(belka.dividends_gross, 2)),
            ("Podatek PL 19% od dywidend", round(belka.dividend_tax_gross, 2)),
            ("WHT zapłacony za granicą", round(belka.withholding_tax, 2)),
            ("Kredyt WHT (max = podatek PL)", round(belka.dividend_tax_credit, 2)),
            ("Dopłata Belki od dywidend", round(belka.dividend_tax_after_wht, 2)),
            ("Łączny szacunek Belki", round(belka.total_tax, 2)),
        ],
    )
    _autosize_columns(ws)

    # --- Zyski_straty ---
    ws_c = wb.create_sheet("Zyski_straty")
    ws_c.cell(row=1, column=1, value="Zamknięte pozycje (PnL w PLN)").font = Font(bold=True, size=12)
    detail = belka.closed_detail
    if detail is not None and not detail.empty:
        cols = [
            c
            for c in (
                "ticker_xtb",
                "close_dt",
                "pnl",
                "pnl_ccy",
                "pnl_pln",
                "commission",
                "quantity",
            )
            if c in detail.columns
        ]
        show = detail[cols].rename(
            columns={
                "ticker_xtb": "Ticker",
                "close_dt": "Data zamknięcia",
                "pnl": "PnL (konto)",
                "pnl_ccy": "Waluta konta",
                "pnl_pln": "PnL PLN (NBP)",
                "commission": "Prowizja",
                "quantity": "Ilość",
            }
        )
        _write_dataframe(ws_c, show, 3)
    else:
        ws_c.cell(row=3, column=1, value="Brak zamkniętych pozycji w tym roku")
    _autosize_columns(ws_c)

    # --- Dywidendy ---
    ws_d = wb.create_sheet("Dywidendy")
    div = belka.dividends_detail
    if div is not None and not div.empty:
        cols = [c for c in ("date", "ticker_xtb", "amount", "currency", "amount_pln", "comment") if c in div.columns]
        show = div[cols].rename(
            columns={
                "date": "Data",
                "ticker_xtb": "Ticker",
                "amount": "Kwota",
                "currency": "Waluta",
                "amount_pln": "PLN (NBP)",
                "comment": "Komentarz",
            }
        )
        _write_dataframe(ws_d, show, 1, table_title="Dywidendy")
    else:
        ws_d.cell(row=1, column=1, value="Brak dywidend w tym roku")
    _autosize_columns(ws_d)

    # --- WHT ---
    ws_w = wb.create_sheet("WHT")
    wht = belka.wht_detail
    if wht is not None and not wht.empty:
        cols = [c for c in ("date", "ticker_xtb", "amount", "currency", "amount_pln", "type", "comment") if c in wht.columns]
        show = wht[cols].rename(
            columns={
                "date": "Data",
                "ticker_xtb": "Ticker",
                "amount": "Kwota (raw)",
                "currency": "Waluta",
                "amount_pln": "|WHT| PLN",
                "type": "Typ",
                "comment": "Komentarz",
            }
        )
        _write_dataframe(ws_w, show, 1, table_title="Podatek u źródła")
    else:
        ws_w.cell(row=1, column=1, value="Brak pozycji WHT w Cash Operations dla tego roku")
    _autosize_columns(ws_w)

    # --- Straty przeniesione ---
    ws_l = wb.create_sheet("Straty_przeniesione")
    entries = load_carry_entries()
    if entries:
        rows = [
            {
                "Rok powstania": e.origin_year,
                "Strata oryginalna": round(e.original_loss, 2),
                "Wykorzystano łącznie": round(e.used_so_far, 2),
                "Pozostało": round(e.remaining, 2),
                "Notatka": e.note,
            }
            for e in entries
        ]
        _write_dataframe(ws_l, pd.DataFrame(rows), 1, table_title="Ledżer strat (lokalny)")
        if belka.carry and belka.carry.details:
            _write_dataframe(
                ws_l,
                pd.DataFrame(belka.carry.details),
                3 + len(rows) + 2,
                table_title=f"Zastosowane w {year}",
            )
    else:
        ws_l.cell(row=1, column=1, value="Brak zapisanych strat z lat ubiegłych")
    _autosize_columns(ws_l)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
