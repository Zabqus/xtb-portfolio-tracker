"""
Tax-loss harvesting (optymalizacja podatkowa pod podatek Belki 19%).

Idea: zrealizowane zyski kapitałowe są opodatkowane 19%. Sprzedając pozycje
z niezrealizowaną stratą **przed końcem roku**, obniżasz podstawę opodatkowania
o tę stratę → płacisz mniejszy podatek (lub przenosisz stratę na kolejne lata).

Ważne dla PL:
- Strata kapitałowa pomniejsza wyłącznie **zyski kapitałowe**, nie dywidendy
  (dywidendy są opodatkowane osobno, ryczałtowo 19%).
- Niewykorzystaną stratę można rozliczać przez 5 lat (max 50% rocznie).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

BELKA_RATE = 0.19


@dataclass
class HarvestResult:
    realized_gain_ytd: float          # zrealizowany zysk/strata kapit. w roku
    harvestable_loss: float           # suma niezrealizowanych strat (otwarte pozycje)
    tax_before: float                 # podatek od bieżącej podstawy
    offset_used: float                # ile straty realnie zmniejsza tegoroczny podatek
    tax_after: float                  # podatek po zebraniu strat
    tax_saved: float                  # oszczędność w tym roku
    carry_forward: float              # nadwyżka straty przeniesiona na kolejne lata
    losers: pd.DataFrame = field(default_factory=pd.DataFrame)
    currency: str = ""
    has_losers: bool = False


def compute_tax_harvest(
    analyzed: pd.DataFrame,
    realized_gain_ytd: float,
    currency: str,
    tax_rate: float = BELKA_RATE,
) -> HarvestResult:
    """
    Liczy potencjał tax-loss harvesting na podstawie otwartych pozycji ze stratą.

    analyzed: otwarte pozycje (kolumny: ticker_xtb, market_value, pnl, roi_pct).
    realized_gain_ytd: zrealizowany wynik kapitałowy w bieżącym roku (z Closed Positions).
    """
    empty = HarvestResult(
        realized_gain_ytd=float(realized_gain_ytd),
        harvestable_loss=0.0,
        tax_before=max(0.0, float(realized_gain_ytd) * tax_rate),
        offset_used=0.0,
        tax_after=max(0.0, float(realized_gain_ytd) * tax_rate),
        tax_saved=0.0,
        carry_forward=0.0,
        currency=currency,
        has_losers=False,
    )

    if analyzed is None or analyzed.empty or "pnl" not in analyzed.columns:
        return empty

    losers = analyzed[analyzed["pnl"] < 0].copy()
    if losers.empty:
        return empty

    losers = losers.sort_values("pnl")  # największa strata pierwsza
    harvestable_loss = float(-losers["pnl"].sum())

    tax_before = max(0.0, float(realized_gain_ytd) * tax_rate)
    # Strata pomniejsza dodatnią podstawę; offset ograniczony do tegorocznych zysków.
    offset_used = min(harvestable_loss, max(0.0, float(realized_gain_ytd)))
    base_after = float(realized_gain_ytd) - harvestable_loss
    tax_after = max(0.0, base_after * tax_rate)
    tax_saved = tax_before - tax_after
    carry_forward = max(0.0, harvestable_loss - max(0.0, float(realized_gain_ytd)))

    # Tabela kandydatów z narastającą tarczą podatkową.
    losers_out = losers.copy()
    losers_out["loss"] = -losers_out["pnl"]
    losers_out["cum_loss"] = losers_out["loss"].cumsum()
    remaining_gain = max(0.0, float(realized_gain_ytd))
    losers_out["tax_shield"] = (
        losers_out["cum_loss"].clip(upper=remaining_gain).diff().fillna(
            losers_out["cum_loss"].clip(upper=remaining_gain)
        )
        * tax_rate
    )

    keep = [c for c in ("ticker_xtb", "market_value", "pnl", "roi_pct", "loss", "tax_shield") if c in losers_out.columns]
    losers_out = losers_out[keep].reset_index(drop=True)

    return HarvestResult(
        realized_gain_ytd=float(realized_gain_ytd),
        harvestable_loss=harvestable_loss,
        tax_before=tax_before,
        offset_used=offset_used,
        tax_after=tax_after,
        tax_saved=tax_saved,
        carry_forward=carry_forward,
        losers=losers_out,
        currency=currency,
        has_losers=True,
    )
