"""Writes a summary of the results to results/: Markdown tables and two charts.

Run after train.py: uv run python report.py
"""

import json
from datetime import date

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb

from src.config import (
    DEFAULT_BLOCK_COST, DEFAULT_THRESHOLDS, DEFAULT_VERIFY_COST, DEFAULT_VERIFY_EFFICACY, META_PATH, MODEL_PATH,
    RESULTS_DIR, RISK_STEPS, SCORED_PATH, USD_PLN_SOURCE,
)
from src.evaluation import (
    BLOCK, PASS, VERIFY, Costs, alarm_curve, compare_at_rules_false_alarms, comparison_table, decide, evaluate,
    sensitive_variants_table,
)
from src.features import BASE_FEATURES, FEATURE_LABELS
from src.formatting import BLUE, INK, ORANGE, fmt_int, fmt_pct, fmt_pln, fmt_step
from src.rules import RULE_LABELS

MODELS = {"XGBoost": "score_xgb", "Regresja logistyczna": "score_lr"}
GRID = "#E1E0D9"


def md_table(df: pd.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def style(ax: plt.Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#C3C2B7")
    ax.tick_params(colors=INK)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def comparison_chart(df: pd.DataFrame, y: np.ndarray, false_alarms: int, rules_detected: float) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    for (label, column), color in zip(MODELS.items(), [BLUE, ORANGE]):
        curve = alarm_curve(y, df[column].to_numpy(), max_per_1000=15)
        ax.plot(curve["false_per_1000"], curve["detected"], color=color, linewidth=2, label=label)
    x = false_alarms / len(df) * 1000
    ax.scatter([x], [rules_detected], s=70, color=INK, zorder=3, label="Proste reguły")
    ax.annotate("Proste reguły", (x, rules_detected), xytext=(8, -14), textcoords="offset points", color=INK)
    ax.set_xlabel("Fałszywe blokady na 1000 transakcji", color=INK)
    ax.set_ylabel("Wykryte oszustwa", color=INK)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.legend(frameon=False, loc="lower right")
    style(ax)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "method_comparison.png")
    plt.close(fig)


def importance_chart(df: pd.DataFrame) -> pd.Series:
    """Mean absolute SHAP value per business feature on a random sample of test transactions."""
    sample = df.sample(20_000, random_state=42)
    booster = xgb.Booster(model_file=str(MODEL_PATH))
    contributions = booster.predict(xgb.DMatrix(sample[BASE_FEATURES].astype("float32")), pred_contribs=True)[:, :-1]
    importance = (
        pd.DataFrame(contributions, columns=BASE_FEATURES).T.groupby(FEATURE_LABELS).sum().T
        .abs().mean().sort_values()
    )
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    ax.barh(importance.index, importance.to_numpy(), height=0.5, color=BLUE)
    ax.set_xlabel("Średni wpływ na ocenę ryzyka (średnia |SHAP|)", color=INK)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.1f}".replace(".", ","))
    style(ax)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "feature_importance.png")
    plt.close(fig)
    return importance.sort_values(ascending=False)


