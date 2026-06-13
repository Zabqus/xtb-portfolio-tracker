"""
Podstrona: alerty — pozycje przekraczające próg ±X% (ROI względem średniej ceny zakupu).
"""

import time

import pandas as pd
import streamlit as st

from core.alerts import (
    PriceAlert,
    alert_row_keys,
    build_roi_snapshot,
    check_price_alerts,
    compute_roi_alerts,
    compute_roi_deltas,
    load_price_alerts,
    mark_new_alerts,
    save_price_alerts,
)
from core.session import get_analyzed_open, get_display_currency, get_report, init_session_state
from ui.formatters import format_currency
from ui.sidebar import render_import_sidebar

init_session_state()

if "alert_threshold_pct" not in st.session_state:
    st.session_state.alert_threshold_pct = 10.0
if "alert_auto_refresh" not in st.session_state:
    st.session_state.alert_auto_refresh = False
if "alert_refresh_seconds" not in st.session_state:
    st.session_state.alert_refresh_seconds = 120
if "alert_prev_keys" not in st.session_state:
    st.session_state.alert_prev_keys = set()
if "alert_roi_snapshot" not in st.session_state:
    st.session_state.alert_roi_snapshot = None
if "alert_mode" not in st.session_state:
    st.session_state.alert_mode = "roi"

st.title("🔔 Alerty")

st.caption(
    "Powiadomienia w aplikacji (bez alertów systemowych): lista pozycji, które przekroczyły "
    "ustawiony próg **±X%** ROI względem średniej ceny zakupu z raportu XTB."
)

if not render_import_sidebar():
    st.info("Wgraj plik XTB w panelu bocznym.")
    st.stop()

if get_report() is None:
    st.stop()

with st.spinner("Aktualizacja cen…"):
    analyzed = get_analyzed_open()

if analyzed is None or analyzed.empty:
    st.warning("Brak otwartych pozycji.")
    st.stop()

currency = get_display_currency()

# --- Ustawienia ---
st.subheader("Ustawienia progu")
c1, c2, c3, c4 = st.columns([2, 2, 2, 1])

with c1:
    threshold = st.number_input(
        "Próg (|ROI %|)",
        min_value=0.5,
        max_value=500.0,
        value=float(st.session_state.alert_threshold_pct),
        step=0.5,
        help="Alert gdy zysk lub strata względem kosztu pozycji przekroczy ten procent.",
        key="alert_threshold_input",
    )
    st.session_state.alert_threshold_pct = threshold

with c2:
    direction = st.radio(
        "Kierunek",
        ["both", "gain", "loss"],
        format_func=lambda x: {"both": "± oba", "gain": "+ tylko zysk", "loss": "− tylko strata"}[x],
        horizontal=True,
        key="alert_direction_radio",
    )

with c3:
    mode = st.radio(
        "Tryb",
        ["roi", "delta"],
        format_func=lambda x: "Od średniej ceny" if x == "roi" else "Zmiana od ostatniego odświeżenia",
        horizontal=True,
        key="alert_mode_radio",
    )
    st.session_state.alert_mode = mode

with c4:
    if st.button("Odśwież", type="primary", use_container_width=True):
        st.rerun()

c5, c6, c7 = st.columns([2, 2, 2])
with c5:
    auto = st.checkbox("Auto-odświeżanie", value=st.session_state.alert_auto_refresh, key="alert_auto_cb")
    st.session_state.alert_auto_refresh = auto
with c6:
    if auto:
        secs = st.slider(
            "Co ile sekund",
            min_value=30,
            max_value=600,
            value=int(st.session_state.alert_refresh_seconds),
            step=30,
            key="alert_refresh_slider",
        )
        st.session_state.alert_refresh_seconds = secs
with c7:
    if st.button("Zapisz stan ROI (baza delty)", use_container_width=True):
        st.session_state.alert_roi_snapshot = build_roi_snapshot(analyzed)
        st.success("Zapisano snapshot ROI.")

