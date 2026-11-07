"""Fee drag, rebalance per ticker, prefs backup, IKE log, alerts CSV."""

from __future__ import annotations

import pandas as pd

from core.alerts import build_triggered_alerts_export, triggered_alerts_to_csv
from core.fee_drag import compute_fee_drag
from core.ike_ikze_log import add_contribution, delete_contribution, year_status
from core.prefs_backup import BACKUP_FILENAMES, export_prefs_zip, import_prefs_zip
from core.rebalance import compute_rebalance, suggest_ticker_orders


def test_fee_drag_basic():
    closed = pd.DataFrame(
        {
            "ticker_xtb": ["A", "B"],
            "close_time": [pd.Timestamp("2024-03-01"), pd.Timestamp("2024-06-01")],
            "pnl": [1000.0, -200.0],
            "commission": [-5.0, -3.0],
        }
    )
    summary = compute_fee_drag(closed, tax_year=2024)
    assert summary.has_data
    assert summary.commission_total == 8.0
    assert summary.gross_pnl == 800.0
    assert summary.net_pnl == 792.0
    assert summary.fee_drag_pct is not None
    assert abs(summary.fee_drag_pct - 1.0) < 1e-9


def test_suggest_ticker_orders():
    enriched = pd.DataFrame(
        {
            "ticker_xtb": ["AAA", "BBB", "CCC"],
            "ticker_yahoo": ["AAA", "BBB", "CCC"],
            "sector": ["Tech", "Tech", "Health"],
            "market_value": [60.0, 40.0, 100.0],
            "weight_pct": [30.0, 20.0, 50.0],
        }
    )
    breakdown = pd.DataFrame(
        {
            "sector": ["Tech", "Health"],
            "market_value": [100.0, 100.0],
            "weight_pct": [50.0, 50.0],
        }
    )
    rb = compute_rebalance(
        breakdown,
        {"Tech": 60.0, "Health": 40.0},
        "sector",
        new_cash=0.0,
    )
    orders = suggest_ticker_orders(enriched, rb, "sector", min_order=0.0)
    assert not orders.empty
    tech = orders[orders["basket"] == "Tech"]
    assert abs(float(tech["suggested_value"].sum()) - float(
        rb.loc[rb["sector"] == "Tech", "delta_value"].iloc[0]
    )) < 1e-6


def test_prefs_backup_roundtrip(tmp_path, monkeypatch):
    import core.prefs_backup as pb

    monkeypatch.setattr(pb, "PROJECT_ROOT", tmp_path)
    sample = tmp_path / "watchlist.json"
    sample.write_text('{"items":[]}\n', encoding="utf-8")
    data = export_prefs_zip()
    sample.unlink()
    restored = import_prefs_zip(data)
    assert "watchlist.json" in restored
    assert (tmp_path / "watchlist.json").exists()
    assert "watchlist.json" in BACKUP_FILENAMES


def test_ike_log_year_status(tmp_path, monkeypatch):
    import core.ike_ikze_log as log

    monkeypatch.setattr(log, "LOG_PATH", tmp_path / "ike_ikze_contributions.json")
    add_contribution("IKE", 1000, "2025-01-10")
    add_contribution("IKZE", 500, "2025-02-01")
    add_contribution("IKE", 200, "2024-12-01")
    status = year_status(2025, ike_limit=26_019, ikze_limit=10_407)
    assert status.ike_contributed == 1000.0
    assert status.ikze_contributed == 500.0
    assert status.ike_remaining == 26_019 - 1000
    entries = log.load_contributions()
    delete_contribution(entries[0].entry_id)


def test_alerts_csv_export():
    roi = pd.DataFrame(
        [
            {
                "ticker_xtb": "AAA",
                "ticker_yahoo": "AAA",
                "alert_type": "Zysk",
                "roi_pct": 12.5,
                "is_new": True,
                "market_price": 10.0,
            }
        ]
    )
    price = pd.DataFrame(
        [
            {
                "ticker_xtb": "BBB",
                "kierunek": "↑ Powyżej",
                "cel": 100.0,
                "aktualna": 105.0,
                "wyzwolony": True,
                "notatka": "x",
            }
        ]
    )
    export = build_triggered_alerts_export(roi, price, mode="roi", threshold_pct=10)
    assert len(export) == 2
    csv = triggered_alerts_to_csv(export)
    assert csv.startswith("\ufeff")
    assert "AAA" in csv and "BBB" in csv
