"""Shared settings: paths, currency conversion and default cost assumptions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "artifacts"
SCORED_PATH = ARTIFACTS_DIR / "scored_test.parquet"
MODEL_PATH = ARTIFACTS_DIR / "xgb_model.json"
META_PATH = ARTIFACTS_DIR / "meta.json"
RESULTS_DIR = ROOT / "results"

# The data set holds US transactions in USD; everything is shown in PLN at one fixed rate.
USD_PLN = 3.9247
USD_PLN_SOURCE = "kurs średni NBP z 23.10.2026 (tabela 207/A/NBP/2026): 1 USD = 3,9247 zł"

# Risk thresholds (%) available on the slider. Denser at low risk, where almost all transactions are
# (99% of honest ones score below ~0.5%).
RISK_STEPS = [0, 0.5, 1, 2, 5, 10, 20, 30, 50, 70, 90, 100]
DEFAULT_THRESHOLDS = (10, 50)  # verify from, block from

# Cost assumptions, editable in the app. They are our assumptions, not market statistics.
DEFAULT_BLOCK_COST = 100.0  # PLN per blocked honest transaction (hotline call, lost sale, annoyed customer)
DEFAULT_VERIFY_COST = 5.0  # PLN per verification (SMS / 3-D Secure, customer inconvenience)
DEFAULT_VERIFY_EFFICACY = 0.9  # share of fraud attempts stopped by verification
