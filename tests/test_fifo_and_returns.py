"""FIFO round-trips oraz XIRR / TWR (bez sieci)."""

from __future__ import annotations

import pandas as pd

from core.returns import compute_xirr
from core.trade_analytics import build_round_trips_from_trades


def test_fifo_round_trips_basic():
    trades = pd.DataFrame(
        [
            {
                "ticker_xtb": "AAA.US",
                "ticker_yahoo": "AAA",
                "side": "OPEN",
                "quantity": 10.0,
                "price": 100.0,
                "trade_time": pd.Timestamp("2024-01-01"),
            },
            {
                "ticker_xtb": "AAA.US",
                "ticker_yahoo": "AAA",
                "side": "OPEN",
                "quantity": 5.0,
                "price": 120.0,
                "trade_time": pd.Timestamp("2024-02-01"),
            },
            {
                "ticker_xtb": "AAA.US",
                "ticker_yahoo": "AAA",
                "side": "CLOSE",
                "quantity": 12.0,
                "price": 130.0,
                "trade_time": pd.Timestamp("2024-03-01"),
            },
        ]
    )
    trips = build_round_trips_from_trades(trades)
    assert len(trips) == 2
    # First lot: 10 @ 100 → 130 = +300
    assert abs(float(trips.iloc[0]["realized_pnl"]) - 300.0) < 1e-9
    assert float(trips.iloc[0]["quantity"]) == 10.0
    # Second lot: 2 @ 120 → 130 = +20
    assert abs(float(trips.iloc[1]["realized_pnl"]) - 20.0) < 1e-9
    assert float(trips.iloc[1]["quantity"]) == 2.0
    assert abs(float(trips["realized_pnl"].sum()) - 320.0) < 1e-9


def test_xirr_known_flows():
    # Wpłata 1000, po dokładnie 365 dniach wypłata 1100 → ~10%
    # (unika roku przestępnego — XIRR liczy dni / 365)
    flows = [
        (pd.Timestamp("2021-01-01"), -1000.0),
        (pd.Timestamp("2022-01-01"), 1100.0),
    ]
    rate = compute_xirr(flows)
    assert rate is not None
    assert abs(rate - 0.10) < 1e-4


def test_xirr_rejects_same_sign():
    flows = [
        (pd.Timestamp("2020-01-01"), -100.0),
        (pd.Timestamp("2021-01-01"), -50.0),
    ]
    assert compute_xirr(flows) is None
