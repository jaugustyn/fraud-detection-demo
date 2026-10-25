"""Decisions, costs and method comparison, shared by the app and the report."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.formatting import fmt_int, fmt_pct, fmt_pln

PASS, VERIFY, BLOCK = 0, 1, 2
DECISION_LABELS = {PASS: "Przepuść", VERIFY: "Dodatkowa weryfikacja", BLOCK: "Blokada"}


@dataclass(frozen=True)
class Costs:
    block: float  # PLN per blocked honest transaction
    verify: float  # PLN per verification
    efficacy: float  # share of fraud attempts stopped by verification


@dataclass(frozen=True)
class Outcome:
    fraud: dict[int, int]  # decision -> number of fraudulent transactions
    honest: dict[int, int]  # decision -> number of honest transactions
    cost: dict[int, float]  # decision -> cost in PLN
    n: int

    @property
    def total_cost(self) -> float:
        return sum(self.cost.values())

    @property
    def cost_per_1000(self) -> float:
        return self.total_cost / self.n * 1000

    @property
    def detected(self) -> int:
        return self.fraud[VERIFY] + self.fraud[BLOCK]

    @property
    def detected_share(self) -> float:
        return self.detected / sum(self.fraud.values())

    @property
    def precision(self) -> float:
        alarms = self.detected + self.honest[VERIFY] + self.honest[BLOCK]
        return self.detected / alarms if alarms else 0.0


def decide(scores: np.ndarray, verify_from: float, block_from: float) -> np.ndarray:
    return np.select([scores >= block_from, scores >= verify_from], [BLOCK, VERIFY], PASS)


def evaluate(y: np.ndarray, amount: np.ndarray, decisions: np.ndarray, costs: Costs) -> Outcome:
    """Cost model: a passed fraud loses its amount, verification stops `efficacy` of fraud
    and costs a fixed fee, blocking stops all fraud but costs a fee per honest transaction."""
    fraud = {d: int(np.sum(y & (decisions == d))) for d in DECISION_LABELS}
    honest = {d: int(np.sum(~y & (decisions == d))) for d in DECISION_LABELS}
    cost = {
        PASS: float(amount[y & (decisions == PASS)].sum()),
        VERIFY: float(
            (1 - costs.efficacy) * amount[y & (decisions == VERIFY)].sum()
            + costs.verify * np.sum(decisions == VERIFY)
        ),
        BLOCK: costs.block * honest[BLOCK],
    }
    return Outcome(fraud, honest, cost, len(y))


def flag_at_false_alarms(y: np.ndarray, scores: np.ndarray, false_alarms: int) -> np.ndarray:
    """Flags the riskiest transactions so that at most `false_alarms` honest ones are flagged."""
    honest_desc = np.sort(scores[~y])[::-1]
    return scores > honest_desc[false_alarms]


def compare_at_rules_false_alarms(
    df: pd.DataFrame, score_columns: dict[str, str], costs: Costs
) -> tuple[int, pd.DataFrame]:
    """Each model blocks as many honest transactions as the simple rules do; who catches more fraud?"""
    y = df["is_fraud"].to_numpy(bool)
    amount = df["amount"].to_numpy()
    rules = df["rules_any"].to_numpy(bool)
    false_alarms = int(np.sum(rules & ~y))

    flagged = {"Proste reguły": rules}
    for label, column in score_columns.items():
        flagged[label] = flag_at_false_alarms(y, df[column].to_numpy(), false_alarms)

    rows = []
    for label, flags in flagged.items():
        outcome = evaluate(y, amount, np.where(flags, BLOCK, PASS), costs)
        rows.append({
            "Metoda": label,
            "Wykryte oszustwa": outcome.detected_share,
            "Trafne alarmy (precyzja)": outcome.precision,
            "Zablokowane uczciwe transakcje": outcome.honest[BLOCK],
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


SENSITIVE_VARIANTS = {
    "Bez płci i wieku (używany w aplikacji)": "score_xgb",
    "Z płcią i wiekiem": "score_xgb_sensitive",
}


def sensitive_variants_table(df: pd.DataFrame, false_alarms: int) -> pd.DataFrame:
    """Share of fraud detected by XGBoost with and without gender and age, at two limits of honest
    transactions blocked: as many as the rules block, and a strict one of 1 per 1000 transactions."""
    y = df["is_fraud"].to_numpy(bool)
    strict = round(len(df) / 1000)

    def detected(column: str, limit: int) -> str:
        return fmt_pct(np.sum(flag_at_false_alarms(y, df[column].to_numpy(), limit) & y) / y.sum(), 1)

    return pd.DataFrame({
        "Wariant XGBoost": list(SENSITIVE_VARIANTS),
        f"Limit {fmt_int(false_alarms)} blokad (jak reguły)": [detected(c, false_alarms) for c in SENSITIVE_VARIANTS.values()],
        f"Limit {fmt_int(strict)} blokad (1 na 1000)": [detected(c, strict) for c in SENSITIVE_VARIANTS.values()],
    })


def alarm_curve(y: np.ndarray, scores: np.ndarray, max_per_1000: float = 30, points: int = 300) -> pd.DataFrame:
    """Share of fraud detected vs. honest transactions flagged per 1000, for every possible threshold."""
    y_sorted = y[np.argsort(-scores, kind="stable")]
    detected = np.cumsum(y_sorted) / y.sum()
    false_per_1000 = np.cumsum(~y_sorted) / len(y) * 1000
    last = np.searchsorted(false_per_1000, max_per_1000, side="right")
    idx = np.unique(np.linspace(0, last - 1, points).astype(int))
    return pd.DataFrame({"false_per_1000": false_per_1000[idx], "detected": detected[idx]})
