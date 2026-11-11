# Strażnik Płatności – wykrywanie oszustw w transakcjach kartowych

> „Zatrzymać oszustwo, nie zatrzymując klienta.”

Demo panelu analityka antyfraudowego. Model ocenia ryzyko oszustwa w każdej transakcji, proponuje decyzję
(przepuść / dodatkowa weryfikacja / blokada), wyjaśnia ją i pokazuje, ile kosztuje wybrany kompromis.

Ekrany: Progi i koszty, Porównanie metod, Transakcje, Sprawdź transakcję. Jak z nich korzystać:
[docs/tutorial.md](docs/tutorial.md). Wyniki modeli: [results/summary.md](results/summary.md).

## Uruchomienie

Najpierw pobierz z Kaggle zbiór [Credit Card Transactions Fraud Detection Dataset](https://www.kaggle.com/datasets/kartik2112/fraud-detection)
(wymaga konta) i wrzuć pliki `fraudTrain.csv` oraz `fraudTest.csv` do folderu `data/`.

**Docker:**

```bash
docker compose up --build
```

Pierwszy start uczy modele (ok. 1 minuty) i zapisuje je w `artifacts/`, potem aplikacja działa pod adresem
http://localhost:8501. Aby nauczyć modele od nowa (np. po aktualizacji kodu), usuń folder `artifacts/`.

**Lokalnie** (Python 3.12 i [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
uv run python train.py                 # uczy modele, zapisuje je do artifacts/
uv run python -m streamlit run app.py  # aplikacja
uv run python report.py                # opcjonalnie: odświeża results/
```

Windows ze Smart App Control: ustaw `UV_PYTHON_PREFERENCE=only-system`, żeby uv użył Pythona z python.org
zamiast pobierać własny (system blokuje jego niepodpisane pliki).

## Jak to działa

- **Dane:** syntetyczne transakcje z USA (generator Sparkov). Uczenie na danych z 01.2019–06.2020, test
  na późniejszych (06–12.2020). Kwoty przeliczone na zł kursem NBP (1 USD = 3,9247 zł).
- **Cechy:** kwota, godzina, kategoria sklepu i historia karty (kwota względem średniej, wydatki w 24 h,
  czas od poprzedniej transakcji). Bez imienia, adresu i zawodu; płeć i wiek tylko w wariancie porównawczym
  w raporcie.
- **Metody:** trzy proste reguły (punkt odniesienia), regresja logistyczna i XGBoost, który działa w aplikacji.
  Decyzje wyjaśniają wartości SHAP z XGBoost.
- **Koszty** (nasze założenia, `src/config.py`): przepuszczone oszustwo kosztuje tyle, ile jego kwota,
  weryfikacja 5 zł i zatrzymuje 90% oszustw, zablokowana uczciwa transakcja 100 zł.

## Struktura

```
app.py        nawigacja i progi wspólne dla ekranów
views/        cztery ekrany aplikacji
train.py      uczenie modeli (artifacts/)
report.py     tabele i wykresy wyników (results/)
src/          konfiguracja, cechy, reguły, ocena metod i kosztów, pomocnicze funkcje aplikacji
docs/         tutorial ze zrzutami ekranu
```
