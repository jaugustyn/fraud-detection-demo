"""Strażnik Płatności – Streamlit entry point: shared sidebar settings and page navigation.

Run: uv run streamlit run app.py
"""

import streamlit as st

from src.app_data import Settings
from src.config import (
    DEFAULT_BLOCK_COST, DEFAULT_THRESHOLDS, DEFAULT_VERIFY_COST, DEFAULT_VERIFY_EFFICACY, RISK_STEPS, SCORED_PATH,
)
from src.evaluation import Costs
from src.formatting import fmt_step

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

# Rendered on every page, so the settings stay the same while switching pages.
with st.sidebar:
    st.subheader("Progi decyzji")
    verify_from, block_from = st.select_slider(
        "Ryzyko oszustwa", options=RISK_STEPS, value=DEFAULT_THRESHOLDS, format_func=fmt_step,
        help="Poniżej pierwszego progu transakcja przechodzi. Między progami klient musi ją potwierdzić "
             "(SMS, 3D Secure). Od drugiego progu transakcja jest blokowana. Skala jest gęstsza przy niskim "
             "ryzyku, bo tam jest prawie każda transakcja.",
    )
    st.caption(f"Poniżej {fmt_step(verify_from)}: przepuść · {fmt_step(verify_from)}–{fmt_step(block_from)}: "
               f"weryfikacja · od {fmt_step(block_from)}: blokada")

    with st.expander("Założenia kosztowe"):
        block_cost = st.number_input("Koszt zablokowania uczciwej transakcji (zł)", min_value=0.0,
                                     value=DEFAULT_BLOCK_COST, step=10.0, format="%.0f")
        verify_cost = st.number_input("Koszt jednej weryfikacji (zł)", min_value=0.0,
                                      value=DEFAULT_VERIFY_COST, step=1.0, format="%.0f")
        efficacy = st.slider("Weryfikacja zatrzymuje oszustwa (%)", min_value=0, max_value=100,
                             value=round(DEFAULT_VERIFY_EFFICACY * 100))
        st.caption("Nasze założenia, nie dane rynkowe. Przepuszczone oszustwo kosztuje tyle, ile jego kwota.")

st.session_state.settings = Settings(
    verify_from / 100, block_from / 100, Costs(block_cost, verify_cost, efficacy / 100)
)
page.run()
