"""Manual check: type in a transaction and see how the model scores and explains it."""

from datetime import datetime, time

import numpy as np
import pandas as pd
import streamlit as st

from src.app_data import score_transaction, show_explanation
from src.evaluation import DECISION_LABELS, decide
from src.features import CATEGORY_LABELS, MAX_HOURS_SINCE_PREV, add_model_inputs
from src.formatting import fmt_pct

settings = st.session_state.settings
categories = list(CATEGORY_LABELS)

st.title("Sprawdź transakcję")
st.caption("Wpisz dane transakcji i zobacz, jak oceni ją model. Na start: typowa uczciwa transakcja z danych.")

col_amount, col_time, col_category = st.columns(3)
amount = col_amount.number_input("Kwota (zł)", min_value=1.0, value=200.0, step=50.0, format="%.0f")
time_of_day = col_time.time_input("Godzina", value=time(14, 0))
category = col_category.selectbox("Kategoria sklepu", categories, index=categories.index("grocery_pos"),
                                  format_func=CATEGORY_LABELS.get)

# Defaults are rounded medians of honest transactions in the test data.
with st.expander("Historia karty"):
    col_mean, col_24h, col_prev = st.columns(3)
    card_mean = col_mean.number_input("Średnia kwota transakcji na tej karcie (zł)", min_value=1.0, value=250.0,
                                      step=50.0, format="%.0f")
    spent_24h = col_24h.number_input("Wydatki karty w ostatnich 24 h (zł)", min_value=0.0, value=800.0, step=100.0,
                                     format="%.0f", help="Bez sprawdzanej transakcji.")
    hours_since_prev = col_prev.number_input("Godziny od poprzedniej transakcji karty", min_value=0.0,
                                             max_value=float(MAX_HOURS_SINCE_PREV), value=4.0, step=1.0)

transaction = add_model_inputs(pd.DataFrame([{
    "ts": datetime.combine(datetime.today(), time_of_day),  # only the time of day matters
    "hour": time_of_day.hour,
    "amount": amount,
    "category": category,
    "amount_ratio": amount / card_mean,
    "spent_24h": spent_24h,
    "hours_since_prev": hours_since_prev,
}])).iloc[0]
risk = score_transaction(transaction)
decision = decide(np.array([risk]), settings.verify_from, settings.block_from)[0]

left, right = st.columns([1, 3], gap="large")
left.metric("Ryzyko oszustwa", fmt_pct(risk, 1), border=True)
left.metric("Proponowana decyzja", DECISION_LABELS[decision], border=True)
with right:
    show_explanation(transaction)
