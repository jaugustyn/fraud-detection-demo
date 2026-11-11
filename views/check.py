"""Manual check: pick an example or type in a transaction and see how the model scores and explains it."""

import streamlit as st

from src.app_data import load_meta, score_transaction, show_assessment, show_explanation
from src.config import CHECK_EXAMPLES
from src.features import CATEGORY_LABELS, MAX_HOURS_SINCE_PREV, transaction_input
from src.formatting import fmt_int

settings = st.session_state.settings
categories = list(CATEGORY_LABELS)
max_amount = round(load_meta()["train"]["max_fraud_amount"])
first_example = next(iter(CHECK_EXAMPLES))

# Widget values are dropped while another page is shown, so the page starts again from the first example.
for key, value in {"example": first_example, **CHECK_EXAMPLES[first_example]}.items():
    st.session_state.setdefault(key, value)


def fill_in_example() -> None:
    if st.session_state.example:
        st.session_state.update(CHECK_EXAMPLES[st.session_state.example])


def clear_example() -> None:
    st.session_state.example = None


st.title("Sprawdź transakcję")
st.segmented_control("Gotowe przykłady", list(CHECK_EXAMPLES), key="example", on_change=fill_in_example)

col_transaction, col_card, col_result = st.columns(3)
with col_transaction.container(border=True, height="stretch"):
    st.markdown("**Transakcja**")
    amount = st.number_input(
        f"Kwota (zł, maks. {fmt_int(max_amount)})", min_value=1.0, max_value=float(max_amount), step=50.0,
        format="%.0f", key="amount", on_change=clear_example,
    )
    time_of_day = st.time_input("Godzina", key="time_of_day", on_change=clear_example)
    category = st.selectbox("Kategoria sklepu", categories, format_func=CATEGORY_LABELS.get, key="category",
                            on_change=clear_example)

with col_card.container(border=True, height="stretch"):
    st.markdown("**Historia karty**")
    card_mean = st.number_input("Średnia kwota transakcji (zł)", min_value=1.0, step=50.0, format="%.0f",
                                key="card_mean", on_change=clear_example)
    spent_24h = st.number_input("Wydatki w 24 h przed tą transakcją (zł)", min_value=0.0, step=100.0, format="%.0f",
                                key="spent_24h", on_change=clear_example)
    hours_since_prev = st.number_input("Godziny od poprzedniej transakcji", min_value=0.0,
                                       max_value=float(MAX_HOURS_SINCE_PREV), step=1.0, format="%.1f",
                                       key="hours_since_prev", on_change=clear_example)

transaction = transaction_input(amount, time_of_day, category, card_mean, spent_24h, hours_since_prev)
with col_result.container(border=True, height="stretch"):
    st.markdown("**Ocena modelu**")
    show_assessment(score_transaction(transaction), settings)
    st.caption("Progi zmienisz na ekranie „Progi i koszty”.")

show_explanation(transaction)
