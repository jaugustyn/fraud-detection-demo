"""Transactions of the day with the most fraud: held ones or the model's mistakes, with an explanation."""

import numpy as np
import pandas as pd
import streamlit as st

from src.app_data import load_scored, show_assessment, show_explanation, show_thresholds
from src.evaluation import BLOCK, DECISION_LABELS, PASS, decide
from src.features import CATEGORY_LABELS
from src.formatting import fmt_pln

HELD, MISTAKES = "Wstrzymane", "Pomyłki modelu"
VIEW_NOTES = {
    HELD: "Transakcje skierowane do weryfikacji lub zablokowane, od najbardziej ryzykownych.",
    MISTAKES: "Przepuszczone oszustwa i fałszywe blokady, od najbardziej ryzykownych.",
}
ROW_HEIGHT = 35  # px per row of st.dataframe, used to fit the table to its rows

settings = st.session_state.settings
df = load_scored()
day = df.loc[df["is_fraud"] == 1, "day"].value_counts().idxmax()

st.title("Transakcje")
st.caption(f"{day:%d.%m.%Y}, dzień z największą liczbą oszustw w danych testowych. Zaznacz wiersz, aby zobaczyć "
           "wyjaśnienie decyzji (na start pokazujemy pierwszy).")

col_view, col_thresholds = st.columns([1.2, 2.8], vertical_alignment="bottom")
view = col_view.segmented_control("Pokaż", [HELD, MISTAKES], default=HELD, required=True)
with col_thresholds:
    show_thresholds(settings, where_to_change=False)

day_df = df[df["day"] == day].copy()
day_df["decision"] = decide(day_df["score_xgb"].to_numpy(), settings.verify_from, settings.block_from)
fraud = day_df["is_fraud"] == 1
if view == MISTAKES:
    day_df = day_df[(fraud & (day_df["decision"] == PASS)) | (~fraud & (day_df["decision"] == BLOCK))]
else:
    day_df = day_df[day_df["decision"] != PASS]
if day_df.empty:
    st.info("Przy tych progach nie ma takich transakcji tego dnia.", icon=":material/check_circle:")
    st.stop()
day_df = day_df.sort_values("score_xgb", ascending=False, ignore_index=True)

table = pd.DataFrame({
    "Godzina": day_df["ts"].dt.strftime("%H:%M"),
    "Kategoria": day_df["category"].map(CATEGORY_LABELS),
    "Kwota (zł)": day_df["amount"].round(),
    "Ryzyko": day_df["score_xgb"] * 100,
    "Decyzja": day_df["decision"].map(DECISION_LABELS),
    "Oszustwo wg danych": np.where(day_df["is_fraud"] == 1, "Tak", "Nie"),
})
event = st.dataframe(
    table, hide_index=True, width="stretch", height=ROW_HEIGHT * (min(len(table), 4) + 1) + 3,
    on_select="rerun", selection_mode="single-row",
    key=f"transactions-{view}-{settings.verify_from}-{settings.block_from}",
    column_config={
        "Kwota (zł)": st.column_config.NumberColumn(format="localized"),
        "Ryzyko": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
    },
)
st.caption(f"{VIEW_NOTES[view]} „Oszustwo wg danych” to prawdziwa etykieta, której analityk w banku nie zna.")

# Without a selection the first (riskiest) row is explained, so the screen is never empty.
row = day_df.iloc[event.selection.rows[0] if event.selection.rows else 0]
st.subheader("Wyjaśnienie decyzji")
st.markdown(f"Wybrana transakcja: **{row['ts']:%H:%M} · {CATEGORY_LABELS[row['category']]} · "
            f"{fmt_pln(row['amount'])}**")

left, right = st.columns([1, 3], gap="large")
with left:
    st.markdown("**Ocena modelu**")
    show_assessment(row["score_xgb"], settings)
    st.markdown(f"Oszustwo wg danych: **{'tak' if row['is_fraud'] else 'nie'}**")
with right:
    show_explanation(row)
