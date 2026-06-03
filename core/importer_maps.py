"""XTB ticker → Yahoo Finance symbol mapping."""

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


def map_ticker_to_yahoo(ticker: str) -> str:
    """
    Konwertuje symbol z XTB na format Yahoo Finance.

    - AKBA.US → AKBA
    - XTB.PL → XTB.WA
    - JD.UK → JD.L
    """
    normalized = str(ticker).strip().upper()
    if not normalized:
        raise ValueError("Empty ticker symbol.")

    if normalized.endswith(".US"):
        return normalized[:-3]

    if normalized.endswith(".PL"):
        return f"{normalized[:-3]}.WA"

    if normalized.endswith(".UK"):
        return f"{normalized[:-3]}.L"

    if "." in normalized:
        return normalized

    return TICKER_MAP.get(normalized, normalized)
