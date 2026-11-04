"""Mapowanie tickerów XTB → Yahoo + nadpisania użytkownika."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core import importer_maps as maps


def test_suffix_rules():
    assert maps.map_ticker_to_yahoo("AAPL.US") == "AAPL"
    assert maps.map_ticker_to_yahoo("XTB.PL") == "XTB.WA"
    assert maps.map_ticker_to_yahoo("JD.UK") == "JD.L"


def test_builtin_map():
    assert maps.map_ticker_to_yahoo("VWCE") == "VWCE.DE"
    assert maps.map_ticker_to_yahoo("PKN") == "PKN.WA"


def test_multi_account_suffix_stripped(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OVERRIDES_PATH", tmp_path / "ticker_overrides.json")
    assert maps.map_ticker_to_yahoo("VWCE [EUR]") == "VWCE.DE"


def test_override_priority(tmp_path, monkeypatch):
    path = tmp_path / "ticker_overrides.json"
    monkeypatch.setattr(maps, "OVERRIDES_PATH", path)
    maps.set_ticker_override("VWCE", "VWCE.L")
    assert maps.map_ticker_to_yahoo("VWCE") == "VWCE.L"
    maps.delete_ticker_override("VWCE")
    assert maps.map_ticker_to_yahoo("VWCE") == "VWCE.DE"
    assert path.exists()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert "VWCE" not in data


def test_positions_missing_prices():
    df = pd.DataFrame(
        {
            "ticker_xtb": ["A", "B"],
            "ticker_yahoo": ["A", "B.DE"],
            "market_price": [10.0, float("nan")],
        }
    )
    missing = maps.positions_missing_prices(df)
    assert len(missing) == 1
    assert missing[0]["ticker_xtb"] == "B"
