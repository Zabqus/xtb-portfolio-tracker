"""
Podstrona: Słownik pojęć.

Krótkie wyjaśnienia wszystkich najważniejszych terminów używanych
w aplikacji – pogrupowane tematycznie, z wyszukiwarką.
Strona jest statyczna i nie wymaga wgranego raportu XTB.
"""

from __future__ import annotations

import streamlit as st

from ui.sidebar import render_import_sidebar
from ui.theme import inject_global_css

st.set_page_config(page_title="Słownik – XTB Tracker", page_icon="📖", layout="wide")

inject_global_css()
# Sidebar (upload + waluta) dla spójności; słownik działa bez raportu.
render_import_sidebar()

st.title("📖 Słownik pojęć")
st.caption(
    "Krótkie wyjaśnienia terminów używanych w aplikacji. "
    "Skorzystaj z wyszukiwarki lub przeglądaj według kategorii."
)

# ── Dane słownika: (kategoria, termin, definicja) ──────────────────────────
# Kolejność kategorii wyznacza kolejność zakładek.
TERMS: list[tuple[str, str, str]] = [
    # Podstawy portfela
    ("Podstawy portfela", "Pozycja otwarta",
     "Instrument (akcja/ETF), który nadal posiadasz. Jej wynik (PnL) jest "
     "*niezrealizowany* – zmienia się wraz z ceną rynkową."),
    ("Podstawy portfela", "Pozycja zamknięta",
     "Instrument, który już sprzedałeś. Wynik jest *zrealizowany* i nie zmienia się więcej."),
    ("Podstawy portfela", "Ilość / Wolumen",
     "Liczba posiadanych jednostek (akcji/udziałów ETF). XTB pozwala na ułamki, "
     "więc ilość może być ułamkowa."),
    ("Podstawy portfela", "Średnia cena (avg price)",
     "Średnia ważona cena, po której nabyłeś daną pozycję – uwzględnia wszystkie dokupienia. "
     "Podstawa do liczenia zysku/straty."),
    ("Podstawy portfela", "Cena rynkowa",
     "Aktualna cena instrumentu pobierana z Yahoo Finance (z cache'em ~1h). "
     "Mnożona przez ilość daje wartość rynkową."),
    ("Podstawy portfela", "Koszt pozycji",
     "Ile zainwestowałeś w pozycję: ilość × średnia cena (w walucie instrumentu, "
     "przeliczone na walutę wyświetlania)."),
    ("Podstawy portfela", "Wartość rynkowa",
     "Aktualna wartość pozycji: ilość × cena rynkowa. Suma po wszystkich pozycjach "
     "to całkowita wartość portfela."),

    # Zysk i zwroty
    ("Zysk i zwroty", "PnL (Profit and Loss)",
     "Zysk lub strata: wartość rynkowa − koszt. Dodatni = zysk, ujemny = strata."),
    ("Zysk i zwroty", "ROI %",
     "Return on Investment – procentowy zwrot z inwestycji: PnL / koszt × 100%. "
     "Pozwala porównać pozycje o różnej wielkości."),
    ("Zysk i zwroty", "PnL niezrealizowany",
     "Zysk/strata pozycji wciąż otwartej – „na papierze”. Zmienia się z ceną rynkową."),
    ("Zysk i zwroty", "PnL zrealizowany",
     "Zysk/strata z pozycji już sprzedanej – ostateczny, wpływa na podatek."),
    ("Zysk i zwroty", "Gross / Net PnL",
     "Gross = wynik przed prowizją; Net = po odjęciu prowizji i opłat. "
     "Net pokazuje, ile realnie zostało w kieszeni."),
    ("Zysk i zwroty", "Cost basis",
     "Baza kosztowa – historia średniej ceny zakupu w czasie. Pokazuje, jak Twoje "
     "dokupienia/sprzedaże zmieniały koszt jednostkowy pozycji."),
    ("Zysk i zwroty", "Round-trip",
     "Pełny cykl: otwarcie i zamknięcie pozycji (metodą FIFO). Na jego podstawie liczone "
     "są: czas trzymania, ROI i trafienie (win/loss)."),
    ("Zysk i zwroty", "Win rate",
     "Odsetek transakcji zakończonych zyskiem: liczba trafionych round-tripów / wszystkie × 100%."),
    ("Zysk i zwroty", "Holding period",
     "Czas trzymania pozycji – liczba dni między otwarciem a zamknięciem."),

    # Metryki ryzyka
    ("Metryki ryzyka", "Zmienność (volatility)",
     "Roczne odchylenie standardowe dziennych zwrotów (× √252). Im wyższa, tym mocniej "
     "waha się wartość portfela – większe ryzyko."),
    ("Metryki ryzyka", "Max Drawdown",
     "Największy spadek wartości portfela od szczytu do dołka. Pokazuje najgorszy "
     "scenariusz obsunięcia, jaki przeszedłeś."),
    ("Metryki ryzyka", "Sharpe Ratio",
     "Zwrot ponad stopę wolną od ryzyka podzielony przez zmienność. Mierzy zwrot na "
     "jednostkę ryzyka. > 1 = dobrze, > 2 = bardzo dobrze."),
    ("Metryki ryzyka", "Calmar Ratio",
     "Roczny zwrot podzielony przez |max drawdown|. Premiuje strategie, które zarabiają "
     "bez głębokich obsunięć."),
    ("Metryki ryzyka", "Korelacja",
     "Miara (−1 do +1) współzmienności dwóch instrumentów. Bliska +1 = poruszają się "
     "razem (słaba dywersyfikacja); bliska 0 = niezależne. Ostrzeżenie przy ≥ 0,9."),
    ("Metryki ryzyka", "Stopa wolna od ryzyka",
     "Hipotetyczny zwrot bez ryzyka (np. obligacje skarbowe). Punkt odniesienia w Sharpe Ratio."),
    ("Metryki ryzyka", "Annualizacja",
     "Przeliczenie wyniku na ujęcie roczne, by porównywać okresy różnej długości "
     "(np. zwrot z 3 miesięcy „rozciągnięty” na rok)."),

    # Analiza techniczna
    ("Analiza techniczna", "MA (średnia krocząca)",
     "Moving Average – średnia ceny z N ostatnich sesji, wygładza wykres. SMA = prosta, "
     "EMA = wykładnicza (większa waga świeższych cen)."),
    ("Analiza techniczna", "RSI",
     "Relative Strength Index (0–100). > 70 = wykupienie (możliwa korekta w dół), "
     "< 30 = wyprzedanie (możliwe odbicie)."),
    ("Analiza techniczna", "MACD",
     "Różnica dwóch EMA + linia sygnału. Przecięcia i histogram sygnalizują zmiany "
     "momentum / trendu."),
    ("Analiza techniczna", "Bollinger Bands",
     "Średnia krocząca i dwie wstęgi oddalone o odchylenie standardowe. Cena przy górnej "
     "wstędze = drogo, przy dolnej = tanio względem ostatniej zmienności."),
    ("Analiza techniczna", "Wolumen",
     "Liczba jednostek w obrocie w danej sesji. Wysoki wolumen potwierdza siłę ruchu ceny."),

    # Fundamenty i konsensus
    ("Fundamenty i konsensus", "P/E (cena/zysk)",
     "Price-to-Earnings – cena akcji / zysk na akcję. Ile płacisz za 1 jednostkę zysku. "
     "Wysokie = drogo lub duże oczekiwania wzrostu."),
    ("Fundamenty i konsensus", "Kapitalizacja rynkowa",
     "Market cap – wartość całej spółki: cena akcji × liczba akcji. Określa wielkość firmy "
     "(small/mid/large cap)."),
    ("Fundamenty i konsensus", "Dywidenda / stopa dywidendy",
     "Wypłata części zysku dla akcjonariuszy. Stopa dywidendy = dywidenda roczna / cena akcji."),
    ("Fundamenty i konsensus", "Cena docelowa (target price)",
     "Średnia prognoza ceny od analityków (targetMeanPrice). Orientacyjny poziom, dokąd "
     "ich zdaniem może dojść kurs."),
    ("Fundamenty i konsensus", "Upside %",
     "Potencjał wzrostu: (cena docelowa − cena bieżąca) / cena bieżąca × 100%. "
     "Dodatni = analitycy widzą przestrzeń do wzrostu."),
    ("Fundamenty i konsensus", "Rating / rekomendacja",
     "Zbiorcza ocena analityków (recommendationKey): strong buy / buy / hold / sell / strong sell."),
    ("Fundamenty i konsensus", "Liczba analityków",
     "Ilu analityków objęło spółkę (numberOfAnalystOpinions). Im więcej, tym wiarygodniejszy konsensus."),
    ("Fundamenty i konsensus", "Zakres 52 tygodni (52W)",
     "Najniższa i najwyższa cena z ostatniego roku. Pasek 52W pokazuje, gdzie obecna cena "
     "leży w tym zakresie."),
    ("Fundamenty i konsensus", "Benchmark",
     "Indeks odniesienia (np. S&P 500, WIG20). Porównanie pozycji/portfela z benchmarkiem "
     "mówi, czy radzisz sobie lepiej niż rynek."),
    ("Fundamenty i konsensus", "Timing score (percentyl wejścia)",
     "Percentyl ceny zakupu względem zakresu z ~3 miesięcy. Niski = kupiłeś relatywnie tanio, "
     "wysoki = blisko szczytu."),

    # Alokacja i dywersyfikacja
    ("Alokacja i dywersyfikacja", "Alokacja",
     "Podział portfela według kryteriów – udział procentowy każdej pozycji, sektora lub regionu."),
    ("Alokacja i dywersyfikacja", "Sektor",
     "Branża spółki (np. technologia, finanse, zdrowie) z Yahoo `.info`. Pokazuje, gdzie "
     "skupia się ryzyko branżowe."),
    ("Alokacja i dywersyfikacja", "Region / geografia",
     "Podział ekspozycji na rynki (USA / EU / PL) wg kraju notowania instrumentu."),
    ("Alokacja i dywersyfikacja", "Dywersyfikacja",
     "Rozłożenie kapitału na różne, słabo skorelowane aktywa, by ograniczyć ryzyko. "
     "Wysoka korelacja oznacza słabą dywersyfikację."),
    ("Alokacja i dywersyfikacja", "Ekspozycja",
     "Wielkość zaangażowania w dany instrument, sektor lub rynek – ile portfela na nim „wisi”."),

    # Waluty i podatki
    ("Waluty i podatki", "Waluta konta",
     "Waluta Twojego rachunku XTB (np. PLN lub EUR), wykrywana automatycznie z eksportu."),
    ("Waluty i podatki", "Waluta wyświetlania",
     "Waluta, na którą przeliczany jest cały majątek w aplikacji (PLN / EUR / USD / GBP). "
     "Nie zmienia konta – tylko prezentację."),
    ("Waluty i podatki", "Kurs FX",
     "Kurs wymiany walut (z Yahoo, cache ~1h) używany do przeliczeń między walutą "
     "instrumentu, konta i wyświetlania."),
    ("Waluty i podatki", "Podatek Belki (19%)",
     "Polski podatek 19% od zrealizowanych zysków kapitałowych i dywidend. Aplikacja podaje "
     "szacunek per rok podatkowy – orientacyjnie, nie jako porada podatkowa."),
    ("Waluty i podatki", "Multi-account",
     "Połączenie dwóch eksportów XTB (np. konto PLN + EUR) w jeden widok całego majątku."),

    # Stopy zwrotu i wartość w czasie
    ("Stopy zwrotu", "MWR (zwrot ważony przepływami)",
     "Money-Weighted Return – realna stopa zwrotu na Twoim kapitale, uwzględniająca "
     "kiedy i ile wpłacałeś/wypłacałeś. Duża wpłata tuż przed wzrostem podbija MWR."),
    ("Stopy zwrotu", "XIRR",
     "Metoda liczenia MWR dla nieregularnych przepływów – znajduje roczną stopę, przy "
     "której zdyskontowane wpłaty, wypłaty i bieżąca wartość konta sumują się do zera."),
    ("Stopy zwrotu", "TWR (zwrot ważony czasem)",
     "Time-Weighted Return – zwrot z samego doboru pozycji, bez wpływu momentu wpłat. "
     "Porównywalny z indeksami i funduszami. Przy regularnych dopłatach TWR ≠ MWR."),
    ("Stopy zwrotu", "Wpłaty netto",
     "Suma wpłat pomniejszona o wypłaty – kapitał własny realnie włożony w konto."),
    ("Stopy zwrotu", "Krzywa wzrostu (equity curve)",
     "Wykres skumulowanego zwrotu w czasie, rebazowany do 100 na starcie. Pokazuje, "
     "jak rosła wartość 1 jednostki zainwestowanej na początku okresu."),
    ("Stopy zwrotu", "Alpha",
     "Przewaga portfela nad benchmarkiem w punktach procentowych. Dodatnia = bijesz "
     "rynek, ujemna = przegrywasz z indeksem."),
    ("Stopy zwrotu", "Snapshot portfela",
     "Zapisany lokalnie (snapshots.json) stan portfela w danym dniu: wartość, koszt, "
     "PnL i pozycje. Buduje własny timeline wartości niezależny od Cash Operations."),

    # Sygnały
    ("Sygnały", "Sygnał kup / trzymaj / sprzedaj",
     "Syntetyczna ocena (skala 0–10) łącząca trzy źródła: analizę techniczną (40%), "
     "konsensus analityków (40%) i bieżący wynik P&L (20%). Heurystyka pomocnicza, "
     "nie rekomendacja inwestycyjna."),
    ("Sygnały", "Alert ROI",
     "Powiadomienie w aplikacji, gdy pozycja przekroczy ustawiony próg ±X% ROI "
     "(zysku lub straty)."),
]

