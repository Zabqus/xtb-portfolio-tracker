"""
Miesięczny raport PDF portfela: podsumowanie, wykresy Plotly (PNG / kaleido), tabela pozycji.
"""

from __future__ import annotations

import re
import tempfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from fpdf.fonts import FontFace

from core.allocation import REGION_ORDER, aggregate_breakdown, enrich_portfolio_allocation
from core.analyzer import portfolio_summary
from core.importer import XTBReport
from ui.allocation_charts import REGION_COLORS, build_breakdown_pie
from ui.charts import build_allocation_pie, build_pnl_bar_chart

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"
DEJAVU_TTF = FONTS_DIR / "DejaVuSans.ttf"
FONT_FAMILY = "PortfolioUnicode"

_FONT_CANDIDATES: tuple[Path, ...] = (
    DEJAVU_TTF,
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path(r"C:\Windows\Fonts\segoeui.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
)

CHART_WIDTH = 900
CHART_HEIGHT = 480


class PdfReportError(RuntimeError):
    """Błąd generowania raportu PDF."""


def _resolve_font_path() -> Path:
    """Czcionka TTF z polskimi znakami: assets/fonts, potem systemowa."""
    for path in _FONT_CANDIDATES:
        if path.is_file():
            return path
    raise PdfReportError(
        "Brak czcionki TTF do raportu PDF. Skopiuj DejaVuSans.ttf lub arial.ttf do "
        f"{FONTS_DIR} (np. z C:\\Windows\\Fonts\\arial.ttf)."
    )


def _ensure_unicode_font(pdf: FPDF) -> str:
    if FONT_FAMILY in pdf.fonts:
        return FONT_FAMILY
    font_path = _resolve_font_path()
    pdf.add_font(FONT_FAMILY, "", str(font_path))
    return FONT_FAMILY


def plotly_figure_to_png(fig: go.Figure, width: int = CHART_WIDTH, height: int = CHART_HEIGHT) -> bytes:
    """Eksportuje wykres Plotly do PNG (wymaga kaleido)."""
    try:
        return fig.to_image(
            format="png",
            engine="kaleido",
            width=width,
            height=height,
            scale=2,
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "kaleido" in msg or "orca" in msg or "image" in msg:
            raise PdfReportError(
                "Eksport wykresów wymaga pakietu kaleido: pip install kaleido"
            ) from exc
        raise PdfReportError(f"Nie udało się wyeksportować wykresu: {exc}") from exc


def _safe_chart_filename(title: str, index: int) -> str:
    safe = re.sub(r"[^\w\-]+", "_", title, flags=re.UNICODE).strip("_")
    return (safe[:36] or "chart") + f"_{index}"


def _write_png_to_temp(png_bytes: bytes, directory: Path, name: str) -> Path:
    path = directory / f"{name}.png"
    path.write_bytes(png_bytes)
    return path


def build_positions_table(analyzed: pd.DataFrame, currency: str) -> pd.DataFrame:
    """Tabela pozycji pod raport PDF (posortowana wg wartości)."""
    cols = [
        "ticker_xtb",
        "ticker_yahoo",
        "quantity",
        "avg_price",
        "market_price",
        "position_cost",
        "market_value",
        "pnl",
        "roi_pct",
    ]
    available = [c for c in cols if c in analyzed.columns]
    table = analyzed[available].copy()
    table = table.sort_values("market_value", ascending=False, na_position="last")

    rename = {
        "ticker_xtb": "Ticker",
        "ticker_yahoo": "Yahoo",
        "quantity": "Ilość",
        "avg_price": "Śr. cena",
        "market_price": "Cena rynk.",
        "position_cost": f"Koszt ({currency})",
        "market_value": f"Wartość ({currency})",
        "pnl": f"PnL ({currency})",
        "roi_pct": "ROI %",
    }
    return table.rename(columns={k: v for k, v in rename.items() if k in table.columns})


def _format_num(value, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "-"
    return f"{float(value):,.{decimals}f}".replace(",", " ")


def _add_summary_section(
    pdf: FPDF,
    font: str,
    summary: dict,
    report: XTBReport,
    report_month: date,
) -> None:
    currency = str(summary["display_currency"])
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf.set_font(font, size=16)
    pdf.cell(0, 12, f"Raport miesieczny portfela XTB – {report_month.strftime('%Y-%m')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font, size=10)
    pdf.cell(0, 6, f"Plik źródłowy: {report.filename}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Wygenerowano: {generated}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font(font, size=12)
    pdf.cell(0, 8, "Podsumowanie", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font, size=11)

    rows = [
        ("Całkowita wartość", f"{_format_num(summary['total_value'])} {currency}"),
        ("Łączny koszt", f"{_format_num(summary['total_cost'])} {currency}"),
        ("Łączny zysk / strata", f"{_format_num(summary['total_pnl'])} {currency}"),
        ("ROI", f"{_format_num(summary['total_roi_pct'])} %"),
        ("Waluta konta", str(summary["account_currency"])),
        ("Liczba otwartych pozycji", str(len(report.open_positions))),
    ]
    if report.is_merged and report.account_labels:
        rows.append(("Konta", ", ".join(report.account_labels)))
    elif report.account_number:
        rows.append(("Numer konta", str(report.account_number)))

    for label, value in rows:
        pdf.cell(70, 7, label + ":", border=0)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)


def _add_chart_image(pdf: FPDF, image_path: Path, title: str, font: str) -> None:
    pdf.set_font(font, size=11)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.image(str(image_path), w=usable_w)
    pdf.ln(4)


def _add_positions_table(pdf: FPDF, table: pd.DataFrame, font: str) -> None:
    if table.empty:
        return

    pdf.add_page()
    pdf.set_font(font, size=12)
    pdf.cell(0, 10, "Otwarte pozycje", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(font, size=8)

    headings = list(table.columns)
    n_cols = len(headings)
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable_w / n_cols

    with pdf.table(
        width=usable_w,
        col_widths=(col_w,) * n_cols,
        line_height=6,
        headings_style=FontFace(emphasis="NONE"),
    ) as pdf_table:
        pdf_table.row(headings)
        for _, row in table.iterrows():
            cells = []
            for col in headings:
                val = row[col]
                if isinstance(val, float):
                    cells.append(_format_num(val, 2 if col != "ROI %" else 1))
                else:
                    cells.append(str(val) if pd.notna(val) else "-")
            pdf_table.row(cells)


def generate_monthly_pdf_bytes(
    report: XTBReport,
    analyzed: pd.DataFrame,
    summary: dict[str, float | str] | None = None,
    report_month: date | None = None,
    include_allocation_charts: bool = True,
) -> bytes:
    """
    Buduje miesięczny raport PDF i zwraca bajty do pobrania (Streamlit download_button).

    Wymaga: fpdf2, kaleido, przeanalizowany portfel (analyze_portfolio).
    """
    if analyzed is None or analyzed.empty:
        raise PdfReportError("Brak otwartych pozycji do raportu.")

    summary = summary or portfolio_summary(analyzed)
    report_month = report_month or date.today().replace(day=1)
    currency = str(summary["display_currency"])

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(12, 12, 12)
    font = _ensure_unicode_font(pdf)
    pdf.set_font(font, "", 11)
    pdf.add_page()

    figures: list[tuple[str, go.Figure]] = [
        ("Struktura portfela (udział wartości)", build_allocation_pie(analyzed, currency)),
        ("Zysk / strata na pozycjach", build_pnl_bar_chart(analyzed, currency)),
    ]

    if include_allocation_charts:
        try:
            enriched = enrich_portfolio_allocation(analyzed)
            if not enriched.empty:
                sector_df = aggregate_breakdown(enriched, "sector")
                region_df = aggregate_breakdown(enriched, "region", sort_order=REGION_ORDER)
                figures.append(
                    ("Alokacja sektorowa", build_breakdown_pie(sector_df, "sector", currency, "Sektory"))
                )
                figures.append(
                    (
                        "Alokacja geograficzna (USA / EU / PL)",
                        build_breakdown_pie(
                            region_df,
                            "region",
                            currency,
                            "Regiony",
                            color_map=REGION_COLORS,
                        ),
                    )
                )
        except (ValueError, KeyError, PdfReportError):
            pass

    positions = build_positions_table(analyzed, currency)

    with tempfile.TemporaryDirectory(prefix="xtb_pdf_") as tmp:
        tmp_path = Path(tmp)
        _add_summary_section(pdf, font, summary, report, report_month)

        for idx, (title, fig) in enumerate(figures):
            png = plotly_figure_to_png(fig)
            img_path = _write_png_to_temp(png, tmp_path, _safe_chart_filename(title, idx))
            if pdf.get_y() > 200:
                pdf.add_page()
            _add_chart_image(pdf, img_path, title, font)

        _add_positions_table(pdf, positions, font)

        out = BytesIO()
        pdf.output(out)
        return out.getvalue()


def default_report_filename(report_month: date | None = None) -> str:
    month = report_month or date.today().replace(day=1)
    return f"raport_portfela_{month.strftime('%Y-%m')}.pdf"
