"""
Fraud / anomalous transaction detection via Isolation Forest.
Powers: Compliance Agent alerts, Risk Agent secondary signal, Reports 'Risk Report'.
"""
from typing import Dict, List
import pandas as pd


def detect_anomalies(transactions_df: pd.DataFrame, model) -> Dict:
    """
    transactions_df: rows of transaction-level data (amount, category, time_delta, etc.)
    Returns flagged transaction indices with anomaly scores.
    Isolation Forest outputs -1 for anomalies, 1 for normal.
    """
    feature_cols = [c for c in transactions_df.columns if c not in ("id", "date", "description")]
    predictions = model.predict(transactions_df[feature_cols])
    scores = model.decision_function(transactions_df[feature_cols])

    flagged = transactions_df[predictions == -1].copy()
    flagged["anomaly_score"] = scores[predictions == -1]

    return {
        "flagged_count": len(flagged),
        "flagged_transactions": flagged.to_dict(orient="records"),
    }
