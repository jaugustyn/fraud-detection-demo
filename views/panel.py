"""Trade-off panel: what the chosen thresholds catch, whom they stop and what it costs."""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.app_data import load_meta, load_scored, readable
from src.config import USD_PLN_SOURCE
from src.evaluation import BLOCK, DECISION_LABELS, PASS, VERIFY, decide, evaluate
from src.formatting import BLUE, GRAY, INK, fmt_date, fmt_int, fmt_pct, fmt_pln

settings = st.session_state.settings
df = load_scored()
test = load_meta()["test"]
y = df["is_fraud"].to_numpy(bool)
amount = df["amount"].to_numpy()

decisions = decide(df["score_xgb"].to_numpy(), settings.verify_from, settings.block_from)
current = evaluate(y, amount, decisions, settings.costs)
no_system = evaluate(y, amount, np.full(len(df), PASS), settings.costs)
rules = evaluate(y, amount, np.where(df["rules_any"], BLOCK, PASS), settings.costs)

period = f"{fmt_date(test['from'])}–{fmt_date(test['to'])}"
st.title("Panel kompromisu")
st.caption(f"{fmt_int(test['rows'])} transakcji testowych ({period}), w tym {fmt_int(test['fraud'])} oszustw. "
           "Przesuwaj progi w panelu bocznym.")

c1, c2, c3, c4 = st.columns(4)
# height="stretch": all tiles as tall as the cost tile, which has an extra line
c1.metric(
    "Wykryte oszustwa", fmt_pct(current.detected_share), border=True, height="stretch",
    help=f"{fmt_int(current.detected)} z {fmt_int(sum(current.fraud.values()))} oszustw trafiło do weryfikacji "
         "lub zostało zablokowanych.",
)
c2.metric("Fałszywe blokady", fmt_int(current.honest[BLOCK]), border=True, height="stretch",
          help="Uczciwe transakcje zablokowane przez system.")
c3.metric("Zbędne weryfikacje", fmt_int(current.honest[VERIFY]), border=True, height="stretch",
          help="Uczciwe transakcje, które klient musiał dodatkowo potwierdzić (SMS, 3D Secure).")
c4.metric(
    "Koszt na 1000 transakcji", fmt_pln(current.cost_per_1000), border=True, height="stretch",
    delta=f"{fmt_pct(current.cost_per_1000 / no_system.cost_per_1000 - 1)} vs bez systemu", delta_color="inverse",
    help=f"Przepuszczone oszustwa, fałszywe blokady i weryfikacje. Kwoty w zł: {USD_PLN_SOURCE}.",
)

st.subheader("Koszt na 1000 transakcji")
variants = pd.DataFrame({
    "Wariant": ["Bez systemu", "Proste reguły (blokada)", "Strażnik Płatności (Twoje progi)"],
    "Koszt": [no_system.cost_per_1000, rules.cost_per_1000, current.cost_per_1000],
})
variants["Etykieta"] = variants["Koszt"].map(fmt_pln)
bars = alt.Chart(variants).mark_bar(size=30, cornerRadiusEnd=4).encode(
    x=alt.X("Koszt:Q", axis=None),  # every bar carries its value label
    y=alt.Y("Wariant:N", sort=None, title=None, axis=alt.Axis(labelLimit=260)),
    color=alt.Color("Wariant:N", scale=alt.Scale(domain=variants["Wariant"].tolist(), range=[GRAY, GRAY, BLUE]),
                    legend=None),
    tooltip=[alt.Tooltip("Wariant:N"), alt.Tooltip("Etykieta:N", title="Koszt")],
)
labels = bars.mark_text(align="left", dx=6, fontSize=14, fontWeight=500).encode(
    text="Etykieta:N", color=alt.value(INK))
st.altair_chart(readable((bars + labels).properties(height=160)), width="stretch")

st.subheader("Co dzieje się z transakcjami")
order = [PASS, VERIFY, BLOCK]
table = pd.DataFrame({
    "Decyzja": [DECISION_LABELS[d] for d in order],
    "Oszustwa": [fmt_int(current.fraud[d]) for d in order],
    "Uczciwe transakcje": [fmt_int(current.honest[d]) for d in order],
    "Koszt": [fmt_pln(current.cost[d]) for d in order],
})
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "Oszustwa": st.column_config.TextColumn(alignment="right"),
    "Uczciwe transakcje": st.column_config.TextColumn(alignment="right"),
    "Koszt": st.column_config.TextColumn(
        alignment="right",
        help="Przepuść: kwoty przepuszczonych oszustw. Weryfikacja: opłaty za weryfikacje i oszustwa, które je "
             "przeszły. Blokada: koszt zablokowanych uczciwych transakcji.",
    ),
})
