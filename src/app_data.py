"""Cached data access, scoring, decision display and explanations for the app."""

import json
from dataclasses import dataclass

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import xgboost as xgb

from src.config import META_PATH, MODEL_PATH, RISK_STEPS, SCORED_PATH
from src.evaluation import BLOCK, DECISION_LABELS, PASS, VERIFY, decide
from src.features import BASE_FEATURES, CATEGORY_LABELS, FEATURE_LABELS
from src.formatting import BLUE, DECISION_COLORS, GRID, INK, ORANGE, fmt_hours, fmt_pct, fmt_pln, fmt_step

DECISION_ICONS = {PASS: ":material/check_circle:", VERIFY: ":material/sms:", BLOCK: ":material/block:"}
DECISION_BADGES = {PASS: "green", VERIFY: "yellow", BLOCK: "red"}  # Streamlit badge colors of the three zones


@dataclass(frozen=True)
class Settings:
    """The decision thresholds set on the trade-off panel."""

    verify_from: float  # risk score (0-1) from which a transaction is verified
    block_from: float  # risk score (0-1) from which a transaction is blocked

    def decide(self, risk: float) -> int:
        return decide(np.array([risk]), self.verify_from, self.block_from)[0]


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
    """Larger, darker chart text than the default, so it reads well on a big screen."""
    return (chart.configure_axis(labelFontSize=13, titleFontSize=13, labelColor=INK, titleColor=INK)
            .configure_legend(labelFontSize=13, labelColor=INK))


def slider_position(risk: float) -> float:
    """Where a risk (0-1) lies on the threshold slider, whose steps are evenly spaced (0 = left end, 1 = right)."""
    return float(np.interp(risk, np.array(RISK_STEPS) / 100, np.linspace(0, 1, len(RISK_STEPS))))


def show_thresholds(settings: Settings) -> None:
    """The three decision zones of the current thresholds, as colored badges."""
    verify, block = fmt_step(settings.verify_from * 100), fmt_step(settings.block_from * 100)
    st.markdown(f"{_badge(PASS, f'Przepuść poniżej {verify}')} "
                f"{_badge(VERIFY, f'Weryfikacja {verify}–{block}')} "
                f"{_badge(BLOCK, f'Blokada od {block}')}")


def _badge(decision: int, text: str) -> str:
    return f":{DECISION_BADGES[decision]}-badge[{DECISION_ICONS[decision]} {text}]"


def show_assessment(risk: float, settings: Settings) -> None:
    """Risk of one transaction and the proposed decision, in plain text, plus the risk on the slider's scale."""
    decision = settings.decide(risk)
    st.markdown(f"Ryzyko oszustwa: **{fmt_pct(risk, 1)}**  \nDecyzja: {_badge(decision, DECISION_LABELS[decision])}")
    _risk_meter(risk, decision, settings)


def _risk_meter(risk: float, decision: int, settings: Settings) -> None:
    """Risk as a bar on the same uneven scale as the threshold slider, colored by the decision."""
    x = alt.X("start:Q", scale=alt.Scale(domain=[0, 1]), axis=None)
    bar = {"y": alt.value(8), "y2": alt.value(20)}

    track = alt.Chart(pd.DataFrame({"start": [0.0], "end": [1.0]})).mark_bar(cornerRadius=6, color=GRID).encode(
        x=x, x2="end:Q", **bar)
    fill = alt.Chart(pd.DataFrame({
        "start": [0.0], "end": [slider_position(risk)], "Ryzyko": [fmt_pct(risk, 1)],
    })).mark_bar(cornerRadius=6, color=DECISION_COLORS[decision]).encode(x=x, x2="end:Q", tooltip=["Ryzyko:N"], **bar)
    thresholds = pd.DataFrame({
        "start": [slider_position(settings.verify_from), slider_position(settings.block_from)],
        "label": [fmt_step(settings.verify_from * 100), fmt_step(settings.block_from * 100)],
    })
    ticks = alt.Chart(thresholds).mark_rule(color=INK, strokeWidth=2).encode(x=x, y=alt.value(2), y2=alt.value(26))
    labels = alt.Chart(thresholds).mark_text(color=INK, fontSize=13, baseline="top").encode(
        x=x, y=alt.value(30), text="label:N")
    st.altair_chart((track + fill + ticks + labels).properties(height=48).configure_view(stroke=None), width="stretch")


def show_explanation(row: pd.Series) -> None:
    """Chart of what raised and lowered the risk of one transaction."""
    st.markdown("**Co wpłynęło na ocenę ryzyka**")
    reasons = explain(row)
    reasons["Etykieta"] = reasons["Cecha"] + ": " + reasons["Wartość"]
    reasons["Kierunek"] = np.where(reasons["Wpływ"] > 0, "Podnosi ryzyko", "Obniża ryzyko")
    chart = alt.Chart(reasons).mark_bar(size=20, cornerRadius=4).encode(
        x=alt.X("Wpływ:Q", title="← obniża ryzyko · podnosi ryzyko →", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("Etykieta:N", sort=None, title=None, axis=alt.Axis(labelLimit=420)),
        # The caption below names the colors; a chart legend would add another font size and a blank band.
        color=alt.Color("Kierunek:N", legend=None,
                        scale=alt.Scale(domain=["Podnosi ryzyko", "Obniża ryzyko"], range=[ORANGE, BLUE])),
        tooltip=["Cecha:N", "Wartość:N", "Kierunek:N"],
    )
    st.altair_chart(readable(chart.properties(height=alt.Step(28))), width="stretch")
    st.caption("Pomarańczowe słupki podnoszą ryzyko, niebieskie je obniżają. Długość słupka to siła wpływu cechy "
               "(wartości SHAP z modelu XGBoost).")
