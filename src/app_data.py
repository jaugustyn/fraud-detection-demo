"""Cached data access, scoring and decision explanations for the app."""

import json
from dataclasses import dataclass

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import xgboost as xgb

from src.config import META_PATH, MODEL_PATH, SCORED_PATH
from src.evaluation import Costs
from src.features import BASE_FEATURES, CATEGORY_LABELS, FEATURE_LABELS
from src.formatting import BLUE, INK, ORANGE, fmt_hours, fmt_pln


@dataclass(frozen=True)
class Settings:
    verify_from: float  # risk score (0-1) from which a transaction is verified
    block_from: float  # risk score (0-1) from which a transaction is blocked
    costs: Costs


@st.cache_data
def load_scored() -> pd.DataFrame:
    df = pd.read_parquet(SCORED_PATH)
    df["day"] = df["ts"].dt.normalize()
    return df


@st.cache_data
def load_meta() -> dict:
    return json.loads(META_PATH.read_text(encoding="utf-8"))


@st.cache_resource
def load_booster() -> xgb.Booster:
    return xgb.Booster(model_file=str(MODEL_PATH))


def _model_input(row: pd.Series) -> xgb.DMatrix:
    return xgb.DMatrix(row[BASE_FEATURES].to_frame().T.astype("float32"))


def score_transaction(row: pd.Series) -> float:
    """Fraud risk (0-1) from the XGBoost model used in the app."""
    return float(load_booster().predict(_model_input(row))[0])


def explain(row: pd.Series) -> pd.DataFrame:
    """SHAP contributions of the XGBoost model for one transaction, grouped into business features.

    XGBoost computes exact SHAP values itself (pred_contribs), so no extra library is needed.
    """
    contributions = load_booster().predict(_model_input(row), pred_contribs=True)[0][:-1]  # last one is the bias
    grouped = pd.Series(contributions, index=BASE_FEATURES).groupby(FEATURE_LABELS).sum()
    values = {
        "Kwota": fmt_pln(row["amount"]),
        "Godzina": row["ts"].strftime("%H:%M"),
        "Kategoria sklepu": CATEGORY_LABELS[row["category"]],
        "Kwota względem zwykłych wydatków karty": f"{row['amount_ratio']:.1f}× średniej".replace(".", ","),
        "Wydatki karty w ostatnich 24 h": fmt_pln(row["spent_24h"]),
        "Czas od poprzedniej transakcji karty": fmt_hours(row["hours_since_prev"]),
    }
    result = pd.DataFrame({
        "Cecha": grouped.index,
        "Wartość": [values[label] for label in grouped.index],
        "Wpływ": grouped.to_numpy(),
    })
    return result.sort_values("Wpływ", key=abs, ascending=False, ignore_index=True)


def readable(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """Larger, darker chart text than the default, so it reads well on a projector."""
    return (chart.configure_axis(labelFontSize=13, titleFontSize=13, labelColor=INK, titleColor=INK)
            .configure_legend(labelFontSize=13, labelColor=INK))


def show_explanation(row: pd.Series) -> None:
    """Chart of what raised and lowered the risk of one transaction."""
    st.markdown("**Co wpłynęło na ocenę ryzyka**")
    reasons = explain(row)
    reasons["Etykieta"] = reasons["Cecha"] + ": " + reasons["Wartość"]
    reasons["Kierunek"] = np.where(reasons["Wpływ"] > 0, "Podnosi ryzyko", "Obniża ryzyko")
    chart = alt.Chart(reasons).mark_bar(size=20, cornerRadius=4).encode(
        x=alt.X("Wpływ:Q", title="← obniża ryzyko · podnosi ryzyko →", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("Etykieta:N", sort=None, title=None, axis=alt.Axis(labelLimit=420)),
        color=alt.Color("Kierunek:N", title=None, legend=alt.Legend(orient="top"),
                        scale=alt.Scale(domain=["Podnosi ryzyko", "Obniża ryzyko"], range=[ORANGE, BLUE])),
        tooltip=["Cecha:N", "Wartość:N", "Kierunek:N"],
    )
    st.altair_chart(readable(chart.properties(height=260)), width="stretch")
    st.caption("Długość słupka to siła wpływu cechy (wartości SHAP z modelu XGBoost).")
