"""Strażnik Płatności – Streamlit entry point: page navigation and the decision thresholds shared by all pages.

Run: uv run python -m streamlit run app.py
"""

import streamlit as st

from src.app_data import Settings
from src.config import DEFAULT_THRESHOLDS, SCORED_PATH

st.set_page_config(page_title="Strażnik Płatności", page_icon=":material/shield:", layout="wide")

if not SCORED_PATH.exists():
    st.error("Brak wytrenowanych modeli. Najpierw uruchom: `uv run python train.py`")
    st.stop()

page = st.navigation([
    st.Page("views/panel.py", title="Panel kompromisu", icon=":material/tune:", default=True),
    st.Page("views/comparison.py", title="Porównanie metod", icon=":material/compare_arrows:"),
    st.Page("views/transactions.py", title="Transakcje", icon=":material/receipt_long:"),
    st.Page("views/check.py", title="Sprawdź transakcję", icon=":material/fact_check:"),
])

# The thresholds slider is on the trade-off panel and keeps its value across pages.
verify_from, block_from = st.session_state.get("thresholds", DEFAULT_THRESHOLDS)
st.session_state.settings = Settings(verify_from / 100, block_from / 100)
page.run()
