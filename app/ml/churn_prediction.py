"""
Customer churn prediction. Powers: Business Health 'Customer Satisfaction'
drill-down, Growth Agent retention recommendations.
"""
from typing import Dict
import pandas as pd


def predict_churn_risk(customer_df: pd.DataFrame, model, scaler) -> Dict:
    """
    customer_df: one row per customer with recency/frequency/monetary features.
    Returns per-customer churn probability plus an aggregate at-risk percentage.
    """
    feature_cols = [c for c in customer_df.columns if c != "customer_id"]
    X = scaler.transform(customer_df[feature_cols])
    probabilities = model.predict_proba(X)[:, 1]

    customer_df = customer_df.copy()
    customer_df["churn_probability"] = probabilities

    at_risk = customer_df[customer_df["churn_probability"] > 0.5]

    return {
        "at_risk_count": len(at_risk),
        "at_risk_percentage": round(len(at_risk) / max(len(customer_df), 1) * 100, 1),
        "top_at_risk": at_risk.sort_values("churn_probability", ascending=False).head(10).to_dict(orient="records"),
    }
