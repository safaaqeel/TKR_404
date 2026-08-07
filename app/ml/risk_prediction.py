"""
Financial distress risk scoring via XGBoost (app/models/xgboost_model.pkl).
Powers: Dashboard 'Financial Distress Risk' card, Risk Agent, AI Decision Board.
"""
from app.ml.preprocessing import engineer_features, scale_features
from typing import Dict


def predict_risk_score(business_features: Dict, model, scaler) -> Dict:
    """
    Returns a risk score (0-100), risk band (Low/Moderate/High), and the
    top contributing features (for explainability in the UI/agent output).
    """
    import pandas as pd
    df = pd.DataFrame([business_features])
    df = engineer_features(df)

    feature_cols = list(business_features.keys())
    X = scale_features(df, feature_cols, scaler)

    proba = model.predict_proba(X)[0][1]  # probability of "distress" class
    score = round(proba * 100, 1)
    band = "High" if score >= 65 else "Moderate" if score >= 35 else "Low"

    # TODO: use model.feature_importances_ or SHAP for real explainability
    top_factors = sorted(business_features.items(), key=lambda kv: kv[1], reverse=True)[:3]

    return {"risk_score": score, "risk_band": band, "top_factors": top_factors}