CATEGORIES = list(dict.fromkeys(cat for cat, _, _ in TERMS))


def _render_term(term: str, definition: str) -> None:
    st.markdown(
        f"""
        <div style="
            background:#FFFFFF;
            border:1px solid #E2E8F0;
            border-left:4px solid #2563EB;
            border-radius:10px;
            padding:12px 16px;
            margin-bottom:10px;">
            <div style="font-weight:700;font-size:1.02rem;color:#0F172A;">{term}</div>
            <div style="color:#475569;font-size:0.92rem;margin-top:3px;">{definition}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


query = st.text_input(
    "🔎 Szukaj pojęcia",
    placeholder="np. ROI, Sharpe, dywidenda…",
    key="glossary_search",
).strip().lower()

if query:
    matches = [
        (cat, term, definition)
        for cat, term, definition in TERMS
        if query in term.lower() or query in definition.lower()
    ]
    st.caption(f"Znaleziono **{len(matches)}** pojęć dla „{query}”.")
    if not matches:
        st.info("Brak dopasowań. Spróbuj innego słowa kluczowego.")
    for cat, term, definition in matches:
        _render_term(f"{term}  ·  <span style='color:#94A3B8;font-weight:500'>{cat}</span>",
                     definition)
else:
    st.caption(f"**{len(TERMS)}** pojęć w **{len(CATEGORIES)}** kategoriach.")
    tabs = st.tabs(CATEGORIES)
    for tab, category in zip(tabs, CATEGORIES):
        with tab:
            for cat, term, definition in TERMS:
                if cat == category:
                    _render_term(term, definition)

st.divider()
st.caption(
    "ℹ️ Definicje mają charakter edukacyjny i upraszczają złożone pojęcia finansowe. "
    "Nie stanowią porady inwestycyjnej ani podatkowej."
)
