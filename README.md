# XTB Portfolio Tracker

Lokalny dashboard (Streamlit) do monitorowania portfela akcji i ETF-ów z brokera XTB.

## Struktura projektu

```
xtb_portfolio_tracker/
├── main.py                 # Strona główna
├── pages/
│   ├── 1_Portfolio.py      # Otwarte pozycje
│   ├── 2_Pozycja.py        # Analiza pojedynczego tickera
│   ├── 3_Historia.py       # Timeline, zamknięte pozycje, transakcje
│   ├── 4_Analiza.py        # Analiza techniczna (pandas_ta)
│   ├── 5_Watchlist.py      # Tickery spoza portfela, porównanie zwrotów
│   ├── 6_Alokacja.py       # Sektor i region (USA/EU/PL)
│   ├── 7_Alerty.py         # Progi ±X% ROI (alerty w aplikacji)
│   ├── 8_Konsensusy_Sygnaly.py  # Konsensusy analityków + sygnały kup/trzymaj/sprzedaj
│   ├── 9_Zwroty.py         # Stopy zwrotu (MWR/XIRR + TWR), portfel vs benchmark, snapshoty
│   └── 10_Slownik.py       # Słownik pojęć (statyczny, z wyszukiwarką)
├── core/
│   ├── importer.py         # Parse XTB Excel/CSV
│   ├── importer_maps.py    # Ticker → Yahoo
│   ├── analyzer.py         # PnL, ROI, summaries
│   ├── history.py          # yfinance .history() 1Y/3Y/5Y
│   ├── fundamentals.py     # yfinance .info (P/E, kapitalizacja, …)
│   ├── analyst_consensus.py  # targetMeanPrice, recommendationKey, …
│   ├── benchmark.py        # vs S&P 500 / WIG20
│   ├── timing_score.py     # percentyl ceny zakupu (3M)
│   ├── transactions.py     # parse Cash Operations trades
│   ├── timeline.py         # portfolio value day-by-day
│   ├── closed_analysis.py  # best/worst closed trades
│   ├── trade_analytics.py  # holding period, win rate, round-trips
│   ├── cost_basis.py       # avg price history per ticker
│   └── technicals.py       # MA, RSI, MACD, Bollinger (pandas_ta / TA-Lib / pandas)
│   ├── currencies.py       # FX detection & conversion
│   ├── market_data.py      # Cached last prices
│   ├── watchlist.py        # watchlist.json, zwroty, vs portfel
│   ├── allocation.py       # sektor / region z yfinance .info
│   ├── pdf_report.py       # miesięczny raport PDF (fpdf2 + kaleido)
│   ├── excel_export.py     # eksport .xlsx (Portfolio / Historia / Analiza)
│   ├── multi_account.py    # merge PLN + EUR (multi-account)
│   ├── alerts.py           # progi ROI ±X%
│   ├── signals.py          # heurystyka sygnałów (technika + konsensus + P&L)
│   ├── risk_metrics.py     # volatility, max DD, Sharpe, Calmar, korelacje
│   ├── dividends.py        # parsowanie i agregacja dywidend z Cash Operations
│   ├── returns.py          # MWR/XIRR + TWR (stopy zwrotu ważone przepływami/czasem)
│   ├── portfolio_benchmark.py  # indeks TWR portfela vs S&P 500 / MSCI World / …
│   ├── snapshots.py        # lokalne snapshoty portfela (snapshots.json)
│   ├── tax_harvest.py      # tax-loss harvesting (podatek Belki 19%)
│   ├── dividend_calendar.py # forward yield + ex-date otwartych pozycji
│   ├── rebalance.py        # sugestie dokupień do docelowej alokacji
│   └── session.py          # st.session_state cache
├── ui/
│   ├── sidebar.py          # Upload + currency settings
│   ├── theme.py            # Globalny motyw / CSS (karty metryk, responsywność)
│   ├── charts.py           # Portfolio Plotly charts
│   ├── position_charts.py  # Price/volume, benchmark, timing gauge
│   ├── formatters.py       # Currency / metric styling
│   ├── tables.py           # DataFrames with Polish headers
│   ├── watchlist_charts.py # Wykresy watchlisty
│   ├── allocation_charts.py # Wykresy alokacji
│   ├── returns_charts.py   # Krzywa TWR, portfel vs benchmark, snapshoty
│   └── risk_charts.py      # Heatmapa korelacji portfela
└── requirements.txt
```

