"""Loading the Sparkov card transactions and building model features."""

import numpy as np
import pandas as pd

from src.config import DATA_DIR, USD_PLN

RAW_COLUMNS = ["trans_date_trans_time", "cc_num", "category", "amt", "gender", "dob", "is_fraud"]

CATEGORY_LABELS = {
    "shopping_net": "Zakupy online",
    "misc_net": "Inne płatności online",
    "grocery_net": "Spożywcze online",
    "shopping_pos": "Zakupy w sklepie",
    "grocery_pos": "Spożywcze w sklepie",
    "misc_pos": "Inne płatności w sklepie",
    "gas_transport": "Paliwo i transport",
    "travel": "Podróże",
    "entertainment": "Rozrywka",
    "food_dining": "Restauracje",
    "personal_care": "Higiena i uroda",
    "health_fitness": "Zdrowie i sport",
    "kids_pets": "Dzieci i zwierzęta",
    "home": "Dom",
}
CATEGORY_COLUMNS = [f"cat_{c}" for c in CATEGORY_LABELS]

NIGHT_HOURS = [22, 23, 0, 1, 2, 3]
MAX_HOURS_SINCE_PREV = 168  # a week; also used for a card's first transaction

BASE_FEATURES = [
    "log_amount",
    "hour",
    "night",
    "log_amount_ratio",
    "log_spent_24h",
    "log_hours_since_prev",
    *CATEGORY_COLUMNS,
]
SENSITIVE_FEATURES = ["age", "is_male"]

# Business-friendly label of each model feature; used to group SHAP contributions.
FEATURE_LABELS = {
    "log_amount": "Kwota",
    "hour": "Godzina",
    "night": "Godzina",
    "log_amount_ratio": "Kwota względem zwykłych wydatków karty",
    "log_spent_24h": "Wydatki karty w ostatnich 24 h",
    "log_hours_since_prev": "Czas od poprzedniej transakcji karty",
    **{c: "Kategoria sklepu" for c in CATEGORY_COLUMNS},
    "age": "Wiek klienta",
    "is_male": "Płeć klienta",
}


def load_transactions() -> pd.DataFrame:
    """Both Kaggle files in one frame; amounts converted to PLN."""
    frames = []
    for split in ("train", "test"):
        part = pd.read_csv(DATA_DIR / f"fraud{split.title()}.csv", usecols=RAW_COLUMNS)
        part["split"] = split
        frames.append(part)
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["trans_date_trans_time"])
    df["amount"] = (df["amt"] * USD_PLN).round(2)
    return df.drop(columns=["trans_date_trans_time", "amt"])


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds model features. Card history features use only earlier transactions of the same card."""
    df = df.sort_values(["cc_num", "ts"], kind="stable").reset_index(drop=True)
    by_card = df.groupby("cc_num", sort=False)

    previous_mean = by_card["amount"].transform(lambda s: s.shift().expanding().mean())
    df["amount_ratio"] = (df["amount"] / previous_mean).fillna(1.0)
    last_24h = df.set_index("ts").groupby("cc_num", sort=False)["amount"].rolling("24h").sum()
    df["spent_24h"] = last_24h.to_numpy() - df["amount"].to_numpy()
    df["hours_since_prev"] = (
        by_card["ts"].diff().dt.total_seconds().div(3600)
        .fillna(MAX_HOURS_SINCE_PREV).clip(upper=MAX_HOURS_SINCE_PREV)
    )

    df["hour"] = df["ts"].dt.hour
    df["age"] = (df["ts"] - pd.to_datetime(df["dob"])).dt.days / 365.25
    df["is_male"] = (df["gender"] == "M").astype("int8")
    return add_model_inputs(df)


def add_model_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Turns business values (amount, hour, category, card history) into model inputs.

    Shared by training and the manual check in the app, so both compute them the same way.
    """
    df["night"] = df["hour"].isin(NIGHT_HOURS).astype("int8")
    for category, column in zip(CATEGORY_LABELS, CATEGORY_COLUMNS):
        df[column] = (df["category"] == category).astype("int8")
    # Log scale helps logistic regression with skewed amounts; trees are indifferent to it.
    df["log_amount"] = np.log1p(df["amount"])
    df["log_amount_ratio"] = np.log1p(df["amount_ratio"])
    df["log_spent_24h"] = np.log1p(df["spent_24h"].clip(lower=0))
    df["log_hours_since_prev"] = np.log1p(df["hours_since_prev"])
    return df
