# XTB Portfolio Tracker

Local Streamlit dashboard for analyzing stock and ETF portfolios from the XTB broker.
Upload an Excel export to get KPIs (TWR, MWR, Sharpe, alerts), PnL, risk,
allocation, analyst consensus, returns, and tax tools — all offline
in the browser, with no cloud account.

## Project structure

```
xtb_portfolio_tracker/
├── main.py                      # KPI dashboard (sparklines)
├── uruchom.bat                  # Windows shortcut (local, in .gitignore)
├── pages/
│   ├── 1_Portfolio.py           # Open positions, risk, PDF/Excel export
│   ├── 2_Pozycja.py             # Ticker analysis (chart, fundamentals, timing)
│   ├── 3_Historia.py            # Timeline, trade analytics, Belka tax, calendar
│   ├── 4_Analiza.py             # Technical analysis (MA, RSI, MACD, BB)
│   ├── 5_Watchlist.py           # Tickers outside the portfolio
│   ├── 6_Alokacja.py            # Sector / region / FX + rebalancing
│   ├── 7_Alerty.py              # ROI ±X% thresholds and price alerts
│   ├── 8_Konsensusy_Sygnaly.py  # Analyst ratings + buy/hold/sell signals
│   ├── 9_Zwroty.py              # MWR/TWR, benchmarks, scenarios, snapshots
│   ├── 10_Cele.py               # Portfolio value goals + FIRE / dividend snowball
│   └── 11_Slownik.py            # Glossary (works without an import)
├── core/                        # Business logic and market data
│   ├── importer.py / importer_maps.py
│   ├── analyzer.py, session.py, multi_account.py
│   ├── market_data.py, history.py, currencies.py, fundamentals.py
│   ├── returns.py, portfolio_benchmark.py, risk_metrics.py
│   ├── dashboard_kpis.py, concentration.py, pnl_breakdown.py
│   ├── fx_decomposition.py      # price effect vs FX effect
│   ├── performance_analytics.py, benchmark_risk.py, position_risk.py
│   ├── trade_analytics.py, trade_excursions.py, trade_tags.py
│   ├── analyst_consensus.py, consensus_snapshots.py
│   ├── signals.py, signal_snapshots.py, range_52w.py
│   ├── dividends.py, dividend_calendar.py, earnings_calendar.py
│   ├── tax_harvest.py, tax_loss_carry.py, belka_tax.py, nbp_fx.py, pit38_export.py
│   ├── ike_ikze.py
│   ├── allocation.py, rebalance.py, alerts.py, watchlist.py
│   ├── snapshots.py, preferences.py, goals.py
│   ├── technicals.py, timing_score.py, cost_basis.py
│   ├── timeline.py, transactions.py, closed_analysis.py
│   ├── pdf_report.py, excel_export.py
│   └── …
├── ui/                          # Plotly charts, tables, theme, sidebar
│   ├── sidebar.py, theme.py, plotly_theme.py, formatters.py, tables.py
│   ├── kpi_dashboard.py, sparklines.py, portfolio_filters.py
│   ├── charts.py, chart_navigation.py, position_charts.py
│   ├── history_charts.py, analytics_charts.py, technical_charts.py
│   ├── returns_charts.py, risk_charts.py, pnl_charts.py, fx_charts.py
│   ├── allocation_charts.py, watchlist_charts.py
│   ├── consensus_charts.py, analyst_consensus.py, goals_charts.py
│   ├── tax_charts.py            # IKE / IKZE vs taxable
│   └── …
├── scripts/
│   └── ci_smoke.py              # Import smoke test (CI)
├── assets/fonts/                # PDF font (downloaded on first report)
├── .streamlit/config.toml       # Streamlit theme
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11 / 3.12)
└── requirements.txt
```

Local user files (in `.gitignore`): `watchlist.json`, `trade_tags.json`,
`user_preferences.json`, `price_alerts.json`, `snapshots.json`,
`ticker_overrides.json`, `tax_loss_carry.json`,
and optionally `consensus_snapshots.json` / `signal_snapshots.json`.

