# XTB Portfolio Tracker

Lokalny dashboard (Streamlit) do analizy portfela akcji i ETF-ów z brokera XTB.
Po wgraniu eksportu Excel dostajesz KPI (TWR, MWR, Sharpe, alerty), PnL, ryzyko,
alokację, konsensusy analityków, stopy zwrotu i narzędzia podatkowe — wszystko offline
w przeglądarce, bez konta w chmurze.

## Struktura projektu

```
xtb_portfolio_tracker/
├── main.py                      # Dashboard KPI (sparklines)
├── uruchom.bat                  # Skrót Windows (lokalny, w .gitignore)
├── pages/
│   ├── 1_Portfolio.py           # Otwarte pozycje, ryzyko, eksport PDF/Excel
│   ├── 2_Pozycja.py             # Analiza tickera (wykres, fundamenty, timing)
│   ├── 3_Historia.py            # Timeline, trade analytics, Belka, dywidendy
│   ├── 4_Analiza.py             # Analiza techniczna (MA, RSI, MACD, BB)
│   ├── 5_Watchlist.py           # Tickery spoza portfela
│   ├── 6_Alokacja.py            # Sektor / region / FX + rebalancing
│   ├── 7_Alerty.py              # Progi ROI ±X% i alerty cenowe
│   ├── 8_Konsensusy_Sygnaly.py  # Ratingi analityków + sygnały kup/trzymaj/sprzedaj
│   ├── 9_Zwroty.py              # MWR/TWR, benchmarki, scenariusze, snapshoty
│   └── 10_Slownik.py            # Słownik pojęć (działa bez importu)
├── core/                        # Logika biznesowa i dane rynkowe
│   ├── importer.py / importer_maps.py
│   ├── analyzer.py, session.py, multi_account.py
│   ├── market_data.py, history.py, currencies.py, fundamentals.py
│   ├── returns.py, portfolio_benchmark.py, risk_metrics.py
│   ├── dashboard_kpis.py, concentration.py, pnl_breakdown.py
│   ├── fx_decomposition.py      # efekt ceny vs efekt FX
│   ├── performance_analytics.py, benchmark_risk.py, position_risk.py
│   ├── trade_analytics.py, trade_excursions.py, trade_tags.py
│   ├── analyst_consensus.py, consensus_snapshots.py
│   ├── signals.py, signal_snapshots.py, range_52w.py
│   ├── dividends.py, dividend_calendar.py, tax_harvest.py
│   ├── allocation.py, rebalance.py, alerts.py, watchlist.py
│   ├── snapshots.py, preferences.py
│   ├── technicals.py, timing_score.py, cost_basis.py
│   ├── timeline.py, transactions.py, closed_analysis.py
│   ├── pdf_report.py, excel_export.py
│   └── …
├── ui/                          # Wykresy Plotly, tabele, motyw, sidebar
│   ├── sidebar.py, theme.py, plotly_theme.py, formatters.py, tables.py
│   ├── kpi_dashboard.py, sparklines.py, portfolio_filters.py
│   ├── charts.py, chart_navigation.py, position_charts.py
│   ├── history_charts.py, analytics_charts.py, technical_charts.py
│   ├── returns_charts.py, risk_charts.py, pnl_charts.py, fx_charts.py
│   ├── allocation_charts.py, watchlist_charts.py
│   ├── consensus_charts.py, analyst_consensus.py
│   └── …
├── scripts/
│   └── ci_smoke.py              # Smoke test importów (CI)
├── assets/fonts/                # Czcionka PDF (pobierana przy pierwszym raporcie)
├── .streamlit/config.toml       # Motyw Streamlit
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11 / 3.12)
└── requirements.txt
```

Lokalne pliki użytkownika (w `.gitignore`): `watchlist.json`, `trade_tags.json`,
`user_preferences.json`, `price_alerts.json`, `snapshots.json`,
oraz opcjonalnie `consensus_snapshots.json` / `signal_snapshots.json`.

## Uruchomienie

