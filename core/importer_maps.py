"""XTB ticker → Yahoo Finance symbol mapping (+ lokalne nadpisania użytkownika)."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_PATH = PROJECT_ROOT / "ticker_overrides.json"

# Ręczne mapowania popularnych ETF-ów / spółek GPW (gdy brak sufiksu .PL/.US/.UK).
TICKER_MAP: dict[str, str] = {
    # Global / EU ETF
    "VWCE": "VWCE.DE",
    "VWCG": "VWCG.DE",
    "VWRL": "VWRL.L",
    "VWRP": "VWRP.L",
    "VUSA": "VUSA.L",
    "VUAG": "VUAG.L",
    "VUAA": "VUAA.L",
    "CSPX": "CSPX.L",
    "IWDA": "IWDA.AS",
    "SWDA": "SWDA.L",
    "EIMI": "EIMI.L",
    "IS3N": "IS3N.DE",
    "SXR8": "SXR8.DE",
    "SXRV": "SXRV.DE",
    "EUNK": "EUNK.DE",
    "XAIX": "XAIX.DE",
    "EXW1": "EXW1.DE",
    "EXXT": "EXXT.DE",
    "EQQQ": "EQQQ.L",
    "CNDX": "CNDX.L",
    "AGGH": "AGGH.L",
    "IEAG": "IEAG.L",
    "IGLN": "IGLN.L",
    "SGLN": "SGLN.L",
    "SPYL": "SPYL.DE",
    "IUSE": "IUSE.L",
    "QDVE": "QDVE.DE",
    "QDV5": "QDV5.DE",
    "LYMS": "LYMS.DE",
    "IMEU": "IMEU.L",
    "IUSQ": "IUSQ.DE",
    "VWRA": "VWRA.L",
    "SSAC": "SSAC.L",
    # GPW (gdy XTB podaje bez .PL)
    "PKN": "PKN.WA",
    "KGH": "KGH.WA",
    "CDR": "CDR.WA",
    "PEO": "PEO.WA",
    "ALE": "ALE.WA",
    "DNP": "DNP.WA",
    "PZU": "PZU.WA",
    "PKO": "PKO.WA",
    "MBK": "MBK.WA",
    "LPP": "LPP.WA",
    "JSW": "JSW.WA",
    "CCC": "CCC.WA",
    "OPL": "OPL.WA",
    "CPS": "CPS.WA",
    "KRU": "KRU.WA",
    "ALR": "ALR.WA",
    "SPL": "SPL.WA",
    "ING": "ING.WA",
    "SAN": "SAN.WA",
    "BNP": "BNP.WA",
    "11B": "11B.WA",
    "ABS": "ABS.WA",
    "XTB": "XTB.WA",
    "KRK": "KRK.WA",
    "ATT": "ATT.WA",
    "ACP": "ACP.WA",
    "KTY": "KTY.WA",
    "MRC": "MRC.WA",
    "ZAB": "ZAB.WA",
}


def load_ticker_overrides() -> dict[str, str]:
    if not OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        k = str(key).strip().upper()
        v = str(value).strip()
        if k and v:
            out[k] = v
    return out


def save_ticker_overrides(overrides: dict[str, str]) -> None:
    clean = {
        str(k).strip().upper(): str(v).strip()
        for k, v in overrides.items()
        if str(k).strip() and str(v).strip()
    }
    OVERRIDES_PATH.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def set_ticker_override(xtb_symbol: str, yahoo_symbol: str) -> dict[str, str]:
    overrides = load_ticker_overrides()
    overrides[str(xtb_symbol).strip().upper()] = str(yahoo_symbol).strip()
    save_ticker_overrides(overrides)
    return overrides


def delete_ticker_override(xtb_symbol: str) -> dict[str, str]:
    overrides = load_ticker_overrides()
    overrides.pop(str(xtb_symbol).strip().upper(), None)
    save_ticker_overrides(overrides)
    return overrides


def map_ticker_to_yahoo(ticker: str) -> str:
    """
    Konwertuje symbol z XTB na format Yahoo Finance.

    - nadpisanie z ticker_overrides.json (najwyższy priorytet)
    - AKBA.US → AKBA
    - XTB.PL → XTB.WA
    - JD.UK → JD.L
    - TICKER_MAP dla gołych symboli
    """
    normalized = str(ticker).strip().upper()
    if not normalized:
        raise ValueError("Empty ticker symbol.")

    # Multi-account: „VWCE [EUR]”
    if " [" in normalized:
        normalized = normalized.split(" [", 1)[0].strip()

    overrides = load_ticker_overrides()
    if normalized in overrides:
        return overrides[normalized]

    if normalized.endswith(".US"):
        base = normalized[:-3]
        return overrides.get(base, base)

    if normalized.endswith(".PL"):
        base = normalized[:-3]
        return overrides.get(base, overrides.get(normalized, f"{base}.WA"))

    if normalized.endswith(".UK"):
        base = normalized[:-3]
        return overrides.get(base, f"{base}.L")

    if "." in normalized:
        return overrides.get(normalized, normalized)

    if normalized in overrides:
        return overrides[normalized]
    return TICKER_MAP.get(normalized, normalized)


def positions_missing_prices(analyzed) -> list[dict[str, str]]:
    """Lista otwartych pozycji bez ceny Yahoo (do UX mapowania)."""
    import math

    import pandas as pd

    if analyzed is None or getattr(analyzed, "empty", True):
        return []
    if "market_price" not in analyzed.columns:
        return []
    rows: list[dict[str, str]] = []
    for _, row in analyzed.iterrows():
        price = row.get("market_price")
        missing = price is None or (isinstance(price, float) and math.isnan(price)) or pd.isna(price)
        if not missing:
            continue
        rows.append(
            {
                "ticker_xtb": str(row.get("ticker_xtb", "")),
                "ticker_yahoo": str(row.get("ticker_yahoo", "")),
            }
        )
    return rows
