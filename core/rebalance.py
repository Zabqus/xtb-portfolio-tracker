"""
Rebalancing helper – sugestie dokupień/redukcji do docelowej alokacji.

Działa na poziomie koszyków (sektor lub region): porównuje bieżący udział
z docelowym i wylicza, ile wartości (w walucie wyświetlania) dokupić lub
zredukować w każdym koszyku, aby trafić w cel.
"""

from __future__ import annotations

import pandas as pd


def compute_rebalance(
    breakdown: pd.DataFrame,
    target_pct: dict[str, float],
    group_col: str,
    *,
    new_cash: float = 0.0,
) -> pd.DataFrame:
    """
    Porównuje bieżącą alokację z docelową i sugeruje akcję.

    breakdown: kolumny [group_col, market_value, weight_pct] (z aggregate_breakdown).
    target_pct: docelowy udział % per koszyk (suma ~100).
    new_cash: dodatkowy kapitał do rozdysponowania (0 = sam rebalancing istniejącego).

    Zwraca tabelę: koszyk, wartość, udział %, cel %, dryf pp, sugerowana zmiana wartości.
    """
    if breakdown is None or breakdown.empty or group_col not in breakdown.columns:
        return pd.DataFrame()

    df = breakdown.copy()
    current_total = float(df["market_value"].sum())
    new_total = current_total + float(new_cash)
    if new_total <= 0:
        return pd.DataFrame()

    df["target_pct"] = df[group_col].map(lambda b: float(target_pct.get(str(b), 0.0)))
    df["current_pct"] = df["weight_pct"]
    df["drift_pp"] = df["current_pct"] - df["target_pct"]
    df["target_value"] = df["target_pct"] / 100.0 * new_total
    df["delta_value"] = df["target_value"] - df["market_value"]

    def _action(delta: float) -> str:
        if delta > current_total * 0.005:
            return "Dokup"
        if delta < -current_total * 0.005:
            return "Zredukuj"
        return "OK"

    df["action"] = df["delta_value"].map(_action)
    return df.sort_values("delta_value", ascending=False).reset_index(drop=True)


def suggest_cash_allocation(
    breakdown: pd.DataFrame,
    target_pct: dict[str, float],
    group_col: str,
    new_cash: float,
) -> pd.DataFrame:
    """
    Rozdziela NOWĄ gotówkę wyłącznie na niedoważone koszyki (bez sprzedaży).

    Zwraca tabelę: koszyk, brakująca wartość, sugerowana wpłata, udział wpłaty %.
    """
    if new_cash <= 0 or breakdown is None or breakdown.empty:
        return pd.DataFrame()

    df = breakdown.copy()
    current_total = float(df["market_value"].sum())
    new_total = current_total + float(new_cash)

    df["target_value"] = df[group_col].map(
        lambda b: float(target_pct.get(str(b), 0.0)) / 100.0 * new_total
    )
    df["shortfall"] = (df["target_value"] - df["market_value"]).clip(lower=0.0)
    total_shortfall = float(df["shortfall"].sum())
    if total_shortfall <= 0:
        return pd.DataFrame()

    df["suggested_buy"] = df["shortfall"] / total_shortfall * float(new_cash)
    df["buy_share_pct"] = df["suggested_buy"] / float(new_cash) * 100.0

    out = df[df["suggested_buy"] > 0][
        [group_col, "market_value", "shortfall", "suggested_buy", "buy_share_pct"]
    ]
    return out.sort_values("suggested_buy", ascending=False).reset_index(drop=True)


def normalize_targets(raw_targets: dict[str, float]) -> tuple[dict[str, float], float]:
    """Zwraca (cele, suma). Pomaga ostrzec użytkownika, gdy suma ≠ 100%."""
    clean = {k: max(0.0, float(v)) for k, v in raw_targets.items()}
    return clean, float(sum(clean.values()))


def suggest_ticker_orders(
    enriched: pd.DataFrame,
    basket_rebalance: pd.DataFrame,
    group_col: str,
    *,
    min_order: float = 0.0,
) -> pd.DataFrame:
    """
    Rozbija sugestie koszykowe na konkretne tickery.

    - Dokup: rozdział `delta_value` proporcjonalnie do wartości pozycji w koszyku
    - Zredukuj: to samo dla ujemnych delt
    - Koszyk bez pozycji: pomijany (brak instrumentu do wskazania)

    enriched: wynik enrich_portfolio_allocation (ticker_xtb, group_col, market_value, …).
    basket_rebalance: wynik compute_rebalance.
    """
    if (
        enriched is None
        or enriched.empty
        or basket_rebalance is None
        or basket_rebalance.empty
        or group_col not in enriched.columns
        or group_col not in basket_rebalance.columns
    ):
        return pd.DataFrame()

    rows: list[dict] = []
    for _, basket in basket_rebalance.iterrows():
        name = str(basket[group_col])
        delta = float(basket.get("delta_value", 0.0))
        action = str(basket.get("action", "OK"))
        if action == "OK" or abs(delta) < 1e-9:
            continue

        members = enriched[enriched[group_col].astype(str) == name].copy()
        if members.empty:
            rows.append(
                {
                    "basket": name,
                    "ticker_xtb": "—",
                    "ticker_yahoo": "",
                    "action": action,
                    "suggested_value": round(delta, 2),
                    "basket_delta": round(delta, 2),
                    "weight_in_basket_pct": None,
                    "note": "Brak pozycji w koszyku — wybierz instrument ręcznie",
                }
            )
            continue

        total = float(members["market_value"].sum())
        if total <= 0:
            continue

        for _, pos in members.iterrows():
            share = float(pos["market_value"]) / total
            order_value = delta * share
            if abs(order_value) < float(min_order):
                continue
            rows.append(
                {
                    "basket": name,
                    "ticker_xtb": str(pos.get("ticker_xtb", "")),
                    "ticker_yahoo": str(pos.get("ticker_yahoo", "")),
                    "action": "Dokup" if order_value > 0 else "Zredukuj",
                    "suggested_value": round(order_value, 2),
                    "basket_delta": round(delta, 2),
                    "weight_in_basket_pct": round(share * 100.0, 1),
                    "note": "",
                }
            )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["_abs"] = out["suggested_value"].abs()
    return out.sort_values(["_abs", "basket"], ascending=[False, True]).drop(
        columns="_abs"
    ).reset_index(drop=True)
