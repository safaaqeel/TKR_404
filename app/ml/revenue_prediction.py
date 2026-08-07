"""
Revenue / profit forecasting via Prophet.
Powers: Dashboard 'Revenue Trend' chart, Growth Agent, What-if Simulator baseline.
"""
import pandas as pd
from typing import Dict


def forecast_revenue(history_df: pd.DataFrame, periods: int = 90) -> Dict:
    """
    history_df must have columns ['ds', 'y'] (date, revenue) per Prophet convention.
    Returns forecast points plus upper/lower confidence bounds for charting.
    """
    from prophet import Prophet

    model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True)
    model.fit(history_df)

    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)

    return {
        "dates": forecast["ds"].dt.strftime("%Y-%m-%d").tolist()[-periods:],
        "predicted": forecast["yhat"].tolist()[-periods:],
        "lower_bound": forecast["yhat_lower"].tolist()[-periods:],
        "upper_bound": forecast["yhat_upper"].tolist()[-periods:],
    }
