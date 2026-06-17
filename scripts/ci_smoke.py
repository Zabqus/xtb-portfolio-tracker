"""
Szybki test importów uruchamiany w GitHub Actions (bez sieci / plików XTB).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Pozwala uruchamiać skrypt zarówno przez `python -m scripts.ci_smoke`,
# jak i bezpośrednio `python scripts/ci_smoke.py` (dodaje korzeń repo do ścieżki).
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    modules = [
        "core.importer",
        "core.analyzer",
        "core.currencies",
        "core.market_data",
        "core.history",
        "core.fundamentals",
        "core.analyst_consensus",
        "core.benchmark",
        "core.timing_score",
        "core.transactions",
        "core.timeline",
        "core.closed_analysis",
        "core.trade_analytics",
        "core.cost_basis",
        "core.technicals",
        "core.watchlist",
        "core.allocation",
        "core.pdf_report",
        "core.excel_export",
        "core.multi_account",
        "core.alerts",
        "core.session",
        "core.signals",
        "core.risk_metrics",
        "core.dividends",
        "ui.charts",
        "ui.formatters",
        "ui.tables",
        "ui.sidebar",
        "ui.position_charts",
        "ui.history_charts",
        "ui.analytics_charts",
        "ui.technical_charts",
        "ui.analyst_consensus",
        "ui.watchlist_charts",
        "ui.allocation_charts",
        "ui.risk_charts",
    ]

    for name in modules:
        __import__(name)

    print(f"OK: {len(modules)} modules imported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
