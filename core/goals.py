"""
Cele inwestycyjne i FIRE (Financial Independence, Retire Early).

Dwa kalkulatory oparte na danych, które aplikacja już liczy:
- **Cel wartości portfela** – procent składany + regularne dopłaty (wartość
  przyszła renty). Odpowiada: „ile lat do kwoty X?".
- **FIRE / dochód pasywny** – liczba FIRE (reguła 4%), pokrycie wydatków przez
  dywidendy (forward yield) i projekcja „snowball" wzrostu dochodu.

Cała matematyka jest lokalna (bez sieci).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

DEFAULT_SWR = 4.0            # bezpieczna stopa wypłaty (reguła 4% → mnożnik 25×)
DEFAULT_RETURN = 7.0        # domyślna roczna stopa zwrotu (%)
DEFAULT_DIV_GROWTH = 5.0    # domyślny roczny wzrost dywidend (%)
MAX_YEARS = 40


# ─────────────────────────── Cel wartości ───────────────────────────

@dataclass
class GoalProjection:
    current_value: float
    target_value: float
    monthly_contribution: float
    annual_return_pct: float
    reached_now: bool
    ever_reaches: bool
    months_to_goal: int | None
    target_date: pd.Timestamp | None
    final_value: float
    progress_pct: float
    trajectory: pd.DataFrame = field(default_factory=pd.DataFrame)  # date, value, invested


def project_goal(
    current_value: float,
    target_value: float,
    monthly_contribution: float,
    annual_return_pct: float,
    *,
    max_years: int = MAX_YEARS,
) -> GoalProjection:
    """
    Symuluje miesięczny wzrost portfela (procent składany + dopłaty) aż do celu.

    Zwraca projekcję z trajektorią (wartość i skumulowany wkład w czasie).
    """
    current_value = max(0.0, float(current_value))
    target_value = max(0.0, float(target_value))
    contribution = max(0.0, float(monthly_contribution))
    monthly_rate = (1.0 + annual_return_pct / 100.0) ** (1.0 / 12.0) - 1.0

    today = pd.Timestamp.now().normalize()
    reached_now = current_value >= target_value > 0

    rows: list[dict] = [{"date": today, "value": current_value, "invested": current_value}]
    value = current_value
    invested = current_value
    months_to_goal: int | None = 0 if reached_now else None

    max_months = max_years * 12
    for m in range(1, max_months + 1):
        value = value * (1.0 + monthly_rate) + contribution
        invested += contribution
        rows.append(
            {"date": today + pd.DateOffset(months=m), "value": value, "invested": invested}
        )
        if months_to_goal is None and value >= target_value > 0:
            months_to_goal = m
            break

    trajectory = pd.DataFrame(rows)
    ever_reaches = reached_now or months_to_goal is not None
    target_date = None
    if months_to_goal:
        target_date = today + pd.DateOffset(months=months_to_goal)
    elif reached_now:
        target_date = today

    progress = (current_value / target_value * 100.0) if target_value > 0 else 0.0

    return GoalProjection(
        current_value=current_value,
        target_value=target_value,
        monthly_contribution=contribution,
        annual_return_pct=float(annual_return_pct),
        reached_now=reached_now,
        ever_reaches=ever_reaches,
        months_to_goal=months_to_goal,
        target_date=target_date,
        final_value=float(value),
        progress_pct=min(progress, 100.0) if reached_now else progress,
        trajectory=trajectory,
    )


# ─────────────────────────── FIRE / dochód pasywny ───────────────────────────

@dataclass
class FireResult:
    annual_expenses: float
    swr_pct: float
    fire_number: float
    current_value: float
    current_yield_pct: float
    current_annual_dividends: float
    coverage_pct: float                # dywidendy teraz / wydatki
    portfolio_needed_by_yield: float   # ile portfela, by yield pokrył wydatki
    fire_progress_pct: float           # wartość / liczba FIRE
    years_to_fire_number: int | None
    years_to_dividend_cover: int | None
    snowball: pd.DataFrame = field(default_factory=pd.DataFrame)  # year, value, dividends, expenses


def compute_fire(
    current_value: float,
    annual_expenses: float,
    current_yield_pct: float,
    monthly_contribution: float,
    annual_return_pct: float,
    *,
    dividend_growth_pct: float = DEFAULT_DIV_GROWTH,
    swr_pct: float = DEFAULT_SWR,
    inflation_pct: float = 0.0,
    max_years: int = MAX_YEARS,
) -> FireResult:
    """
    Liczy liczbę FIRE i projekcję „dividend snowball" pokrycia wydatków.

    - fire_number = roczne wydatki / (SWR/100)  (reguła 4% → ×25)
    - snowball: co roku portfel rośnie o stopę zwrotu + dopłaty; dochód z dywidend
      = wartość × yield × (1+wzrost dywidend)^rok; wydatki rosną o inflację.
    """
    current_value = max(0.0, float(current_value))
    annual_expenses = max(0.0, float(annual_expenses))
    base_yield = max(0.0, float(current_yield_pct)) / 100.0
    contribution = max(0.0, float(monthly_contribution))
    r = annual_return_pct / 100.0
    g = dividend_growth_pct / 100.0
    infl = inflation_pct / 100.0

    fire_number = annual_expenses / (swr_pct / 100.0) if swr_pct > 0 else 0.0
    current_annual_dividends = current_value * base_yield
    coverage = (current_annual_dividends / annual_expenses * 100.0) if annual_expenses > 0 else 0.0
    portfolio_needed_by_yield = (annual_expenses / base_yield) if base_yield > 0 else 0.0
    fire_progress = (current_value / fire_number * 100.0) if fire_number > 0 else 0.0

    rows: list[dict] = [
        {
            "year": 0,
            "value": current_value,
            "dividends": current_annual_dividends,
            "expenses": annual_expenses,
        }
    ]
    value = current_value
    years_to_fire_number: int | None = 0 if (fire_number > 0 and current_value >= fire_number) else None
    years_to_dividend_cover: int | None = (
        0 if (annual_expenses > 0 and current_annual_dividends >= annual_expenses) else None
    )

    for year in range(1, max_years + 1):
        value = value * (1.0 + r) + contribution * 12.0
        dividends = value * base_yield * ((1.0 + g) ** year)
        expenses = annual_expenses * ((1.0 + infl) ** year)
        rows.append({"year": year, "value": value, "dividends": dividends, "expenses": expenses})

        if years_to_fire_number is None and fire_number > 0 and value >= fire_number:
            years_to_fire_number = year
        if years_to_dividend_cover is None and expenses > 0 and dividends >= expenses:
            years_to_dividend_cover = year

    snowball = pd.DataFrame(rows)

    return FireResult(
        annual_expenses=annual_expenses,
        swr_pct=float(swr_pct),
        fire_number=fire_number,
        current_value=current_value,
        current_yield_pct=float(current_yield_pct),
        current_annual_dividends=current_annual_dividends,
        coverage_pct=coverage,
        portfolio_needed_by_yield=portfolio_needed_by_yield,
        fire_progress_pct=fire_progress,
        years_to_fire_number=years_to_fire_number,
        years_to_dividend_cover=years_to_dividend_cover,
        snowball=snowball,
    )


# ─────────────────────────── Pomocnicze ───────────────────────────

def infer_monthly_contribution(cashflows: pd.DataFrame) -> float | None:
    """
    Szacuje średnią miesięczną wpłatę z historii depozytów.

    cashflows: wynik core.returns.extract_external_cashflows (kolumny date, amount, kind).
    """
    if cashflows is None or cashflows.empty or "kind" not in cashflows.columns:
        return None
    deposits = cashflows[cashflows["kind"] == "deposit"]
    if deposits.empty:
        return None
    total = float(deposits["amount"].sum())
    # Liczba kalendarzowych miesięcy objętych wpłatami (włącznie), min. 1.
    first = pd.Timestamp(deposits["date"].min()).to_period("M")
    last = pd.Timestamp(deposits["date"].max()).to_period("M")
    months = max((last - first).n + 1, 1)
    return total / months


def format_duration(months: int | None) -> str:
    """Ładny opis czasu: '3 lata 2 mies.'."""
    if months is None:
        return "—"
    if months == 0:
        return "cel już osiągnięty"
    years, rem = divmod(int(months), 12)
    parts: list[str] = []
    if years:
        parts.append(f"{years} {'rok' if years == 1 else 'lata' if 2 <= years <= 4 else 'lat'}")
    if rem:
        parts.append(f"{rem} mies.")
    return " ".join(parts) or "< 1 mies."
