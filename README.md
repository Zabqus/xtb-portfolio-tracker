# XTB Portfolio Tracker

Lokalny dashboard (Streamlit) do monitorowania portfela akcji i ETF-ów z brokera XTB.

## Wymagania

- Python 3.10+
- JetBrains PyCharm (Community lub Professional)

## Uruchomienie w PyCharm – krok po kroku

### 1. Otwórz projekt

1. Uruchom **PyCharm**.
2. **File → Open** i wybierz folder `xtb_portfolio_tracker`.
3. Potwierdź otwarcie jako projekt.

### 2. Skonfiguruj interpreter (venv)

1. **File → Settings** (Windows/Linux) lub **PyCharm → Preferences** (macOS).
2. **Project: xtb_portfolio_tracker → Python Interpreter**.
3. Kliknij ikonę koła zębatego → **Add Interpreter → Add Local Interpreter**.
4. Wybierz **Existing** i wskaż interpreter z folderu `.venv` w projekcie  
   (np. `xtb_portfolio_tracker\.venv\Scripts\python.exe` na Windows).
5. Jeśli `.venv` nie istnieje: **New → Virtualenv**, lokalizacja w katalogu projektu, Python 3.10+.

### 3. Zainstaluj zależności

W terminalu PyCharm (**View → Tool Windows → Terminal**), upewnij się, że venv jest aktywny:

```bash
pip install -r requirements.txt
```

### 4. Uruchom aplikację

**Opcja A – terminal:**

```bash
streamlit run main.py
```

Przeglądarka otworzy się pod adresem `http://localhost:8501`.

**Opcja B – konfiguracja Run w PyCharm:**

1. **Run → Edit Configurations → + → Python**.
2. **Script path:** zostaw puste; w **Module name** wpisz: `streamlit`.
3. **Parameters:** `run main.py`.
4. **Working directory:** katalog główny projektu.
5. Uruchom zielonym przyciskiem **Run**.

### 5. Wgraj raport XTB

1. W panelu bocznym (**sidebar**) kliknij **Browse files**.
2. Wybierz **natywny eksport Excel z platformy XTB** (arkusze m.in. *Cash Operations*)
   **albo** uproszczony CSV/Excel z kolumnami: Ticker, Ilość, Średnia cena zakupu.
3. Dashboard wyliczy otwarte pozycje, pobierze ceny z Yahoo Finance i pokaże wykresy.

> **Uwaga:** eksport XTB zawiera numer konta – nie commituj go do publicznego repozytorium.

### Uruchomienie w Cursor (Windows, bez aktywacji venv)

```powershell
cd D:\xtb_portfolio_tracker
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run main.py
```

## Przykładowy plik testowy

W folderze `data/` znajduje się `przyklad_portfela.csv` do szybkiego testu.

## Struktura projektu

| Plik | Opis |
|------|------|
| `importer.py` | Parsowanie CSV/Excel, mapowanie tickerów XTB → Yahoo |
| `analizator.py` | Pobieranie cen (yfinance), ROI, zysk/strata |
| `main.py` | Interfejs Streamlit |
| `requirements.txt` | Zależności Python |

## Mapowanie tickerów

Tickery z XTB często wymagają sufiksu giełdy dla Yahoo (np. `VWCE` → `VWCE.DE`).  
Edytuj słownik `TICKER_MAP` w pliku `importer.py`.