# --- Wylicz alerty ---
if mode == "delta":
    alerts = compute_roi_deltas(
        analyzed,
        st.session_state.alert_roi_snapshot,
        threshold,
    )
    alert_mode_key = "delta"
    if st.session_state.alert_roi_snapshot is None:
        st.info("Tryb „Zmiana od ostatniego odświeżenia” wymaga zapisania stanu ROI (przycisk obok).")
else:
    alerts = compute_roi_alerts(analyzed, threshold, direction=direction)
    alert_mode_key = "roi"

alerts = mark_new_alerts(alerts, st.session_state.alert_prev_keys, mode=alert_mode_key)
st.session_state.alert_prev_keys = alert_row_keys(alerts, mode=alert_mode_key)

# --- Podsumowanie ---
st.subheader("Aktywne alerty")
total = len(analyzed.dropna(subset=["roi_pct"]))
n_alert = len(alerts) if alerts is not None else 0
n_new = int(alerts["is_new"].sum()) if alerts is not None and not alerts.empty and "is_new" in alerts.columns else 0

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Pozycje w portfelu", total)
with m2:
    st.metric("Powyżej progu", n_alert, delta=f"próg {threshold:g}%", delta_color="off")
with m3:
    st.metric("Nowe (ten cykl)", n_new)

if alerts is None or alerts.empty:
    st.success(f"Żadna pozycja nie przekroczyła progu {threshold:g}% (tryb: {mode}).")
else:
    display = alerts.copy()
    if "pnl" in display.columns:
        display["PnL"] = display["pnl"].map(lambda v: format_currency(v, currency) if pd.notna(v) else "—")
    display["ROI %"] = display["roi_pct"].map(lambda v: f"{v:+.2f}%" if pd.notna(v) else "—")
    if "roi_delta_pp" in display.columns:
        display["Zmiana ROI"] = display["roi_delta_pp"].map(
            lambda v: f"{v:+.2f} p.p." if pd.notna(v) else "—"
        )
    if "przekroczenie_pp" in display.columns:
        display["Powyżej progu"] = display["przekroczenie_pp"].map(
            lambda v: f"+{v:.2f} p.p." if pd.notna(v) else "—"
        )
    display["Status"] = display.apply(
        lambda r: "🆕 Nowy" if r.get("is_new") else "Aktywny",
        axis=1,
    )

    cols = ["Status", "ticker_xtb", "ticker_yahoo"]
    if "account_label" in display.columns:
        cols.append("account_label")
    cols.extend(
        c
        for c in (
            "alert_type",
            "ROI %",
            "Zmiana ROI",
            "Powyżej progu",
            "PnL",
            "market_price",
            "avg_price",
        )
        if c in display.columns
    )

    renamed = display[cols].rename(
        columns={
            "ticker_xtb": "Ticker",
            "ticker_yahoo": "Yahoo",
            "account_label": "Konto",
            "alert_type": "Typ",
            "market_price": "Cena rynk.",
            "avg_price": "Śr. cena",
        }
    )
    st.dataframe(renamed, use_container_width=True, hide_index=True)

    gains = alerts[alerts["roi_pct"] >= 0] if "roi_pct" in alerts.columns else pd.DataFrame()
    losses = alerts[alerts["roi_pct"] < 0] if "roi_pct" in alerts.columns else pd.DataFrame()
    if not gains.empty:
        st.caption(f"Zyski: {len(gains)} pozycji")
    if not losses.empty:
        st.caption(f"Straty: {len(losses)} pozycji")

st.divider()
st.subheader("Wszystkie pozycje (ROI)")
preview = analyzed.copy()
preview["ROI %"] = preview["roi_pct"].map(lambda v: f"{v:+.2f}%" if pd.notna(v) else "—")
preview["alert"] = preview["roi_pct"].map(
    lambda v: "⚠️" if pd.notna(v) and abs(float(v)) >= threshold else ""
)
show_cols = ["alert", "ticker_xtb", "ROI %"]
if "account_label" in preview.columns:
    show_cols.insert(2, "account_label")
