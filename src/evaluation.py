"""Decisions, costs and method comparison, shared by the app and the report."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.config import BLOCK_COST, VERIFY_COST, VERIFY_EFFICACY
from src.formatting import fmt_pct, fmt_pln

PASS, VERIFY, BLOCK = 0, 1, 2
DECISION_LABELS = {PASS: "Przepuść", VERIFY: "Dodatkowa weryfikacja", BLOCK: "Blokada"}

MODELS = {"XGBoost": "score_xgb", "Regresja logistyczna": "score_lr"}  # label -> score column


@dataclass(frozen=True)
class Outcome:
    fraud: dict[int, int]  # decision -> number of fraudulent transactions
    honest: dict[int, int]  # decision -> number of honest transactions
    cost: dict[int, float]  # decision -> cost in PLN
    n: int

    @property
    def cost_per_1000(self) -> float:
        return sum(self.cost.values()) / self.n * 1000

    @property
    def detected(self) -> int:
        return self.fraud[VERIFY] + self.fraud[BLOCK]

    @property
    def detected_share(self) -> float:
        return self.detected / sum(self.fraud.values())

    @property
    def precision(self) -> float:
        return self.detected / (self.detected + self.honest[VERIFY] + self.honest[BLOCK])


def decide(scores: np.ndarray, verify_from: float, block_from: float) -> np.ndarray:
    return np.select([scores >= block_from, scores >= verify_from], [BLOCK, VERIFY], PASS)


def evaluate(y: np.ndarray, amount: np.ndarray, decisions: np.ndarray) -> Outcome:
    """Cost model: a passed fraud loses its amount, verification stops VERIFY_EFFICACY of fraud
    and costs a fixed fee, blocking stops all fraud but costs a fee per honest transaction."""
    fraud = {d: int(np.sum(y & (decisions == d))) for d in DECISION_LABELS}
    honest = {d: int(np.sum(~y & (decisions == d))) for d in DECISION_LABELS}
    cost = {
        PASS: float(amount[y & (decisions == PASS)].sum()),
        VERIFY: float(
            (1 - VERIFY_EFFICACY) * amount[y & (decisions == VERIFY)].sum()
            + VERIFY_COST * np.sum(decisions == VERIFY)
        ),
        BLOCK: BLOCK_COST * honest[BLOCK],
    }
    return Outcome(fraud, honest, cost, len(y))


def flag_at_false_alarms(y: np.ndarray, scores: np.ndarray, false_alarms: int) -> np.ndarray:
    """Flags the riskiest transactions so that at most `false_alarms` honest ones are flagged."""
    honest_desc = np.sort(scores[~y])[::-1]
    return scores > honest_desc[false_alarms]


def compare_at_rules_false_alarms(df: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    """Each model blocks as many honest transactions as the simple rules do; who catches more fraud?"""
    y = df["is_fraud"].to_numpy(bool)
    amount = df["amount"].to_numpy()
    rules = df["rules_any"].to_numpy(bool)
    false_alarms = int(np.sum(rules & ~y))

    flagged = {"Proste reguły": rules}
    for label, column in MODELS.items():
        flagged[label] = flag_at_false_alarms(y, df[column].to_numpy(), false_alarms)

    rows = []
    for label, flags in flagged.items():
        outcome = evaluate(y, amount, np.where(flags, BLOCK, PASS))
        rows.append({
            "Metoda": label,
            "Wykryte oszustwa": outcome.detected_share,
            "Trafne alarmy (precyzja)": outcome.precision,
            "Koszt na 1000 transakcji (zł)": outcome.cost_per_1000,
        })
    return false_alarms, pd.DataFrame(rows)


def comparison_table(comparison: pd.DataFrame) -> pd.DataFrame:
    """The result of compare_at_rules_false_alarms, formatted for display."""
    return pd.DataFrame({
        "Metoda": comparison["Metoda"],
        "Wykryte oszustwa": comparison["Wykryte oszustwa"].map(lambda v: fmt_pct(v, 1)),
        "Trafne alarmy (precyzja)": comparison["Trafne alarmy (precyzja)"].map(lambda v: fmt_pct(v, 1)),
        "Koszt na 1000 transakcji": comparison["Koszt na 1000 transakcji (zł)"].map(fmt_pln),
    })


def alarm_curve(y: np.ndarray, scores: np.ndarray, max_per_1000: float = 15, points: int = 300) -> pd.DataFrame:
    """Share of fraud detected vs. honest transactions flagged per 1000, for every possible threshold."""
    y_sorted = y[np.argsort(-scores, kind="stable")]
    detected = np.cumsum(y_sorted) / y.sum()
    false_per_1000 = np.cumsum(~y_sorted) / len(y) * 1000
    last = np.searchsorted(false_per_1000, max_per_1000, side="right")
    idx = np.unique(np.linspace(0, last - 1, points).astype(int))
    return pd.DataFrame({"false_per_1000": false_per_1000[idx], "detected": detected[idx]})
