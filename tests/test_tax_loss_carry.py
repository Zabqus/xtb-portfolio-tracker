"""Ledżer przenoszenia strat 5 lat / max 50%."""

from __future__ import annotations

from core.tax_loss_carry import (
    CarryEntry,
    apply_carry_forward,
    eligible_for_year,
    max_deductible_this_year,
)


def test_eligibility_window():
    e = CarryEntry(origin_year=2020, original_loss=10_000.0)
    assert not eligible_for_year(e, 2020)
    assert eligible_for_year(e, 2021)
    assert eligible_for_year(e, 2025)
    assert not eligible_for_year(e, 2026)


def test_max_50_percent_per_year():
    e = CarryEntry(origin_year=2023, original_loss=10_000.0)
    assert max_deductible_this_year(e) == 5_000.0
    e.used_so_far = 5_000.0
    assert max_deductible_this_year(e) == 5_000.0
    e.used_so_far = 8_000.0
    assert max_deductible_this_year(e) == 2_000.0


def test_apply_oldest_first_and_cap_by_gain():
    entries = [
        CarryEntry(origin_year=2022, original_loss=4_000.0),
        CarryEntry(origin_year=2023, original_loss=10_000.0),
    ]
    result = apply_carry_forward(2024, capital_net=6_000.0, entries=entries, persist=False)
    assert result.applied == 6_000.0  # 2000 from 2022 + 4000 from 2023 (50% caps)
    assert result.base_after == 0.0
    # 2022: 50% of 4000 = 2000
    # 2023: 50% of 10000 = 5000, but only 4000 gain left → 4000
    by_origin = {d["origin_year"]: d["applied"] for d in result.details}
    assert by_origin[2022] == 2000.0
    assert by_origin[2023] == 4000.0


def test_no_apply_when_net_loss():
    entries = [CarryEntry(origin_year=2023, original_loss=5_000.0)]
    result = apply_carry_forward(2024, capital_net=-1_000.0, entries=entries)
    assert result.applied == 0.0
    assert result.base_after == -1_000.0
