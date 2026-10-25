"""Trains the models on fraudTrain.csv, scores fraudTest.csv and saves what the app needs.

Run: uv run python train.py
"""

import json
import time

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from src.config import (
    ARTIFACTS_DIR, DATA_DIR, DEFAULT_BLOCK_COST, DEFAULT_VERIFY_COST, DEFAULT_VERIFY_EFFICACY,
    META_PATH, MODEL_PATH, SCORED_PATH,
)
from src.evaluation import Costs, compare_at_rules_false_alarms
from src.features import BASE_FEATURES, SENSITIVE_FEATURES, add_features, load_transactions
from src.rules import rule_flags

# Test-set columns kept for display; BASE_FEATURES are kept too, the app explains decisions from them.
DISPLAY_COLUMNS = ["ts", "cc_num", "category", "amount", "is_fraud", "amount_ratio", "spent_24h", "hours_since_prev"]
SCORE_COLUMNS = ["score_xgb", "score_xgb_sensitive", "score_lr"]


def fit_xgboost(X: pd.DataFrame, y: pd.Series) -> XGBClassifier:
    model = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8,
        tree_method="hist", n_jobs=-1, random_state=42,
    )
    return model.fit(X, y)


def summary(part: pd.DataFrame) -> dict:
    return {
        "rows": len(part),
        "fraud": int(part["is_fraud"].sum()),
        "from": part["ts"].min().strftime("%Y-%m-%d"),
        "to": part["ts"].max().strftime("%Y-%m-%d"),
    }


def main() -> None:
    if not (DATA_DIR / "fraudTrain.csv").exists() or not (DATA_DIR / "fraudTest.csv").exists():
        raise SystemExit(f"Brak danych. Pobierz fraudTrain.csv i fraudTest.csv z Kaggle do folderu {DATA_DIR} (patrz README).")
    start = time.time()
    print("Wczytuję dane i liczę cechy...")
    df = add_features(load_transactions())
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"].sort_values("ts").reset_index(drop=True)
    y = train["is_fraud"]
    with_sensitive = BASE_FEATURES + SENSITIVE_FEATURES

    print("Uczę XGBoost (2 warianty) i regresję logistyczną...")
    xgb = fit_xgboost(train[BASE_FEATURES], y)
    xgb_sensitive = fit_xgboost(train[with_sensitive], y)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(train[BASE_FEATURES], y)

    scored = pd.concat([test[DISPLAY_COLUMNS + BASE_FEATURES], rule_flags(test)], axis=1)
    scored["score_xgb"] = xgb.predict_proba(test[BASE_FEATURES])[:, 1]
    scored["score_xgb_sensitive"] = xgb_sensitive.predict_proba(test[with_sensitive])[:, 1]
    scored["score_lr"] = lr.predict_proba(test[BASE_FEATURES])[:, 1]
    scored[SCORE_COLUMNS] = scored[SCORE_COLUMNS].astype("float32")

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    scored.to_parquet(SCORED_PATH, index=False)
    xgb.save_model(MODEL_PATH)
    meta = {
        "train": summary(train),
        "test": summary(test),
        "average_precision": {c: average_precision_score(scored["is_fraud"], scored[c]) for c in SCORE_COLUMNS},
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    costs = Costs(DEFAULT_BLOCK_COST, DEFAULT_VERIFY_COST, DEFAULT_VERIFY_EFFICACY)
    false_alarms, comparison = compare_at_rules_false_alarms(
        scored, {"Regresja logistyczna": "score_lr", "XGBoost": "score_xgb"}, costs
    )
    print(json.dumps(meta, indent=2))
    print(f"\nPorównanie przy {false_alarms} zablokowanych uczciwych transakcjach (jak reguły):")
    print(comparison.round(3).to_string(index=False))
    print(f"\nGotowe w {time.time() - start:.0f} s. Wyniki w {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