## Uruchomienie (Cursor / terminal)

Przy pierwszym uruchomieniu najpierw wykonaj kroki z sekcji [Pierwsza instalacja](#pierwsza-instalacja) poniżej.

```powershell
cd ścieżka\do\xtb_tracker
.\.venv\Scripts\python -m streamlit run main.py
```

Otwórz **http://localhost:8501** → wgraj eksport XTB w sidebarze → **Portfolio**, **Pozycja** lub **Historia**.

## Funkcje

- **Multi-page** – dane w `st.session_state` (plik parsowany raz, nie przy każdym kliknięciu)
- **Waluta konta** – auto-wykrywanie PLN/EUR (konwersje w Cash Operations, tickery `.PL`)
- **Przeliczanie** – sumy w PLN / EUR / USD / GBP (kursy Yahoo, cache 1h)
- **Closed Positions** – arkusz z eksportu XTB, statystyki PnL i win rate
- **Cache cen** – `yfinance` przez `@st.cache_data` w `core/market_data.py`
- **Konsensus analityków** – `targetMeanPrice`, `recommendationKey`, `numberOfAnalystOpinions` (zakładka *Fundamenty* na stronie Pozycja)
- **Analiza techniczna** – `pandas-ta` (Python 3.12+) lub opcjonalnie **TA-Lib**, w przeciwnym razie fallback w pandas
- **Watchlist** – symbole spoza otwartego portfela, zwroty 1M/3M/1Y i porównanie ze średnią ważoną portfela (`watchlist.json` lokalnie)
- **Alokacja** – wykresy sektorowe i geograficzne (USA / EU / PL) z `sector` i `country` w Yahoo `.info`
- **Raport PDF** – miesięczny eksport z Portfolio: podsumowanie, wykresy Plotly→PNG (`kaleido`), tabela pozycji (`fpdf2`)
- **Eksport Excel** – sformatowany `.xlsx` z arkuszami Portfolio / Historia / Analiza (`openpyxl`)
- **Multi-account** – dwa eksporty XTB (np. PLN + EUR), merge i jeden widok całego majątku
- **Alerty** – zakładka z listą pozycji powyżej progu ±X% ROI; auto-odświeżanie (`st.rerun()`)
- **Konsensusy i sygnały** – strona z tabelą celów/ratingów analityków (upside %, P/E, pasek 52W) oraz syntetycznym sygnałem *kup / trzymaj / sprzedaj* (technika 40% + konsensus 40% + P&L 20%, skala 0–10)
- **Podatek Belki** – zakładka *Historia* z szacunkiem podatku 19% od zrealizowanych zysków/strat i dywidend per rok podatkowy (z disclaimerem)
- **Dywidendy** – zakładka *Historia*: metryki, bar chart per rok, wykres kumulatywny, podsumowanie per ticker
- **Metryki ryzyka** – na stronie *Portfolio*: volatility, max drawdown, Sharpe, Calmar, najlepszy/najgorszy dzień + macierz korelacji pozycji (ostrzeżenie przy korelacji ≥ 0.9)
- **Wpłaty vs wartość** – wykres warstwowy na *Timeline* porównujący skumulowane wpłaty z wartością rynkową portfela
- **Zwroty (MWR/TWR)** – zakładka *Zwroty*: stopa zwrotu ważona przepływami (MWR/XIRR, uwzględnia timing wpłat) i ważona czasem (TWR, porównywalna z indeksami); krótkie okresy (<90 dni) nie są annualizowane
- **Portfel vs benchmark** – krzywa indeksu TWR portfela zestawiona z S&P 500 / MSCI World / NASDAQ 100 / WIG20 (alpha w punktach proc.)
- **Snapshoty portfela** – lokalny zapis wartości/kosztu/PnL na dziś do `snapshots.json`; własny timeline niezależny od Cash Operations (działa też dla importu CSV)
- **Tax-loss harvesting** – zakładka *Historia → Podatek Belki*: ranking otwartych pozycji ze stratą, tarcza podatkowa (19%) i strata do przeniesienia na kolejne lata
- **Kalendarz dywidend** – zakładka *Historia → Dywidendy*: forward yield, najbliższe ex-date i szacowany roczny przychód z dywidend otwartych pozycji
- **Rebalancing helper** – zakładka *Alokacja*: docelowe udziały sektor/region vs obecne, dryf, sugerowane dokupienia/redukcje oraz rozdział nowej gotówki
- **Ekspozycja walutowa** – zakładka *Alokacja*: rozbicie wg waluty notowań instrumentu (ryzyko FX), z dodatkowym podziałem per konto przy multi-account
- **Słownik** – zakładka z wyszukiwarką i krótkimi wyjaśnieniami wszystkich pojęć używanych w aplikacji (pogrupowane tematycznie)
- **Motyw wizualny** – wspólny `.streamlit/config.toml` + `ui/theme.py` (karty metryk, spójne nagłówki, responsywność na wąskich ekranach)

### Eksport (Portfolio)

| Format | Zawartość |
|--------|-----------|
| **PDF** | Podsumowanie, wykresy PNG (kaleido), tabela pozycji |
| **Excel** | Arkusz *Portfolio* (pozycje + KPI), *Historia* (timeline, transakcje, round-tripy, zamknięte), *Analiza* (trade stats, cost basis, alokacja) |

PDF: czcionka z `assets/fonts/` lub systemowa (Arial). Wymaga `fpdf2` i `kaleido` (w `requirements.txt`).

### Biblioteki techniczne (opcjonalne)

```powershell
# pandas-ta — wymaga Python 3.12+
.\.venv\Scripts\python -m pip install pandas-ta

# TA-Lib — najpierw natywna biblioteka C (Windows: np. wheel z https://github.com/cgohlke/talib-build/releases)
# potem:
.\.venv\Scripts\python -m pip install TA-Lib
```

Kolejność silników w `core/technicals.py`: **pandas_ta** → **TA-Lib** → **pandas**.

## Eksport XTB

Natywny plik Excel z arkuszami:

- **Cash Operations** – otwarte pozycje (wyliczane z historii zakupów/sprzedaży)
- **Closed Positions** – zamknięte transakcje

## Mapowanie tickerów

Edytuj `core/importer_maps.py` (np. `VWCE` → `VWCE.DE`, `XTB.PL` → `XTB.WA`).

## Pierwsza instalacja

Wymagania: **Python 3.12+** (m.in. dla `pandas-ta`). Folder `.venv` nie jest w repozytorium — po `git clone` trzeba go utworzyć lokalnie.

### 1. Pobierz projekt i wejdź do katalogu

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

W PowerShell ścieżka musi zaczynać się od `.\` — inaczej pojawi się błąd *„The module '.venv' could not be loaded”*:

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 5. Uruchom aplikację

```powershell
.\.venv\Scripts\python -m streamlit run main.py
```

### Problemy?

| Objaw | Rozwiązanie |
|-------|-------------|
| `Permission denied` przy `venv` | Usuń niepełny folder: `Remove-Item -Recurse -Force .venv`, zamknij inne terminale / procesy Pythona, spróbuj ponownie |
| Błąd o module `.venv` | Użyj `.\.venv\Scripts\python`, nie `.venv\Scripts\python` |
| `python` nie znaleziony | Użyj `py -3.12` zamiast `python` |
