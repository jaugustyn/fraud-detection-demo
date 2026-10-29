# Wyniki – Strażnik Płatności

Wygenerowane przez `report.py` (29.10.2026). Wszystkie liczby dotyczą zbioru testowego,
którego modele nie widziały podczas nauki.

## Dane

- Zbiór: „Credit Card Transactions Fraud Detection Dataset” (Kaggle, autor kartik2112, dane syntetyczne
  z generatora Sparkov): https://www.kaggle.com/datasets/kartik2112/fraud-detection
- Uczenie: 1 296 675 transakcji (01.01.2019 – 21.06.2020),
  w tym 7 506 oszustw (0,58%).
- Test: 555 719 transakcji (21.06.2020 – 31.12.2020),
  w tym 2 145 oszustw (0,39%).
- Kwoty w zbiorze są w USD, przeliczamy je na zł: kurs średni NBP z 23.10.2026 (tabela 207/A/NBP/2026): 1 USD = 3,9247 zł.
- Model, który przepuszcza wszystko, ma trafność (accuracy) 99,6% i nie łapie żadnego
  oszustwa. Dlatego patrzymy na wykryte oszustwa, fałszywe alarmy i koszt.

## Cechy modelu

Kwota, godzina (z pórą nocną 22:00–3:59), kategoria sklepu, kwota względem dotychczasowej średniej karty,
wydatki karty w ostatnich 24 h, czas od poprzedniej transakcji karty. Cechy historii karty liczymy tylko
z wcześniejszych transakcji. Nie używamy imienia, adresu, zawodu ani (w wariancie głównym) płci i wieku.
Odległość od domu do sklepu odrzuciliśmy: w tych danych ma taki sam rozkład dla oszustw i uczciwych transakcji.

Najważniejsze cechy według średniego wpływu na ocenę XGBoost (wykres: `feature_importance.png`):

| Cecha | Średni wpływ (SHAP) |
|---|---|
| Kwota | 3,65 |
| Wydatki karty w ostatnich 24 h | 1,40 |
| Kategoria sklepu | 0,98 |
| Godzina | 0,82 |
| Kwota względem zwykłych wydatków karty | 0,60 |
| Czas od poprzedniej transakcji karty | 0,48 |

## Proste reguły (punkt odniesienia)

| Reguła | Wykryte oszustwa | Zablokowane uczciwe transakcje |
|---|---|---|
| Kwota powyżej 3 000 zł | 40,2% | 2 058 |
| Transakcja nocna (22:00–3:59) powyżej 1 200 zł | 54,1% | 2 344 |
| Zakupy lub inne płatności online powyżej 2 800 zł | 34,2% | 924 |
| Dowolna z powyższych | 60,7% | 4 013 |

Progi reguł to okrągłe kwoty dobrane na danych uczących.

## Porównanie metod przy tej samej liczbie blokad

Każda metoda blokuje 4 013 uczciwych transakcji, tyle co proste reguły
(wykres: `method_comparison.png`). Koszt: przepuszczone oszustwa plus 100 zł za każdą
zablokowaną uczciwą transakcję.

| Metoda | Wykryte oszustwa | Trafne alarmy (precyzja) | Koszt na 1000 transakcji |
|---|---|---|---|
| Proste reguły | 60,7% | 24,5% | 1 486 zł |
| XGBoost | 97,6% | 34,3% | 803 zł |
| Regresja logistyczna | 66,2% | 26,1% | 1 740 zł |

Jakość rankingu (average precision, 1 = idealnie): XGBoost 0,935,
regresja logistyczna 0,547, XGBoost z płcią i wiekiem 0,959.

## Płeć i wiek klienta

Odsetek wykrytych oszustw przy dwóch limitach fałszywych blokad (zablokowanych uczciwych transakcji):

| Wariant XGBoost | Limit 4 013 blokad (jak reguły) | Limit 556 blokad (1 na 1000) |
|---|---|---|
| Bez płci i wieku (używany w aplikacji) | 97,6% | 90,6% |
| Z płcią i wiekiem | 98,0% | 94,9% |

Płeć i wiek poprawiają wynik, najbardziej przy małej liczbie blokad. W aplikacji używamy wariantu bez nich,
bo decyzja o zablokowaniu karty nie powinna zależeć od płci ani wieku klienta.

## Panel kompromisu przy domyślnych założeniach

Wykres: `cost_comparison.png`. Założenia (nasze, nie dane rynkowe): blokada uczciwej transakcji 100 zł,
jedna weryfikacja 5 zł, weryfikacja zatrzymuje 90% oszustw,
przepuszczone oszustwo kosztuje tyle, ile jego kwota.

| Wariant | Koszt na 1000 transakcji |
|---|---|
| Bez systemu | 8 004 zł |
| Proste reguły (blokada) | 1 486 zł |
| XGBoost, weryfikacja od 10%, blokada od 50% | 415 zł |
| XGBoost, najtańsze progi na suwaku: weryfikacja od 0,5%, blokada od 50% | 219 zł |

Przy progach 10% / 50%: wykryte oszustwa 93,2%,
zablokowane uczciwe transakcje 199, zweryfikowane uczciwe transakcje
747.

## Zastrzeżenia

- Dane są syntetyczne. Generator tworzy wyraźne wzorce oszustw (noc, wysokie kwoty, seria transakcji
  w krótkim czasie), więc na prawdziwych danych wyniki byłyby prawdopodobnie niższe.
- Uczenie i test pochodzą z tego samego generatora; test jest późniejszy w czasie (jak w praktyce).
- Model zna tylko sytuacje z danych uczących. Największe oszustwo w nich to 5 401 zł, więc wyższych
  kwot model nie uznaje za bardziej podejrzane. Przykład (zakupy spożywcze w sklepie o 23:00, wydatki karty
  w ostatnich 24 h 4 000 zł): przy 1 500 zł ryzyko wynosi 100,0%,
  a przy 20 000 zł tylko 80,7%.
- Koszty i skuteczność weryfikacji to założenia. Najtańsze progi zmieniają się razem z nimi.
