"""Transactions of one day with the proposed decision, plus an explanation of a selected one."""

import numpy as np
import pandas as pd
import streamlit as st

from src.app_data import load_scored, show_assessment, show_explanation, show_thresholds
from src.evaluation import BLOCK, DECISION_LABELS, PASS, decide
from src.features import CATEGORY_LABELS
from src.formatting import fmt_int, fmt_pln

HELD, MISTAKES = "Wstrzymane", "Pomyłki modelu"
ROW_HEIGHT = 35  # px per row of st.dataframe, used to fit the table to its rows

settings = st.session_state.settings
df = load_scored()

st.title("Transakcje")
st.caption("Transakcje z wybranego dnia, od najbardziej ryzykownych. Zaznacz wiersz, aby zobaczyć wyjaśnienie decyzji "
           "(na start pokazujemy pierwszy).")

busiest_fraud_day = df.loc[df["is_fraud"] == 1, "day"].value_counts().idxmax()
col_day, col_view, col_thresholds = st.columns([1, 1.2, 2.3], vertical_alignment="bottom")
day = col_day.date_input("Dzień", value=busiest_fraud_day.date(), min_value=df["day"].min().date(),
                         max_value=df["day"].max().date(), format="DD.MM.YYYY")
view = col_view.segmented_control(
    "Pokaż", [HELD, MISTAKES], default=HELD, required=True,
    help="Wstrzymane: transakcje skierowane do weryfikacji lub zablokowane. Pomyłki modelu: przepuszczone oszustwa "
         "i fałszywe blokady.",
)
with col_thresholds:
    show_thresholds(settings)

day_df = df[df["day"] == pd.Timestamp(day)].copy()
day_df["decision"] = decide(day_df["score_xgb"].to_numpy(), settings.verify_from, settings.block_from)
fraud = day_df["is_fraud"] == 1
missed = fraud & (day_df["decision"] == PASS)
false_block = ~fraud & (day_df["decision"] == BLOCK)
st.caption(f"Tego dnia: {fmt_int(len(day_df))} transakcji, wstrzymanych {fmt_int((day_df['decision'] != PASS).sum())}, "
           f"oszustw wg danych {fmt_int(fraud.sum())}. Pomyłki: przepuszczone oszustwa {fmt_int(missed.sum())}, "
           f"fałszywe blokady {fmt_int(false_block.sum())}.")

day_df = day_df[missed | false_block] if view == MISTAKES else day_df[day_df["decision"] != PASS]
if day_df.empty:
    st.info("Tego dnia nie ma takich transakcji. Wybierz inny dzień.", icon=":material/event_busy:")
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
    key=f"transactions-{day}-{view}-{settings.verify_from}-{settings.block_from}",
    column_config={
        "Kwota (zł)": st.column_config.NumberColumn(format="localized"),
        "Ryzyko": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "Oszustwo wg danych": st.column_config.TextColumn(
            help="Prawdziwa etykieta ze zbioru testowego. Analityk w banku jej nie zna, "
                 "pokazujemy ją, żeby sprawdzić model."),
    },
)

# Without a selection the first (riskiest) row is explained, so the screen is never empty.
row = day_df.iloc[event.selection.rows[0] if event.selection.rows else 0]
st.subheader(f"{row['ts']:%d.%m.%Y, %H:%M} · {CATEGORY_LABELS[row['category']]} · {fmt_pln(row['amount'])}")

left, right = st.columns([1, 3], gap="large")
with left:
    show_assessment(row["score_xgb"], settings)
    st.markdown(f"**Oszustwo wg danych:** {'tak' if row['is_fraud'] else 'nie'}")
with right:
    show_explanation(row)