def cheapest_thresholds(y: np.ndarray, amount: np.ndarray, scores: np.ndarray, costs: Costs) -> tuple[float, float, float]:
    """The cheapest pair of slider thresholds (in percent) under the given cost assumptions."""
    pairs = [(verify, block) for verify in RISK_STEPS for block in RISK_STEPS if verify <= block]
    cost = {
        pair: evaluate(y, amount, decide(scores, pair[0] / 100, pair[1] / 100), costs).cost_per_1000
        for pair in pairs
    }
    best = min(cost, key=cost.get)
    return best[0], best[1], cost[best]


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    df = pd.read_parquet(SCORED_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    y = df["is_fraud"].to_numpy(bool)
    amount = df["amount"].to_numpy()
    costs = Costs(DEFAULT_BLOCK_COST, DEFAULT_VERIFY_COST, DEFAULT_VERIFY_EFFICACY)

    false_alarms, comparison = compare_at_rules_false_alarms(df, MODELS, costs)
    rules_detected = comparison.loc[comparison["Metoda"] == "Proste reguły", "Wykryte oszustwa"].item()
    comparison_chart(df, y, false_alarms, rules_detected)
    importance = importance_chart(df)

    rules_table = pd.DataFrame({
        "Reguła": [*RULE_LABELS.values(), "Dowolna z powyższych"],
        "Wykryte oszustwa": [fmt_pct(np.sum(df[c].to_numpy() & y) / y.sum(), 1) for c in [*RULE_LABELS, "rules_any"]],
        "Zablokowane uczciwe transakcje": [fmt_int(np.sum(df[c].to_numpy() & ~y)) for c in [*RULE_LABELS, "rules_any"]],
    })

    scores = df["score_xgb"].to_numpy()
    verify_from, block_from = DEFAULT_THRESHOLDS
    panel = evaluate(y, amount, decide(scores, verify_from / 100, block_from / 100), costs)
    no_system = evaluate(y, amount, np.full(len(df), PASS), costs)
    rules = evaluate(y, amount, np.where(df["rules_any"], BLOCK, PASS), costs)
    best_verify, best_block, best_cost = cheapest_thresholds(y, amount, scores, costs)
    train, test = meta["train"], meta["test"]
    ap = {k: f"{v:.3f}".replace(".", ",") for k, v in meta["average_precision"].items()}

    report = f"""# Wyniki – Strażnik Płatności

Wygenerowane przez `report.py` ({date.today():%d.%m.%Y}). Wszystkie liczby dotyczą zbioru testowego,
którego modele nie widziały podczas nauki.

## Dane

- Zbiór: „Credit Card Transactions Fraud Detection Dataset” (Kaggle, autor kartik2112, dane syntetyczne
  z generatora Sparkov): https://www.kaggle.com/datasets/kartik2112/fraud-detection
- Uczenie: {fmt_int(train['rows'])} transakcji ({train['from']} – {train['to']}), w tym {fmt_int(train['fraud'])}
  oszustw ({fmt_pct(train['fraud'] / train['rows'], 2)}).
- Test: {fmt_int(test['rows'])} transakcji ({test['from']} – {test['to']}), w tym {fmt_int(test['fraud'])}
  oszustw ({fmt_pct(test['fraud'] / test['rows'], 2)}).
- Kwoty w zbiorze są w USD, przeliczamy je na zł: {USD_PLN_SOURCE}.
- Model, który przepuszcza wszystko, ma trafność (accuracy) {fmt_pct(1 - y.mean(), 1)} i nie łapie żadnego
  oszustwa. Dlatego patrzymy na wykryte oszustwa, fałszywe alarmy i koszt.

## Cechy modelu

Kwota, godzina (z pórą nocną 22:00–3:59), kategoria sklepu, kwota względem dotychczasowej średniej karty,
wydatki karty w ostatnich 24 h, czas od poprzedniej transakcji karty. Cechy historii karty liczymy tylko
z wcześniejszych transakcji. Nie używamy imienia, adresu, zawodu ani (w wariancie głównym) płci i wieku.
Odległość od domu do sklepu odrzuciliśmy: w tych danych ma taki sam rozkład dla oszustw i uczciwych transakcji.

Najważniejsze cechy według średniego wpływu na ocenę XGBoost (wykres: `feature_importance.png`):

{md_table(pd.DataFrame({
    "Cecha": importance.index,
    "Średni wpływ (SHAP)": [f"{v:.2f}".replace(".", ",") for v in importance],
}))}

## Proste reguły (punkt odniesienia)

{md_table(rules_table)}

Progi reguł to okrągłe kwoty dobrane na danych uczących.

## Porównanie metod przy tej samej liczbie blokad

Każda metoda blokuje {fmt_int(false_alarms)} uczciwych transakcji, tyle co proste reguły
(wykres: `method_comparison.png`). Koszt: przepuszczone oszustwa plus {fmt_pln(DEFAULT_BLOCK_COST)} za każdą
zablokowaną uczciwą transakcję.

{md_table(comparison_table(comparison))}

Jakość rankingu (average precision, 1 = idealnie): XGBoost {ap['score_xgb']},
regresja logistyczna {ap['score_lr']}, XGBoost z płcią i wiekiem {ap['score_xgb_sensitive']}.

## Płeć i wiek klienta

Odsetek wykrytych oszustw przy dwóch limitach fałszywych blokad (zablokowanych uczciwych transakcji):

{md_table(sensitive_variants_table(df, false_alarms))}

Płeć i wiek poprawiają wynik, najbardziej przy małej liczbie blokad. W aplikacji używamy wariantu bez nich,
bo decyzja o zablokowaniu karty nie powinna zależeć od płci ani wieku klienta.

## Panel kompromisu przy domyślnych założeniach

Założenia (nasze, nie dane rynkowe): blokada uczciwej transakcji {fmt_pln(DEFAULT_BLOCK_COST)},
jedna weryfikacja {fmt_pln(DEFAULT_VERIFY_COST)}, weryfikacja zatrzymuje {fmt_pct(DEFAULT_VERIFY_EFFICACY)} oszustw,
przepuszczone oszustwo kosztuje tyle, ile jego kwota.

| Wariant | Koszt na 1000 transakcji |
|---|---|
| Bez systemu | {fmt_pln(no_system.cost_per_1000)} |
| Proste reguły (blokada) | {fmt_pln(rules.cost_per_1000)} |
| XGBoost, weryfikacja od {fmt_step(verify_from)}, blokada od {fmt_step(block_from)} | {fmt_pln(panel.cost_per_1000)} |
| XGBoost, najtańsze progi na suwaku: weryfikacja od {fmt_step(best_verify)}, blokada od {fmt_step(best_block)} | {fmt_pln(best_cost)} |

Przy progach {fmt_step(verify_from)} / {fmt_step(block_from)}: wykryte oszustwa {fmt_pct(panel.detected_share, 1)},
zablokowane uczciwe transakcje {fmt_int(panel.honest[BLOCK])}, zweryfikowane uczciwe transakcje
{fmt_int(panel.honest[VERIFY])}.

## Zastrzeżenia

- Dane są syntetyczne. Generator tworzy wyraźne wzorce oszustw (noc, wysokie kwoty, seria transakcji
  w krótkim czasie), więc na prawdziwych danych wyniki byłyby prawdopodobnie niższe.
- Uczenie i test pochodzą z tego samego generatora; test jest późniejszy w czasie (jak w praktyce).
- Koszty i skuteczność weryfikacji to założenia. Najtańsze progi zmieniają się razem z nimi.
"""
    (RESULTS_DIR / "summary.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
