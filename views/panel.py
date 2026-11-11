"""Thresholds and costs: the decision thresholds, what they catch, whom they stop and what it costs."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.app_data import load_meta, load_scored, readable, show_thresholds
from src.config import DEFAULT_THRESHOLDS, RISK_STEPS, VERIFY_COST
from src.evaluation import BLOCK, DECISION_LABELS, PASS, VERIFY, Outcome, decide, evaluate
from src.formatting import BLUE, GRAY, INK, ORANGE, fmt_date, fmt_int, fmt_pct, fmt_pln, fmt_step

COST_PARTS = {"Oszustwa, które przeszły": ORANGE, "Zablokowane uczciwe transakcje": BLUE, "Weryfikacje": GRAY}
COST_PART_SHORT = ["oszustwa", "blokady", "weryfikacje"]  # in the bar labels, same order


def cost_parts(outcome: Outcome) -> list[float]:
    """Cost per 1000 transactions split by cause, in the order of COST_PARTS."""
    fees = VERIFY_COST * (outcome.fraud[VERIFY] + outcome.honest[VERIFY])
    per_1000 = 1000 / outcome.n
    # Verified fraud that got through is a loss like passed fraud, so it moves from the verification cost.
    return [(outcome.cost[PASS] + outcome.cost[VERIFY] - fees) * per_1000, outcome.cost[BLOCK] * per_1000,
            fees * per_1000]


def total_label(outcome: Outcome) -> str:
    """'415 zł: oszustwa 371 zł + blokady 36 zł + weryfikacje 8 zł'; the small parts are hard to see on the bar."""
    shown = [f"{name} {fmt_pln(value)}" for name, value in zip(COST_PART_SHORT, cost_parts(outcome)) if value >= 0.5]
    total = fmt_pln(outcome.cost_per_1000)
    return f"{total}: {' + '.join(shown)}" if len(shown) > 1 else total


settings = st.session_state.settings
df = load_scored()
test = load_meta()["test"]
y = df["is_fraud"].to_numpy(bool)
amount = df["amount"].to_numpy()

current = evaluate(y, amount, decide(df["score_xgb"].to_numpy(), settings.verify_from, settings.block_from))
no_system = evaluate(y, amount, np.full(len(df), PASS))
rules = evaluate(y, amount, np.where(df["rules_any"], BLOCK, PASS))

period = f"{fmt_date(test['from'])}–{fmt_date(test['to'])}"
st.title("Progi i koszty")
st.caption(f"{fmt_int(test['rows'])} transakcji testowych ({period}), w tym {fmt_int(test['fraud'])} oszustw.")

with st.container(border=True):
    # persist_state keeps the thresholds while other pages are shown; app.py reads them from session_state.
    st.select_slider(
        "Progi decyzji: od jakiego ryzyka oszustwa transakcję weryfikujemy (SMS, 3D Secure), a od jakiego blokujemy",
        options=RISK_STEPS, value=DEFAULT_THRESHOLDS, format_func=fmt_step, key="thresholds", persist_state="session",
    )
    show_thresholds(settings)

# Short notes under the numbers instead of "?" tooltips: nobody hovers them while the app is being shown.
tiles = [
    ("Wykryte oszustwa", fmt_pct(current.detected_share), None,
     f"{fmt_int(current.detected)} z {fmt_int(sum(current.fraud.values()))} oszustw zweryfikowanych lub zablokowanych"),
    ("Fałszywe blokady", fmt_int(current.honest[BLOCK]), None, "Uczciwe transakcje zablokowane przez system"),
    ("Zbędne weryfikacje", fmt_int(current.honest[VERIFY]), None, "Uczciwe transakcje, które klient musiał potwierdzić"),
    ("Koszt na 1000 transakcji", fmt_pln(current.cost_per_1000),
     f"{fmt_pct(current.cost_per_1000 / no_system.cost_per_1000 - 1)} vs bez systemu",
     "Oszustwa, które przeszły, blokady i weryfikacje"),
]
for column, (label, value, delta, note) in zip(st.columns(4), tiles):
    with column.container(border=True, height="stretch"):  # stretch: tiles as tall as the cost tile with its delta
        st.metric(label, value, delta=delta, delta_color="inverse")
        st.caption(note)

st.subheader("Z czego składa się koszt na 1000 transakcji")
st.caption("Średnio na każde 1000 płatności: straty z oszustw, które przeszły, plus koszt zablokowanych uczciwych "
           "transakcji i weryfikacji.")
variants = {"Bez systemu": no_system, "Proste reguły (blokada)": rules, "Strażnik Płatności": current}
parts = pd.DataFrame([
    {"Wariant": name, "Składnik": part, "Koszt": value, "Kolejność": i}
    for name, outcome in variants.items()
    for i, (part, value) in enumerate(zip(COST_PARTS, cost_parts(outcome)))
])
parts["Etykieta"] = parts["Koszt"].map(fmt_pln)
totals = pd.DataFrame({
    "Wariant": list(variants),
    "Koszt": [o.cost_per_1000 for o in variants.values()],
    "Etykieta": [total_label(o) for o in variants.values()],
})

rows = alt.Y("Wariant:N", sort=list(variants), title=None, axis=alt.Axis(labelLimit=260))
bars = alt.Chart(parts).mark_bar(size=30).encode(
    x=alt.X("Koszt:Q", stack="zero", axis=None),  # every bar carries its total as a label
    y=rows,
    color=alt.Color("Składnik:N", title=None, legend=alt.Legend(orient="top", labelLimit=0),
                    scale=alt.Scale(domain=list(COST_PARTS), range=list(COST_PARTS.values()))),
    order=alt.Order("Kolejność:Q"),
    tooltip=["Wariant:N", "Składnik:N", alt.Tooltip("Etykieta:N", title="Koszt")],
)
labels = alt.Chart(totals).mark_text(align="left", dx=6, fontSize=16, fontWeight=500, color=INK).encode(
    x="Koszt:Q", y=rows, text="Etykieta:N")
st.altair_chart(readable((bars + labels).properties(height=190)), width="stretch")

st.subheader("Co dzieje się z transakcjami")
order = [PASS, VERIFY, BLOCK]
table = pd.DataFrame({
    "Decyzja": [DECISION_LABELS[d] for d in order],
    "Oszustwa": [fmt_int(current.fraud[d]) for d in order],
    "Uczciwe transakcje": [fmt_int(current.honest[d]) for d in order],
})
right_aligned = st.column_config.TextColumn(alignment="right")
st.dataframe(table, hide_index=True, width="content",
             column_config={"Oszustwa": right_aligned, "Uczciwe transakcje": right_aligned})
st.caption("Liczba transakcji testowych, które przy Twoich progach dostają każdą z decyzji.")