## Running the app

On first run, follow the steps in [First-time setup](#first-time-setup).

```powershell
cd path\to\xtb-portfolio-tracker
.\.venv\Scripts\python -m streamlit run main.py
```

On Windows you can also use a local `uruchom.bat` (not in the repository — create it
yourself or copy it from the docs below).

Open **http://localhost:8501** → upload the XTB export in the sidebar → browse the pages.

## Features

### Getting started and data

- **KPI dashboard** – home page with a wall of metrics (TWR, MWR, Sharpe, drawdown, alerts) and 30/90-day sparklines
- **Multi-page** – data in `st.session_state` (file parsed once)
- **Account currency** – auto-detect PLN/EUR; display in PLN / EUR / USD / GBP (Yahoo FX rates, 1h cache)
- **Multi-account** – two XTB exports (e.g. PLN + EUR) → one net-worth view
- **Light/dark theme** – sidebar toggle, preference stored in `user_preferences.json`
- **Glossary** – concept search; works without an uploaded report

### Portfolio and risk

- **Global filters** – sector, region, account, ROI range (charts + table)
- **Charts** – pie/bar or treemap; click a ticker → Position page
- **P&L waterfall** – unrealized + realized + dividends − estimated Belka tax
- **FX decomposition** – PnL into price effect vs currency effect (waterfall + per position); purchase FX rate from the analyzer or Cash Operations
- **Concentration** – HHI, Top-5/Top-10, effective number of positions
- **Position risk map** – weight × ROI × 90d volatility
- **Risk metrics** – volatility, max DD, Sharpe, Calmar, rolling risk, correlation matrix (warning ≥ 0.9)
- **Export** – PDF (fpdf2 + kaleido) and Excel (openpyxl) from the Portfolio page

### Position and technicals

- **Price chart** 1Y / 3Y / 5Y, volume, vs benchmark (S&P 500 / WIG20)
- **Fundamentals** – P/E, market cap, 52W range, analyst consensus
- **Entry timing** – purchase price percentile (3M)
- **Technical analysis** – MA, RSI, MACD, Bollinger (`pandas-ta` → TA-Lib → pandas)

### History and trading

- **Timeline** – day-by-day portfolio value, drawdown, deposits vs market value
- **Trade analytics** – win rate, holding period, equity curve, rolling PF, P&L heatmap
- **MAE / MFE** – maximum adverse/favorable excursion while holding
- **Round-trip tags** – manual entry/exit reasons (`trade_tags.json`)
- **Cost basis** – average price history per ticker
- **Belka tax** – 19% estimate per tax year with **NBP FX**, **WHT credit** from Cash Operations,
  **loss carry-forward** ledger (5y / max 50%), tax-loss harvesting, **PIT-38 helper Excel**,
  and IKE/IKZE vs taxable comparison
- **Calendar** – dividends (metrics, ex-date, forward yield, cashflow, growth) + quarterly results (earnings: date, days to report, EPS estimate, 7/14-day highlight)

### Allocation, watchlist, alerts

- **Allocation** – sector / region (USA / EU / PL) + FX exposure + FX decomposition
- **Rebalancing** – target weights, drift, buy suggestions and new-cash allocation
- **Watchlist** – symbols outside the portfolio, 1M/3M/1Y returns vs portfolio weighted average
- **ROI alerts** – ±X% threshold with auto-refresh
- **Price alerts** – price thresholds (`price_alerts.json`)

### Consensus, signals, returns

- **Consensus** – targetMeanPrice, recommendationKey, upside %, 52W bar; snapshots over time
- **Signals** – *buy / hold / sell* heuristic (technicals 40% + consensus 40% + P&L 20%), timeframe agreement, momentum, backtest
- **MWR / TWR** – money-weighted (XIRR) and time-weighted returns; short periods (<90 days) without annualization
- **Portfolio vs benchmark** – S&P 500 / MSCI World / NASDAQ 100 / WIG20 / mWIG40 / WIG /
  bond proxy (TBSP / EU gov); beta, tracking error, IR
- **Ticker mapping UX** – expanded built-in map + sidebar overrides (`ticker_overrides.json`)
  when Yahoo has no price
- **Attribution and rolling returns** – position/sector contribution, rolling heatmap
- **Scenarios** – stress test of top positions + Monte Carlo (bootstrap)
- **Portfolio snapshots** – local value timeline (`snapshots.json`), also for CSV import
- **Goals and FIRE** – *Goals* page: time-to-goal projection (compound + contributions), FIRE number (4% rule), dividend expense coverage and “dividend snowball” chart

### Export (Portfolio)

| Format | Contents |
|--------|----------|
| **PDF** | Summary, PNG charts (kaleido), positions table |
| **Excel** | *Portfolio* (positions + KPI), *History* (timeline, transactions, round-trips), *Analysis* (trade stats, cost basis, allocation) |

PDF: font from `assets/fonts/` or system (Arial). Requires `fpdf2` and `kaleido`.

### Optional technical libraries

```powershell
# pandas-ta — requires Python 3.12+ (already in requirements.txt on 3.12+)
.\.venv\Scripts\python -m pip install pandas-ta

# TA-Lib — install the native C library first (Windows: wheel from https://github.com/cgohlke/talib-build/releases)
.\.venv\Scripts\python -m pip install TA-Lib
```

Engine order in `core/technicals.py`: **pandas_ta** → **TA-Lib** → **pandas**.

## XTB export

Native Excel file with sheets:

- **Cash Operations** – open positions (from buy/sell history) plus timeline / dividends
- **Closed Positions** – closed trades

## Ticker mapping

Built-in map in `core/importer_maps.py` (e.g. `VWCE` → `VWCE.DE`, `XTB.PL` → `XTB.WA`).
Missing Yahoo prices: use **Mapowanie tickerów** in the sidebar (writes `ticker_overrides.json`)
or edit the built-in map.

## CI

On push / PR to `main` or `master`, GitHub Actions runs:

1. `python -m compileall` (core, ui, pages, main.py)
2. `python -m pytest tests/` — unit tests (FIFO, Belka/WHT/carry, XIRR, ticker maps)
3. `python -m scripts.ci_smoke` — import key modules with no network and no XTB file

Matrix: **Python 3.11** and **3.12** (`pandas-ta` only on 3.12+).

## First-time setup

Requirements: **Python 3.12+** recommended (full technical analysis with `pandas-ta`);
**3.11** also works (CI), without `pandas-ta`. The `.venv` folder is not in the repository.

### 1. Clone the project

```powershell
git clone https://github.com/Zabqus/xtb-portfolio-tracker.git
cd xtb-portfolio-tracker
```

### 2. Check the Python version

```powershell
py --version
```

If `python` does not work but `py` does — use the `py` launcher in the next steps.

### 3. Create a virtual environment

```powershell
py -3.12 -m venv .venv
```

### 4. Install dependencies

In PowerShell the path must start with `.\`:

```powershell
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 5. Run the app

```powershell
.\.venv\Scripts\python -m streamlit run main.py
```

Optional Windows shortcut (`uruchom.bat` in the project directory):

```bat
@echo off
cd /d "%~dp0"
.\.venv\Scripts\python -m streamlit run main.py
pause
```

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Permission denied` on `venv` | Remove the incomplete folder: `Remove-Item -Recurse -Force .venv`, close other terminals / Python processes, try again |
| Error about a `.venv` module | Use `.\.venv\Scripts\python`, not `.venv\Scripts\python` |
| `python` not found | Use `py -3.12` instead of `python` |
| Missing Yahoo price for a ticker | Add a mapping in `core/importer_maps.py` |
