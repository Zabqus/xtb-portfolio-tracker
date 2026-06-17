"""
Stopy zwrotu portfela ważone czasem (TWR) i przepływami pieniężnymi (MWR/XIRR).

Dlaczego to ważne: przy regularnych wpłatach zwykłe ROI (PnL / koszt) myli timing
dopłat z faktyczną efektywnością inwestycji.

- **MWR / XIRR** – uwzględnia kiedy i ile wpłaciłeś/wypłaciłeś. To „Twoja” roczna
  stopa zwrotu na zainwestowanym kapitale.
- **TWR** – usuwa wpływ momentu dopłat; mierzy samą jakość doboru pozycji
  (porównywalne z indeksami / funduszami).

Wszystkie kwoty przepływów (`Amount` z Cash Operations) są w walucie konta,
więc MWR liczony jest w walucie konta. TWR jest bezwymiarowy (procentowy).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.transactions import parse_cash_operations_trades

# Typy operacji w Cash Operations traktowane jako zewnętrzne przepływy inwestora.
DEPOSIT_RE = r"deposit|cash in|wpłata|wplata|payment in"
WITHDRAWAL_RE = r"withdraw|cash out|wypłata|wyplata|payout"
TAX_RE = r"tax|podatek"

DAYS_PER_YEAR = 365.0

# Poniżej tylu dni nie annualizujemy zwrotu – roczne przeliczenie krótkiego
# okresu daje absurdalne wartości (np. +8% w miesiąc → setki % rocznie).
MIN_ANNUALIZE_DAYS = 90


@dataclass
class MWRResult:
    """Wynik stopy zwrotu ważonej przepływami (money-weighted)."""

    xirr_pct: float | None  # roczna (annualizowana) stopa MWR; None gdy okres < 90 dni
    net_contributions: float  # wpłaty − wypłaty (kapitał własny netto)
    terminal_value: float  # bieżąca wartość konta (pozycje + gotówka)
    total_gain: float  # terminal_value − net_contributions
    simple_return_pct: float | None  # łączny zwrot na kapitale (bez annualizacji)
    cash_balance: float  # szacowane wolne środki (suma Amount)
    holdings_value: float  # wartość otwartych pozycji
    flow_count: int
    days: int = 0  # rozpiętość od pierwszej wpłaty do dziś
    has_data: bool = True
    currency: str = ""


@dataclass
class TWRResult:
    """Wynik stopy zwrotu ważonej czasem (time-weighted)."""

    twr_total_pct: float | None  # łączny zwrot TWR za cały okres
    twr_annualized_pct: float | None
    days: int
    index: pd.DataFrame = field(default_factory=pd.DataFrame)  # date, twr_index (start=100)
    has_data: bool = False


# ─────────────────────────── XIRR ───────────────────────────

def _xnpv(rate: float, amounts: np.ndarray, years: np.ndarray) -> float:
    """Wartość bieżąca netto przepływów dla danej stopy rocznej."""
    return float(np.sum(amounts / np.power(1.0 + rate, years)))


def compute_xirr(
    flows: list[tuple[pd.Timestamp, float]],
    *,
    low: float = -0.9999,
    high: float = 100.0,
) -> float | None:
    """
    XIRR – wewnętrzna stopa zwrotu dla nieregularnych przepływów.

    Konwencja inwestora: wpłata = ujemna, wypłata / wartość końcowa = dodatnia.
    Zwraca roczną stopę (np. 0.12 = 12%) lub None, gdy brak rozwiązania.
    """
    if len(flows) < 2:
        return None

    flows = sorted(flows, key=lambda f: f[0])
    t0 = flows[0][0]
    amounts = np.array([a for _, a in flows], dtype=float)
    years = np.array([(d - t0).days / DAYS_PER_YEAR for d, _ in flows], dtype=float)

    # XIRR istnieje tylko, gdy przepływy mają różne znaki.
    if np.all(amounts >= 0) or np.all(amounts <= 0):
        return None

    f_low = _xnpv(low, amounts, years)
    f_high = _xnpv(high, amounts, years)
    if np.isnan(f_low) or np.isnan(f_high) or f_low * f_high > 0:
        # Brak zmiany znaku w przedziale – stopa poza zakresem.
        return None

    # Bisekcja (stabilniejsza od Newtona dla dziwnych przepływów).
    lo, hi = low, high
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = _xnpv(mid, amounts, years)
        if abs(f_mid) < 1e-7:
            return float(mid)
        if f_low * f_mid < 0:
            hi = mid
            f_high = f_mid
        else:
            lo = mid
            f_low = f_mid
    return float((lo + hi) / 2.0)


# ─────────────────────────── przepływy zewnętrzne ───────────────────────────

def extract_external_cashflows(cash_ops: pd.DataFrame) -> pd.DataFrame:
    """
    Wpłaty i wypłaty z Cash Operations (kolumny: date, amount, kind).

    `amount` w walucie konta, ze znakiem XTB (wpłata > 0, wypłata < 0).
    Pomija podatki (np. „… interest tax”), które trafiają do regex wypłat.
    """
    if cash_ops is None or cash_ops.empty or "Type" not in cash_ops.columns:
        return pd.DataFrame(columns=["date", "amount", "kind"])

    types = cash_ops["Type"].astype(str)
    is_tax = types.str.contains(TAX_RE, case=False, na=False)
    is_dep = types.str.contains(DEPOSIT_RE, case=False, na=False) & ~is_tax
    is_wd = types.str.contains(WITHDRAWAL_RE, case=False, na=False) & ~is_tax

    rows: list[dict] = []
    for mask, kind in ((is_dep, "deposit"), (is_wd, "withdrawal")):
        subset = cash_ops[mask].copy()
        if subset.empty:
            continue
        subset["date"] = pd.to_datetime(subset.get("Time"), errors="coerce")
        subset["amount"] = pd.to_numeric(subset.get("Amount"), errors="coerce")
        subset = subset.dropna(subset=["date", "amount"])
        for _, r in subset.iterrows():
            rows.append({"date": r["date"], "amount": float(r["amount"]), "kind": kind})

    if not rows:
        return pd.DataFrame(columns=["date", "amount", "kind"])
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def estimate_cash_balance(cash_ops: pd.DataFrame) -> float:
    """
    Szacuje wolne środki na koncie = suma wszystkich Amount.

    Poprawne, gdy eksport obejmuje całą historię konta (od pierwszej wpłaty).
    """
    if cash_ops is None or cash_ops.empty or "Amount" not in cash_ops.columns:
        return 0.0
    amounts = pd.to_numeric(cash_ops["Amount"], errors="coerce").dropna()
    return float(amounts.sum())


def compute_mwr(
    cash_ops: pd.DataFrame,
    holdings_value: float,
    *,
    currency: str = "",
    as_of: pd.Timestamp | None = None,
) -> MWRResult:
    """
    MWR (XIRR) konta: przepływy zewnętrzne + bieżąca wartość konta jako przepływ końcowy.

    holdings_value: wartość otwartych pozycji w walucie konta.
    Wartość końcowa = pozycje + szacowana gotówka.
    """
    flows_df = extract_external_cashflows(cash_ops)
    cash_balance = estimate_cash_balance(cash_ops)
    terminal_value = float(holdings_value) + cash_balance

    if flows_df.empty:
        return MWRResult(
            xirr_pct=None,
            net_contributions=0.0,
            terminal_value=terminal_value,
            total_gain=0.0,
            simple_return_pct=None,
            cash_balance=cash_balance,
            holdings_value=float(holdings_value),
            flow_count=0,
            days=0,
            has_data=False,
            currency=currency,
        )

    deposits = float(flows_df.loc[flows_df["kind"] == "deposit", "amount"].sum())
    withdrawals = float(flows_df.loc[flows_df["kind"] == "withdrawal", "amount"].sum())
    net_contributions = deposits + withdrawals  # withdrawals są ujemne

    as_of = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp.now()
    span_days = int((as_of.normalize() - flows_df["date"].min().normalize()).days)

    # Konwencja inwestora: wpłaty/wypłaty ze znakiem przeciwnym do Amount,
    # wartość końcowa dodatnia.
    flows: list[tuple[pd.Timestamp, float]] = [
        (pd.Timestamp(d), -float(a)) for d, a in zip(flows_df["date"], flows_df["amount"])
    ]
    flows.append((as_of, terminal_value))

    xirr = compute_xirr(flows)
    # Krótki okres → roczne przeliczenie myli; pokazujemy tylko zwrot skumulowany.
    xirr_pct = (xirr * 100) if (xirr is not None and span_days >= MIN_ANNUALIZE_DAYS) else None
    total_gain = terminal_value - net_contributions
    simple_return = (total_gain / net_contributions * 100) if net_contributions > 0 else None

    return MWRResult(
        xirr_pct=xirr_pct,
        net_contributions=net_contributions,
        terminal_value=terminal_value,
        total_gain=total_gain,
        simple_return_pct=simple_return,
        cash_balance=cash_balance,
        holdings_value=float(holdings_value),
        flow_count=len(flows_df),
        days=span_days,
        has_data=True,
        currency=currency,
    )


# ─────────────────────────── TWR ───────────────────────────

def _daily_net_investment(cash_ops: pd.DataFrame) -> pd.Series:
    """
    Dzienny przepływ kapitału do/z pozycji w jednostkach timeline
    (Σ kupno qty×price − Σ sprzedaż qty×price), indeks = data (znormalizowana).
    """
    trades = parse_cash_operations_trades(cash_ops)
    if trades.empty:
        return pd.Series(dtype=float)
    signed = trades.assign(
        flow=lambda d: np.where(d["side"] == "OPEN", 1.0, -1.0)
        * d["quantity"].astype(float)
        * d["price"].astype(float)
    )
    return signed.groupby(signed["trade_date"].dt.normalize())["flow"].sum()


def compute_twr(timeline: pd.DataFrame, cash_ops: pd.DataFrame) -> TWRResult:
    """
    TWR z timeline pozycji, usuwając dzienny dopływ kapitału (kupna/sprzedaże).

    Zwrot dnia t: r = (V_t − F_t) / V_{t-1} − 1, gdzie F_t = kapitał wpłacony w dniu t.
    Łączny TWR = Π(1 + r) − 1. Zwraca też indeks wzrostu (start = 100) do wykresów.
    """
    empty = TWRResult(twr_total_pct=None, twr_annualized_pct=None, days=0)
    if timeline is None or timeline.empty or "market_value" not in timeline.columns:
        return empty

    df = timeline.dropna(subset=["date", "market_value"]).sort_values("date").copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[df["market_value"] > 0].reset_index(drop=True)
    if len(df) < 2:
        return empty

    flows = _daily_net_investment(cash_ops)

    dates = df["date"].tolist()
    values = df["market_value"].astype(float).tolist()

    # Próg mianownika: przy bardzo małym kapitale (pierwsze dni) drobne różnice
    # między ceną wykonania a kursem zamknięcia dają fałszywe, ogromne zwroty.
    value_floor = max(max(values) * 0.05, 1.0)

    growth = 1.0
    index_dates = [dates[0]]
    index_vals = [100.0]
    for i in range(1, len(df)):
        v_prev = values[i - 1]
        v_now = values[i]
        f = float(flows.get(dates[i], 0.0)) if not flows.empty else 0.0
        if v_prev < value_floor:
            # Zbyt mały kapitał odniesienia – pomijamy (brak wpływu na łączny TWR).
            index_dates.append(dates[i])
            index_vals.append(growth * 100.0)
            continue
        r = (v_now - f) / v_prev - 1.0
        # Ogranicza absurdalne skoki dziennie do ±50%.
        if not np.isfinite(r):
            r = 0.0
        r = max(-0.5, min(0.5, r))
        growth *= (1.0 + r)
        index_dates.append(dates[i])
        index_vals.append(growth * 100.0)

    twr_total = (growth - 1.0) * 100.0
    n_days = (dates[-1] - dates[0]).days
    if n_days >= MIN_ANNUALIZE_DAYS:
        twr_ann = ((growth ** (DAYS_PER_YEAR / n_days)) - 1.0) * 100.0
    else:
        twr_ann = None

    index_df = pd.DataFrame({"date": index_dates, "twr_index": index_vals})
    return TWRResult(
        twr_total_pct=float(twr_total),
        twr_annualized_pct=float(twr_ann) if twr_ann is not None else None,
        days=int(n_days),
        index=index_df,
        has_data=True,
    )
