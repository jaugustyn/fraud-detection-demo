"""Transactions of one day with the proposed decision, plus an explanation of a selected one."""

import numpy as np
import pandas as pd
import streamlit as st

from src.app_data import load_scored, show_explanation
from src.evaluation import DECISION_LABELS, PASS, decide
from src.features import CATEGORY_LABELS
from src.formatting import fmt_int, fmt_pct, fmt_pln

settings = st.session_state.settings
df = load_scored()

st.title("Transakcje")
st.caption("Transakcje z wybranego dnia, od najbardziej ryzykownych. Zaznacz wiersz, aby zobaczyć wyjaśnienie.")

busiest_fraud_day = df.loc[df["is_fraud"] == 1, "day"].value_counts().idxmax()
col_day, col_filter = st.columns([1, 3], vertical_alignment="bottom")
day = col_day.date_input("Dzień", value=busiest_fraud_day.date(), min_value=df["day"].min().date(),
                         max_value=df["day"].max().date(), format="DD.MM.YYYY")
only_held = col_filter.toggle("Tylko wstrzymane (weryfikacja lub blokada)", value=True)

day_df = df[df["day"] == pd.Timestamp(day)].copy()
day_df["decision"] = decide(day_df["score_xgb"].to_numpy(), settings.verify_from, settings.block_from)
held = int((day_df["decision"] != PASS).sum())
st.caption(f"Tego dnia: {fmt_int(len(day_df))} transakcji, wstrzymanych {fmt_int(held)}, "
           f"oszustw wg danych {fmt_int(day_df['is_fraud'].sum())}.")
if only_held:
    day_df = day_df[day_df["decision"] != PASS]
day_df = day_df.sort_values("score_xgb", ascending=False, ignore_index=True)

table = pd.DataFrame({
    "Godzina": day_df["ts"].dt.strftime("%H:%M"),
    "Karta": "•••• " + day_df["cc_num"].astype(str).str[-4:],
    "Kategoria": day_df["category"].map(CATEGORY_LABELS),
    "Kwota (zł)": day_df["amount"].round(),
    "Ryzyko": day_df["score_xgb"] * 100,
    "Decyzja": day_df["decision"].map(DECISION_LABELS),
    "Oszustwo wg danych": np.where(day_df["is_fraud"] == 1, "Tak", ""),
})
event = st.dataframe(
    table, hide_index=True, width="stretch", height=320, on_select="rerun", selection_mode="single-row",
    key=f"transactions-{day}-{only_held}-{settings.verify_from}-{settings.block_from}",
    column_config={
        "Kwota (zł)": st.column_config.NumberColumn(format="localized"),
        "Ryzyko": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "Oszustwo wg danych": st.column_config.TextColumn(
            help="Prawdziwa etykieta ze zbioru testowego. Analityk w banku jej nie zna, "
                 "pokazujemy ją, żeby sprawdzić model."),
    },
)

if not event.selection.rows:
    st.info("Wybierz transakcję z tabeli, aby zobaczyć wyjaśnienie decyzji.", icon=":material/touch_app:")
    st.stop()

row = day_df.iloc[event.selection.rows[0]]
st.subheader(f"{row['ts']:%d.%m.%Y, %H:%M} · {CATEGORY_LABELS[row['category']]} · {fmt_pln(row['amount'])}")

left, right = st.columns([1, 3], gap="large")
left.metric("Ryzyko oszustwa", fmt_pct(row["score_xgb"], 1), border=True)
left.metric("Proponowana decyzja", DECISION_LABELS[row["decision"]], border=True)
left.metric("Oszustwo wg danych", "Tak" if row["is_fraud"] else "Nie", border=True)

with right:
    show_explanation(row)
