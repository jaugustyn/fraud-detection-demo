# Strażnik Płatności – wykrywanie oszustw w transakcjach kartowych

Demo panelu analityka antyfraudowego: model ocenia ryzyko każdej transakcji, proponuje decyzję (przepuść / dodatkowa weryfikacja / blokada),
wyjaśnia ją i pokazuje koszt kompromisu w złotówkach.

> „Zatrzymać oszustwo, nie zatrzymując klienta.”

## Ekrany

- **Panel kompromisu** – suwak z dwoma progami ryzyka. Na żywo widać, ile oszustw wykrywamy, ile uczciwych
  transakcji blokujemy (fałszywe blokady) lub weryfikujemy i ile to kosztuje na 1000 transakcji.
- **Porównanie metod** – proste reguły vs regresja logistyczna vs XGBoost przy tej samej liczbie
  fałszywych blokad oraz wariant modelu z płcią i wiekiem klienta.
- **Transakcje** – transakcje z wybranego dnia z proponowaną decyzją. Po zaznaczeniu: które cechy podniosły
  lub obniżyły ryzyko (wartości SHAP z XGBoost).
- **Sprawdź transakcję** – ręcznie wpisana transakcja (kwota, godzina, kategoria, historia karty):
  ryzyko, decyzja i wyjaśnienie.

Jak korzystać z aplikacji, krok po kroku: [docs/tutorial.md](docs/tutorial.md).

Podsumowanie wyników (tabele i wykresy): [results/summary.md](results/summary.md).

## Dane

Syntetyczny zbiór [Credit Card Transactions Fraud Detection Dataset](https://www.kaggle.com/datasets/kartik2112/fraud-detection)
(Kaggle, autor kartik2112, generator Sparkov). Pobierz go ręcznie (wymaga konta na Kaggle) i wrzuć pliki
`fraudTrain.csv` oraz `fraudTest.csv` do folderu `data/`. Dane nie trafiają do repozytorium.

## Uruchomienie w Dockerze (najprościej)

```bash
docker compose up --build
```

Przy pierwszym starcie kontener uczy modele (ok. 1 minuty), potem uruchamia aplikację:
http://localhost:8501. Wytrenowane modele lądują w `artifacts/`, więc kolejne starty są natychmiastowe.
Aby nauczyć modele od nowa, usuń folder `artifacts/`.

## Uruchomienie lokalne

Wymagania: Python 3.12 i [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python train.py      # uczy modele, zapisuje wyniki do artifacts/
uv run streamlit run app.py # aplikacja
uv run python report.py     # opcjonalnie: odświeża tabele i wykresy w results/
```

Windows ze Smart App Control: ustaw `UV_PYTHON_PREFERENCE=only-system`, żeby uv używał Pythona z python.org
zamiast pobierać własny (system blokuje jego niepodpisane pliki).

## Jak to działa

- **Podział danych:** uczymy na `fraudTrain.csv` (01.2019 – 06.2020), oceniamy na `fraudTest.csv`
  (06.2020 – 12.2020). Test jest późniejszy w czasie, jak w praktyce.
- **Cechy:** kwota, godzina, kategoria sklepu oraz historia karty: kwota względem dotychczasowej średniej,
  wydatki w ostatnich 24 h, czas od poprzedniej transakcji (liczone tylko z wcześniejszych transakcji).
  Nie używamy imienia, adresu ani zawodu. Płeć i wiek są tylko w wariancie porównawczym.
- **Metody:** trzy proste reguły (punkt odniesienia), regresja logistyczna, XGBoost.
- **Waluta:** kwoty w zbiorze są w USD, przeliczamy je na zł kursem średnim NBP z 23.10.2026 (3,9247 zł).
- **Model kosztów** (założenia do zmiany w aplikacji, nie dane rynkowe):
  - przepuszczone oszustwo kosztuje tyle, ile jego kwota,
  - weryfikacja kosztuje 5 zł i zatrzymuje 90% oszustw,
  - blokada zatrzymuje każde oszustwo, ale zablokowana uczciwa transakcja kosztuje 100 zł.

## Struktura

```
app.py              aplikacja Streamlit: panel boczny z progami i nawigacja
views/              cztery ekrany aplikacji
train.py            uczenie modeli i zapis wyników do artifacts/
report.py           podsumowanie wyników: tabele i wykresy (results/)
results/            summary.md i wykresy
docs/               tutorial ze zrzutami ekranu
src/
  config.py         ścieżki, kurs NBP, domyślne założenia kosztowe
  features.py       wczytanie danych i cechy
  rules.py          proste reguły
  evaluation.py     decyzje, model kosztów, porównanie metod
  app_data.py       wczytywanie wyników w aplikacji i wyjaśnienia decyzji
  formatting.py     formatowanie liczb i kolory wykresów
```