st.dataframe(
    preview[show_cols].rename(columns={"ticker_xtb": "Ticker", "account_label": "Konto"}),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "ROI % = (wartość rynkowa − koszt pozycji) / koszt. Ceny z Yahoo; odśwież stronę lub włącz auto-odświeżanie."
)

st.divider()
st.subheader("Alerty cenowe")
st.caption("Powiadomi gdy cena instrumentu przekroczy zadany poziom (powyżej lub poniżej).")

price_alerts = load_price_alerts()

# Formularz dodawania
with st.expander("➕ Dodaj alert cenowy"):
    pa1, pa2, pa3, pa4 = st.columns([2, 2, 2, 2])
    with pa1:
        pa_ticker = st.selectbox(
            "Ticker",
            analyzed["ticker_xtb"].tolist(),
            key="pa_ticker_select",
        )
    with pa2:
        pa_direction = st.radio(
            "Kierunek",
            ["Powyżej ceny", "Poniżej ceny"],
            horizontal=True,
            key="pa_direction",
        )
    with pa3:
        if pa_ticker in analyzed["ticker_xtb"].values:
            raw_price = analyzed.loc[analyzed["ticker_xtb"] == pa_ticker, "market_price"].iloc[0]
            current_price = float(raw_price) if pd.notna(raw_price) else 0.0
        else:
            current_price = 0.0
        pa_target = st.number_input(
            "Cena docelowa",
            value=round(current_price * 1.1, 2),
            step=0.01,
            key="pa_target_price",
        )
    with pa4:
        pa_note = st.text_input("Notatka (opcjonalnie)", key="pa_note")

    if st.button("Dodaj alert", type="primary"):
        yahoo = analyzed.loc[analyzed["ticker_xtb"] == pa_ticker, "ticker_yahoo"].iloc[0]
        new_alert = PriceAlert(
            ticker_xtb=pa_ticker,
            ticker_yahoo=str(yahoo),
            direction="above" if "Powyżej" in pa_direction else "below",
            target_price=pa_target,
            note=pa_note,
        )
        price_alerts.append(new_alert)
        save_price_alerts(price_alerts)
        st.success(
            f"Alert dodany: {pa_ticker} {'>' if new_alert.direction == 'above' else '<'} {pa_target}"
        )
        st.rerun()

# Sprawdź wyzwolone
if price_alerts:
    triggered_df = check_price_alerts(price_alerts, analyzed)
    hit = triggered_df[triggered_df["wyzwolony"]] if not triggered_df.empty else pd.DataFrame()

    if not hit.empty:
        st.warning(f"🔔 {len(hit)} alert(y) cenowe wyzwolone!")
        st.dataframe(hit.drop(columns=["wyzwolony"]), use_container_width=True, hide_index=True)

    st.markdown(f"**Skonfigurowane alerty ({len(price_alerts)})**")
    if not triggered_df.empty:
        st.dataframe(
            triggered_df.rename(columns={"wyzwolony": "Wyzwolony"}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Brak aktualnych cen do sprawdzenia alertów.")

    # Usuwanie
    to_del = st.selectbox(
        "Usuń alert",
        range(len(price_alerts)),
        format_func=lambda i: (
            f"{price_alerts[i].ticker_xtb} "
            f"{'>' if price_alerts[i].direction == 'above' else '<'} "
            f"{price_alerts[i].target_price}"
        ),
        key="pa_delete_select",
    )
    if st.button("Usuń wybrany alert", type="secondary"):
        price_alerts.pop(to_del)
        save_price_alerts(price_alerts)
        st.rerun()
else:
    st.info("Brak skonfigurowanych alertów cenowych.")

if st.session_state.alert_auto_refresh:
    wait = int(st.session_state.alert_refresh_seconds)
    st.caption(f"Następne odświeżenie za {wait}s…")
    time.sleep(wait)
    st.rerun()
