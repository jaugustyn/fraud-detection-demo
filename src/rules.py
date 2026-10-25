"""Simple hand-written rules: the baseline the models are compared against.

Thresholds are round numbers picked by looking at the training data.
"""

import pandas as pd

ONLINE_CATEGORIES = ["shopping_net", "misc_net"]

RULE_LABELS = {
    "rule_high_amount": "Kwota powyżej 3 000 zł",
    "rule_night": "Transakcja nocna (22:00–3:59) powyżej 1 200 zł",
    "rule_online": "Zakupy lub inne płatności online powyżej 2 800 zł",
}


def rule_flags(df: pd.DataFrame) -> pd.DataFrame:
    """One boolean column per rule; a transaction is flagged when any rule fires."""
    flags = pd.DataFrame(index=df.index)
    flags["rule_high_amount"] = df["amount"] > 3000
    flags["rule_night"] = (df["night"] == 1) & (df["amount"] > 1200)
    flags["rule_online"] = df["category"].isin(ONLINE_CATEGORIES) & (df["amount"] > 2800)
    flags["rules_any"] = flags[list(RULE_LABELS)].any(axis=1)
    return flags
