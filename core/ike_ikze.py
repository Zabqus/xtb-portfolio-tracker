"""
Porównanie kont emerytalnych IKE / IKZE vs zwykłe konto maklerskie.

Model edukacyjny (horyzont do emerytury, wypłata całości na końcu):
- **Zwykłe**: wzrost składany, na końcu Belka 19% od zysków.
- **IKE**: ten sam wzrost, wypłata bez Belki (warunek: po 60. r.ż. + limity).
- **IKZE**: wpłata odliczana od PIT → zwrot = wpłata × stawka; zwroty reinwestowane
  na zwykłym (Belka od ich zysków); na końcu ryczałt 10% od salda IKZE.

Limity roczne są konfigurowalne (zmieniają się co rok) — domyślnie wartości 2025.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.tax_harvest import BELKA_RATE

# Limity wpłat 2025 (PLN) — źródło: obwieszczenia Min. Rodziny / ZUS; zmieniane co rok.
IKE_LIMIT_2025 = 26_019.0
IKZE_LIMIT_2025 = 10_407.0
IKZE_LIMIT_BIZ_2025 = 15_611.0  # działalność gospodarcza / 1.5×

IKZE_EXIT_RATE = 0.10  # ryczałt przy wypłacie po 65. r.ż.

PIT_RATES = {
    "12% (skala I próg)": 0.12,
    "32% (skala II próg)": 0.32,
    "19% (B2B / liniowy)": 0.19,
}


@dataclass
class AccountProjection:
    """Wynik projekcji jednego typu konta."""

    label: str
    annual_contribution: float       # faktyczna wpłata (po limicie)
    total_contributed: float
    gross_value: float                # saldo przed podatkiem wyjścia
    exit_tax: float                   # Belka / ryczałt IKZE / 0
    side_pocket_net: float            # netto z reinwestowanych zwrotów PIT (tylko IKZE)
    net_value: float                  # majątek netto na końcu
    tax_saved_vs_taxable: float       # różnica netto vs to samo na zwykłym (ta sama wpłata)
    immediate_refund_annual: float    # roczny zwrot PIT (IKZE)
    capped: bool                      # True jeśli wpłata ucięta limitem


@dataclass
class IkeIkzeComparison:
    years: int
    annual_return_pct: float
    requested_contribution: float
    pit_rate: float
    ike_limit: float
    ikze_limit: float
    taxable: AccountProjection
    ike: AccountProjection
    ikze: AccountProjection
    trajectory: pd.DataFrame = field(default_factory=pd.DataFrame)
    # kolumny: year, taxable_net, ike_net, ikze_net


def _future_value_annuity(annual_contribution: float, rate: float, years: int) -> float:
    """Wartość przyszła renty zwykłej (wpłata na koniec każdego roku)."""
    c = max(0.0, float(annual_contribution))
    n = max(0, int(years))
    r = float(rate)
    if n == 0:
        return 0.0
    if abs(r) < 1e-12:
        return c * n
    return c * ((1.0 + r) ** n - 1.0) / r


def _project_path(annual_contribution: float, rate: float, years: int) -> list[float]:
    """Saldo brutto po każdym roku (wpłata na koniec roku, potem brak — już w FV)."""
    c = max(0.0, float(annual_contribution))
    r = float(rate)
    value = 0.0
    path = [0.0]
    for _ in range(max(0, int(years))):
        value = value * (1.0 + r) + c
        path.append(value)
    return path


def _taxable_net_from_gross(gross: float, contributed: float, belka: float = BELKA_RATE) -> tuple[float, float]:
    gains = max(0.0, gross - contributed)
    tax = gains * belka
    return gross - tax, tax


def compare_accounts(
    annual_contribution: float,
    years: int,
    annual_return_pct: float,
    pit_rate: float,
    *,
    ike_limit: float = IKE_LIMIT_2025,
    ikze_limit: float = IKZE_LIMIT_2025,
    belka_rate: float = BELKA_RATE,
    ikze_exit_rate: float = IKZE_EXIT_RATE,
) -> IkeIkzeComparison:
    """
    Porównuje trzy konta przy tej samej żądanej rocznej wpłacie i stopie zwrotu.

    Wpłaty na IKE/IKZE są ucinane limitem; zwykłe konto przyjmuje pełną kwotę.
    Dla sprawiedliwego „tax_saved” IKE/IKZE vs taxable liczymy też wariant
    taxable przy *tej samej* (uciętej) wpłacie.
    """
    years = max(0, int(years))
    rate = float(annual_return_pct) / 100.0
    requested = max(0.0, float(annual_contribution))
    pit = max(0.0, min(1.0, float(pit_rate)))
    ike_lim = max(0.0, float(ike_limit))
    ikze_lim = max(0.0, float(ikze_limit))

    c_taxable = requested
    c_ike = min(requested, ike_lim) if ike_lim > 0 else 0.0
    c_ikze = min(requested, ikze_lim) if ikze_lim > 0 else 0.0

    path_t = _project_path(c_taxable, rate, years)
    path_ike = _project_path(c_ike, rate, years)
    path_ikze = _project_path(c_ikze, rate, years)

    # Zwroty PIT z IKZE reinwestowane na zwykłym (Belka na końcu od zysków kieszeni).
    refund_annual = c_ikze * pit
    path_refund = _project_path(refund_annual, rate, years)

    rows: list[dict] = []
    for y in range(years + 1):
        contrib_y = c_taxable * y
        t_net, _ = _taxable_net_from_gross(path_t[y], contrib_y, belka_rate)

        ike_contrib_y = c_ike * y
        ike_net = path_ike[y]  # bez Belki

        ikze_gross = path_ikze[y]
        ikze_exit = ikze_gross * ikze_exit_rate
        refund_contrib_y = refund_annual * y
        refund_net, _ = _taxable_net_from_gross(path_refund[y], refund_contrib_y, belka_rate)
        ikze_net = ikze_gross - ikze_exit + refund_net

        rows.append(
            {
                "year": y,
                "taxable_net": t_net,
                "ike_net": ike_net,
                "ikze_net": ikze_net,
            }
        )

    trajectory = pd.DataFrame(rows)

    # Wyniki końcowe
    total_t = c_taxable * years
    gross_t = path_t[-1] if path_t else 0.0
    net_t, tax_t = _taxable_net_from_gross(gross_t, total_t, belka_rate)

    total_ike = c_ike * years
    gross_ike = path_ike[-1] if path_ike else 0.0
    # Taxable przy tej samej wpłacie co IKE — do „zaoszczędzonego podatku”
    peer_ike_gross = _future_value_annuity(c_ike, rate, years)
    peer_ike_net, _ = _taxable_net_from_gross(peer_ike_gross, total_ike, belka_rate)

    total_ikze = c_ikze * years
    gross_ikze = path_ikze[-1] if path_ikze else 0.0
    exit_ikze = gross_ikze * ikze_exit_rate
    refund_gross = path_refund[-1] if path_refund else 0.0
    refund_total = refund_annual * years
    refund_net, _ = _taxable_net_from_gross(refund_gross, refund_total, belka_rate)
    net_ikze = gross_ikze - exit_ikze + refund_net

    peer_ikze_gross = _future_value_annuity(c_ikze, rate, years)
    peer_ikze_net, _ = _taxable_net_from_gross(peer_ikze_gross, total_ikze, belka_rate)

    taxable = AccountProjection(
        label="Zwykłe",
        annual_contribution=c_taxable,
        total_contributed=total_t,
        gross_value=gross_t,
        exit_tax=tax_t,
        side_pocket_net=0.0,
        net_value=net_t,
        tax_saved_vs_taxable=0.0,
        immediate_refund_annual=0.0,
        capped=False,
    )
    ike = AccountProjection(
        label="IKE",
        annual_contribution=c_ike,
        total_contributed=total_ike,
        gross_value=gross_ike,
        exit_tax=0.0,
        side_pocket_net=0.0,
        net_value=gross_ike,
        tax_saved_vs_taxable=gross_ike - peer_ike_net,  # = peer_ike_tax przy tej samej wpłacie
        immediate_refund_annual=0.0,
        capped=requested > ike_lim + 1e-9,
    )
    ikze = AccountProjection(
        label="IKZE",
        annual_contribution=c_ikze,
        total_contributed=total_ikze,
        gross_value=gross_ikze,
        exit_tax=exit_ikze,
        side_pocket_net=refund_net,
        net_value=net_ikze,
        tax_saved_vs_taxable=net_ikze - peer_ikze_net,
        immediate_refund_annual=refund_annual,
        capped=requested > ikze_lim + 1e-9,
    )

    return IkeIkzeComparison(
        years=years,
        annual_return_pct=float(annual_return_pct),
        requested_contribution=requested,
        pit_rate=pit,
        ike_limit=ike_lim,
        ikze_limit=ikze_lim,
        taxable=taxable,
        ike=ike,
        ikze=ikze,
        trajectory=trajectory,
    )