Przy pierwszym uruchomieniu wykonaj kroki z [Pierwsza instalacja](#pierwsza-instalacja).

```powershell
cd ścieżka\do\xtb-portfolio-tracker
.\.venv\Scripts\python -m streamlit run main.py
```

Na Windows możesz też użyć lokalnego `uruchom.bat` (nie jest w repozytorium — utwórz go
sam albo skopiuj z dokumentacji poniżej).

Otwórz **http://localhost:8501** → wgraj eksport XTB w sidebarze → przeglądaj strony.

## Funkcje

### Start i dane

- **Dashboard KPI** – strona główna ze wallą metryk (TWR, MWR, Sharpe, drawdown, alerty) i sparkline’ami 30/90 dni
- **Multi-page** – dane w `st.session_state` (plik parsowany raz)
- **Waluta konta** – auto-wykrywanie PLN/EUR; wyświetlanie w PLN / EUR / USD / GBP (kursy Yahoo, cache 1h)
- **Multi-account** – dwa eksporty XTB (np. PLN + EUR) → jeden widok majątku
- **Motyw light/dark** – przełącznik w sidebarze, preferencja w `user_preferences.json`
- **Słownik** – wyszukiwarka pojęć; działa bez wgranego raportu

### Portfolio i ryzyko

- **Filtry globalne** – sektor, region, konto, zakres ROI (wykresy + tabela)
- **Wykresy** – pie/bar lub treemap; klik w ticker → strona Pozycja
- **Wodospad P&L** – niezrealizowany + zrealizowany + dywidendy − szacunek Belki
- **Dekompozycja FX** – PnL na efekt ceny vs efekt waluty (wodospad + per pozycja); kurs zakupu z analyzera lub Cash Operations
- **Koncentracja** – HHI, Top-5/Top-10, efektywna liczba pozycji
- **Mapa ryzyka pozycji** – waga × ROI × zmienność 90d
- **Metryki ryzyka** – volatility, max DD, Sharpe, Calmar, rolling risk, macierz korelacji (ostrzeżenie ≥ 0.9)
- **Eksport** – PDF (fpdf2 + kaleido) i Excel (openpyxl) ze strony Portfolio

### Pozycja i technika

- **Wykres ceny** 1Y / 3Y / 5Y, wolumen, vs benchmark (S&P 500 / WIG20)
- **Fundamenty** – P/E, kapitalizacja, zakres 52W, konsensus analityków
- **Timing wejścia** – percentyl ceny zakupu (3M)
- **Analiza techniczna** – MA, RSI, MACD, Bollinger (`pandas-ta` → TA-Lib → pandas)

### Historia i trading

- **Timeline** – wartość portfela day-by-day, drawdown, wpłaty vs wartość rynkowa
- **Trade analytics** – win rate, holding period, equity curve, rolling PF, heatmap P&L
- **MAE / MFE** – maksymalne odchylenie niekorzystne/korzystne w trakcie trzymania
- **Tagi round-tripów** – ręczne przyczyny wejścia/wyjścia (`trade_tags.json`)
- **Cost basis** – historia średniej ceny per ticker
- **Podatek Belki** – szacunek 19% per rok podatkowy + tax-loss harvesting
- **Dywidendy** – metryki, kalendarz ex-date, forward yield, projected cashflow, growth tracker

### Alokacja, watchlist, alerty

- **Alokacja** – sektor / region (USA / EU / PL) + ekspozycja walutowa (FX) + dekompozycja FX
- **Rebalancing** – docelowe udziały, dryf, sugestie dokupień i rozdział nowej gotówki
- **Watchlist** – symbole spoza portfela, zwroty 1M/3M/1Y vs średnia ważona portfela
- **Alerty ROI** – próg ±X% z auto-odświeżaniem
- **Alerty cenowe** – progi ceny (`price_alerts.json`)

### Konsensusy, sygnały, zwroty

- **Konsensusy** – targetMeanPrice, recommendationKey, upside %, pasek 52W; snapshoty w czasie
- **Sygnały** – heurystyka *kup / trzymaj / sprzedaj* (technika 40% + konsensus 40% + P&L 20%), zgoda interwałów, momentum, backtest
- **MWR / TWR** – stopa ważona przepływami (XIRR) i czasem; krótkie okresy (<90 dni) bez annualizacji
- **Portfel vs benchmark** – S&P 500 / MSCI World / NASDAQ 100 / WIG20; beta, tracking error, IR
- **Atrybucja i rolling returns** – wkład pozycji/sektorów, heatmapa rolling
- **Scenariusze** – stress test top pozycji + Monte Carlo (bootstrap)
- **Snapshoty portfela** – lokalny timeline wartości (`snapshots.json`), też dla importu CSV

### Eksport (Portfolio)

| Format | Zawartość |
|--------|-----------|
| **PDF** | Podsumowanie, wykresy PNG (kaleido), tabela pozycji |
| **Excel** | *Portfolio* (pozycje + KPI), *Historia* (timeline, transakcje, round-tripy), *Analiza* (trade stats, cost basis, alokacja) |

PDF: czcionka z `assets/fonts/` lub systemowa (Arial). Wymaga `fpdf2` i `kaleido`.

### Biblioteki techniczne (opcjonalne)

```powershell
# pandas-ta — wymaga Python 3.12+ (już w requirements.txt przy 3.12+)
.\.venv\Scripts\python -m pip install pandas-ta

# TA-Lib — najpierw natywna biblioteka C (Windows: wheel z https://github.com/cgohlke/talib-build/releases)
.\.venv\Scripts\python -m pip install TA-Lib
```

Kolejność silników w `core/technicals.py`: **pandas_ta** → **TA-Lib** → **pandas**.

## Eksport XTB

Natywny plik Excel z arkuszami:

- **Cash Operations** – otwarte pozycje (z historii zakupów/sprzedaży) oraz timeline / dywidendy
- **Closed Positions** – zamknięte transakcje

## Mapowanie tickerów

Edytuj `core/importer_maps.py` (np. `VWCE` → `VWCE.DE`, `XTB.PL` → `XTB.WA`).

## CI

Przy pushu / PR na `main` lub `master` GitHub Actions uruchamia:

1. `python -m compileall` (core, ui, pages, main.py)
2. `python -m scripts.ci_smoke` — import kluczowych modułów bez sieci i pliku XTB

Macierz: **Python 3.11** i **3.12** (`pandas-ta` tylko na 3.12+).

## Pierwsza instalacja

Wymagania: **Python 3.12+** zalecane (pełna analiza techniczna z `pandas-ta`);
**3.11** też działa (CI), bez `pandas-ta`. Folder `.venv` nie jest w repozytorium.

### 1. Pobierz projekt

```powershell
git clone https://github.com/Zabqus/xtb-portfolio-tracker.git
cd xtb-portfolio-tracker
```

### 2. Sprawdź wersję Pythona

```powershell
py --version
```

Jeśli `python` nie działa, a `py` tak — w kolejnych krokach używaj launchera `py`.

### 3. Utwórz środowisko wirtualne

```powershell
py -3.12 -m venv .venv
```

### 4. Zainstaluj zależności

W PowerShell ścieżka musi zaczynać się od `.\`:

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 5. Uruchom aplikację

```powershell
.\.venv\Scripts\python -m streamlit run main.py
```

Opcjonalny skrót Windows (`uruchom.bat` w katalogu projektu):

```bat
@echo off
cd /d "%~dp0"
.\.venv\Scripts\python -m streamlit run main.py
pause
```

### Problemy?

| Objaw | Rozwiązanie |
|-------|-------------|
| `Permission denied` przy `venv` | Usuń niepełny folder: `Remove-Item -Recurse -Force .venv`, zamknij inne terminale / procesy Pythona, spróbuj ponownie |
| Błąd o module `.venv` | Użyj `.\.venv\Scripts\python`, nie `.venv\Scripts\python` |
| `python` nie znaleziony | Użyj `py -3.12` zamiast `python` |
| Brak ceny Yahoo dla tickera | Dodaj mapowanie w `core/importer_maps.py` |
