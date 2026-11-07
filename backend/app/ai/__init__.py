"""AI modules used by the intelligence endpoints.

Each is a pure function over plain dicts — no database access — so they can be
unit-tested without a connection and reused from any route.
"""

from .ai_query_engine import answer_query
from .anomaly_detector import detect_anomalies
from .forecast_engine import forecast_depletion, generate_time_series_forecast
from .insight_generator import generate_insights
from .nlp_engine import understand_request
from .recommendation_engine import recommend_provider
from .risk_predictor import predict_zone_risks
from .simulation_engine import run_simulation

__all__ = [
    "answer_query", "detect_anomalies", "forecast_depletion",
    "generate_time_series_forecast", "generate_insights", "understand_request",
    "recommend_provider", "predict_zone_risks", "run_simulation",
]
