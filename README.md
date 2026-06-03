# XTB Portfolio Tracker

Lokalny dashboard (Streamlit) do monitorowania portfela akcji i ETF-ów z brokera XTB.

## Struktura projektu

```
xtb_portfolio_tracker/
├── main.py                 # Strona główna
├── pages/
│   ├── 1_Portfolio.py      # Otwarte pozycje
│   ├── 2_Pozycja.py        # Analiza pojedynczego tickera
│   └── 3_Historia.py       # Timeline, zamknięte pozycje, transakcje
├── core/
│   ├── importer.py         # Parse XTB Excel/CSV
│   ├── importer_maps.py    # Ticker → Yahoo
│   ├── analyzer.py         # PnL, ROI, summaries
│   ├── history.py          # yfinance .history() 1Y/3Y/5Y
│   ├── fundamentals.py     # yfinance .info
│   ├── benchmark.py        # vs S&P 500 / WIG20
│   ├── timing_score.py     # percentyl ceny zakupu (3M)
│   ├── transactions.py     # parse Cash Operations trades
│   ├── timeline.py         # portfolio value day-by-day
│   └── closed_analysis.py  # best/worst closed trades
│   ├── currencies.py       # FX detection & conversion
│   ├── market_data.py      # Cached last prices
│   └── session.py          # st.session_state cache
├── ui/
│   ├── sidebar.py          # Upload + currency settings
│   ├── charts.py           # Portfolio Plotly charts
│   ├── position_charts.py  # Price/volume, benchmark, timing gauge
│   ├── formatters.py       # Currency / metric styling
│   └── tables.py           # DataFrames with Polish headers
└── requirements.txt
```

## Uruchomienie (Cursor / terminal)

```powershell
cd D:\xtb_portfolio_tracker
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run main.py
```

Otwórz **http://localhost:8501** → wgraj eksport XTB w sidebarze → **Portfolio**, **Pozycja** lub **Historia**.

## Funkcje

- **Multi-page** – dane w `st.session_state` (plik parsowany raz, nie przy każdym kliknięciu)
- **Waluta konta** – auto-wykrywanie PLN/EUR (konwersje w Cash Operations, tickery `.PL`)
- **Przeliczanie** – sumy w PLN / EUR / USD / GBP (kursy Yahoo, cache 1h)
- **Closed Positions** – arkusz z eksportu XTB, statystyki PnL i win rate
- **Cache cen** – `yfinance` przez `@st.cache_data` w `core/market_data.py`

## Eksport XTB

Natywny plik Excel z arkuszami:

- **Cash Operations** – otwarte pozycje (wyliczane z historii zakupów/sprzedaży)
- **Closed Positions** – zamknięte transakcje

> Nie commituj plików eksportu (`import_xtb.xlsx`, `pln_import.xlsx`) – zawierają numer konta.

## Mapowanie tickerów

Edytuj `core/importer_maps.py` (np. `VWCE` → `VWCE.DE`, `XTB.PL` → `XTB.WA`).
