"""
Kursy średnie NBP (tabela A) — podstawa przeliczeń do Belki / PIT-38.

API: https://api.nbp.pl  (bez klucza). Dla weekendów/świąt cofamy się do
ostatniego dnia roboczego z notowaniem. Wyświetlanie w UI nadal może używać Yahoo.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from functools import lru_cache

NBP_TABLE = "a"
NBP_LOOKBACK_DAYS = 14
_USER_AGENT = "xtb-portfolio-tracker/1.0 (local; NBP table A)"


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    ts = pd_to_date(value)
    return ts


def pd_to_date(value: object) -> date:
    """Bezpieczna konwersja bez twardej zależności od pandas w sygnaturze publicznej."""
    if hasattr(value, "date") and callable(value.date) and not isinstance(value, date):
        try:
            return value.date()  # type: ignore[no-any-return]
        except Exception:
            pass
    text = str(value)[:10]
    return date.fromisoformat(text)


@lru_cache(maxsize=4096)
def fetch_nbp_mid_rate(currency: str, on_date: date) -> float | None:
    """
    Średni kurs NBP (PLN za 1 jednostkę waluty) na dany dzień lub wcześniejszy
    dzień roboczy. PLN → 1.0. None gdy brak danych / błąd sieci.
    """
    code = str(currency).strip().upper()
    if not code or code == "PLN":
        return 1.0
    if code in {"MULTI", "NAN", "NONE", "<NA>"}:
        return None

    day = on_date
    for _ in range(NBP_LOOKBACK_DAYS):
        url = (
            f"https://api.nbp.pl/api/exchangerates/rates/{NBP_TABLE}/"
            f"{code}/{day.isoformat()}/?format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            rates = payload.get("rates") or []
            if rates:
                mid = rates[0].get("mid")
                if mid is not None:
                    return float(mid)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError):
            pass
        day -= timedelta(days=1)
    return None


def nbp_amount_to_pln(
    amount: float,
    currency: str,
    on_date: date | datetime | str,
    *,
    rate_cache: dict[tuple[str, date], float | None] | None = None,
) -> float | None:
    """
    Przelicza kwotę na PLN kursem NBP z dnia (lub poprzedniego dnia roboczego).
    Zwraca None, gdy kurs niedostępny.
    """
    if amount is None:
        return None
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    code = str(currency).strip().upper()
    day = _as_date(on_date)
    cache_key = (code, day)
    if rate_cache is not None and cache_key in rate_cache:
        rate = rate_cache[cache_key]
    else:
        rate = fetch_nbp_mid_rate(code, day)
        if rate_cache is not None:
            rate_cache[cache_key] = rate
    if rate is None:
        return None
    return value * rate


def clear_nbp_cache() -> None:
    fetch_nbp_mid_rate.cache_clear()
