"""Comparison of methods: rules vs logistic regression vs XGBoost, and the gender/age variant."""

import altair as alt
import pandas as pd
import streamlit as st

from src.app_data import load_scored, readable
from src.evaluation import (
    alarm_curve, compare_at_rules_false_alarms, comparison_table, sensitive_variants_table,
)
from src.formatting import BLUE, INK, ORANGE, fmt_int, fmt_pct
from src.rules import RULE_LABELS

MODELS = {"XGBoost": "score_xgb", "Regresja logistyczna": "score_lr"}

settings = st.session_state.settings
df = load_scored()
y = df["is_fraud"].to_numpy(bool)
right_aligned = st.column_config.TextColumn(alignment="right")

st.title("Porównanie metod")
st.caption("Te same transakcje testowe dla wszystkich metod (druga połowa 2020, modele nie widziały ich podczas nauki).")

false_alarms, comparison = compare_at_rules_false_alarms(df, MODELS, settings.costs)
detected = comparison.set_index("Metoda")["Wykryte oszustwa"]
rules = "; ".join(label[0].lower() + label[1:] for label in RULE_LABELS.values())
st.subheader("Przy tej samej liczbie fałszywych blokad")
st.markdown(
    f"Każda metoda blokuje **{fmt_int(false_alarms)}** uczciwych transakcji, tyle co proste reguły. "
    f"XGBoost wykrywa wtedy **{fmt_pct(detected['XGBoost'])}** oszustw, regresja logistyczna "
    f"**{fmt_pct(detected['Regresja logistyczna'])}**, a reguły **{fmt_pct(detected['Proste reguły'])}**."
)
st.dataframe(comparison_table(comparison), hide_index=True, width="stretch", column_config={
    "Wykryte oszustwa": right_aligned,
    "Trafne alarmy (precyzja)": st.column_config.TextColumn(
        alignment="right", help="Jaka część zablokowanych transakcji to faktycznie oszustwa."),
    "Koszt na 1000 transakcji": st.column_config.TextColumn(
        alignment="right",
        help="Jak w panelu, ale bez weryfikacji: oznaczona transakcja jest blokowana. Regresja wykrywa więcej "
             "oszustw niż reguły, a kosztuje więcej, bo gubi duże kwoty."),
})
st.caption(f"Proste reguły: {rules}.")

st.subheader("Wykryte oszustwa a fałszywe blokady")
curves = pd.concat([alarm_curve(y, df[col].to_numpy(), max_per_1000=15).assign(Metoda=label)
                    for label, col in MODELS.items()])
rules_point = pd.DataFrame({
    "false_per_1000": [false_alarms / len(df) * 1000],
    "detected": [detected["Proste reguły"]],
    "Metoda": ["Proste reguły"],
})
for points in (curves, rules_point):  # tooltip texts with a decimal comma
    points["Blokady na 1000"] = points["false_per_1000"].map(lambda v: f"{v:.1f}".replace(".", ","))
    points["Wykryte oszustwa"] = points["detected"].map(lambda v: fmt_pct(v, 1))
color = alt.Color("Metoda:N", title=None, legend=alt.Legend(orient="top"),
                  scale=alt.Scale(domain=[*MODELS, "Proste reguły"], range=[BLUE, ORANGE, INK]))
x = alt.X("false_per_1000:Q", title="Fałszywe blokady na 1000 transakcji",
          axis=alt.Axis(labelExpr="replace(format(datum.value, '~g'), '.', ',')"))
y_axis = alt.Y("detected:Q", title="Wykryte oszustwa", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]))
tooltip = ["Metoda:N", "Blokady na 1000:N", "Wykryte oszustwa:N"]
lines = alt.Chart(curves).mark_line(strokeWidth=2).encode(x=x, y=y_axis, color=color)
hover_points = alt.Chart(curves).mark_point(size=80, opacity=0).encode(x=x, y=y_axis, tooltip=tooltip)
point = alt.Chart(rules_point).mark_point(filled=True, size=120, opacity=1).encode(
    x=x, y=y_axis, color=color, tooltip=tooltip)
point_label = point.mark_text(align="left", dx=10, dy=16, color=INK, fontSize=13).encode(text="Metoda:N")
st.altair_chart(readable((lines + hover_points + point + point_label).properties(height=360)), width="stretch")
st.caption("Każdy punkt linii to inny próg modelu. Im wyżej i bardziej w lewo, tym lepiej.")

st.subheader("Czy model potrzebuje płci i wieku klienta?")
variants = sensitive_variants_table(df, false_alarms)
st.dataframe(variants, hide_index=True, width="stretch",
             column_config={c: right_aligned for c in variants.columns[1:]})
st.caption("Odsetek wykrytych oszustw. Płeć i wiek pomagają, zwłaszcza przy ostrym limicie, ale ich nie używamy: "
           "blokada karty nie powinna zależeć od płci ani wieku.")

st.info(
    f"**Dlaczego nie patrzymy na trafność (accuracy)?** Oszustwa to {fmt_pct(y.mean(), 2)} transakcji. "
    f"Model, który przepuszcza wszystko, ma trafność {fmt_pct(1 - y.mean(), 1)} i nie łapie żadnego oszustwa.",
    icon=":material/info:",
)
