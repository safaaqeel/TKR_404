"""
Shared feature engineering used by every model in this folder.
Centralized here so revenue_prediction, risk_prediction, churn_prediction
etc. don't each reimplement scaling/encoding slightly differently.
"""
import pandas as pd
import numpy as np
from typing import List


NUMERIC_FEATURES = [
    "revenue", "expenses", "cash_balance", "receivables_days",
    "payables_days", "inventory_turnover", "debt_to_equity",
]


def load_business_dataframe(csv_path: str) -> pd.DataFrame:
    """Load and lightly validate a business financial dataset."""
    df = pd.read_csv(csv_path)
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive standard ratios used across risk/revenue/churn models."""
    out = df.copy()
    if {"revenue", "expenses"}.issubset(out.columns):
        out["gross_margin"] = (out["revenue"] - out["expenses"]) / out["revenue"].replace(0, np.nan)
    if {"cash_balance", "expenses"}.issubset(out.columns):
        out["cash_runway_months"] = out["cash_balance"] / (out["expenses"] / 12).replace(0, np.nan)
    return out.fillna(0)


def scale_features(df: pd.DataFrame, feature_cols: List[str], scaler=None):
    """Apply a pre-fit sklearn scaler (loaded via model_loader) to feature columns."""
    if scaler is None:
        raise ValueError("A fitted scaler must be provided - do not fit at inference time.")
    return scaler.transform(df[feature_cols])
