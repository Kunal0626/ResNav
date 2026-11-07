"""
AI Module 2 — Provider Recommendation Engine
=============================================
Recommends the best provider for a resource request using
scikit-learn (RandomForestClassifier / GradientBoosting).

Features: distance, stock_level, historical_success_rate,
           request_urgency, provider_reliability_score.

Output: recommended_provider, confidence_score, reasoning explanation.
"""

import math

import numpy as np

# ---------------------------------------------------------------------------
# Training data synthesis + model cache
# ---------------------------------------------------------------------------
_model = None
_feature_names = [
    "distance_km", "stock_level", "stock_ratio",
    "success_rate", "urgency", "reliability_score",
]


def _train_model():
    """
    Train a RandomForestClassifier on synthetic feature data.
    Target: 1 = good provider, 0 = poor provider.
    Called once, cached globally.
    """
    global _model
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.RandomState(42)
    n = 500

    distance = rng.uniform(1, 200, n)
    stock = rng.uniform(0, 2000, n)
    stock_ratio = rng.uniform(0, 1, n)
    success_rate = rng.uniform(0.2, 1.0, n)
    urgency = rng.uniform(1.0, 3.0, n)
    reliability = rng.uniform(0.3, 1.0, n)

    # Synthetic label: provider is "good" when close, high stock, reliable
    score = (
        0.25 * (1 - distance / 200)
        + 0.25 * stock_ratio
        + 0.20 * success_rate
        + 0.15 * reliability
        + 0.15 * (urgency / 3.0)
    )
    labels = (score > 0.50).astype(int)

    X = np.column_stack([distance, stock, stock_ratio, success_rate, urgency, reliability])
    clf = RandomForestClassifier(n_estimators=80, max_depth=8, random_state=42)
    clf.fit(X, labels)
    _model = clf
    return clf


def _get_model():
    global _model
    if _model is None:
        _train_model()
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend_provider(
    providers: list,
    quantity_requested: float = 1.0,
    urgency: float = 1.0,
    user_lat: float = 28.6,
    user_lon: float = 77.2,
) -> dict:
    """
    AI-powered provider recommendation.

    Args:
        providers: list of dicts, each with keys:
            id, name, city, latitude, longitude, stock_level,
            success_rate (0-1), reliability_score (0-1)
        quantity_requested: how much resource is needed
        urgency: 1.0 – 3.0
        user_lat, user_lon: requester coordinates

    Returns:
        {
            "recommended_provider": { id, name, city, score, ... },
            "all_scored": [ ... sorted by score desc ],
            "confidence_score": int (0-100),
            "explanation": str,
        }
    """
    if not providers:
        return {
            "recommended_provider": None,
            "all_scored": [],
            "confidence_score": 0,
            "explanation": "No providers available for recommendation.",
        }

    clf = _get_model()
    scored = []

    for p in providers:
        plat = float(p.get("latitude", user_lat) or user_lat)
        plon = float(p.get("longitude", user_lon) or user_lon)
        dist_deg = math.hypot(plat - user_lat, plon - user_lon)
        dist_km = dist_deg * 111.0  # rough deg→km

        stock = float(p.get("stock_level", 0))
        stock_ratio = min(1.0, stock / max(1.0, quantity_requested))
        success = float(p.get("success_rate", 0.7))
        reliability = float(p.get("reliability_score", 0.7))
        urg = min(3.0, max(1.0, urgency))

        features = np.array([[dist_km, stock, stock_ratio, success, urg, reliability]])

        # Probability of "good provider"
        prob = float(clf.predict_proba(features)[0][1])

        # Feature importances for this prediction
        importances = clf.feature_importances_

        # Build per-provider reasoning
        reasons = []
        if stock_ratio >= 0.9:
            reasons.append("sufficient stock to fulfill request")
        elif stock_ratio >= 0.5:
            reasons.append("partial stock available")
        else:
            reasons.append("low stock relative to demand")

        if dist_km < 30:
            reasons.append("close proximity to requester")
        elif dist_km < 100:
            reasons.append("moderate distance")
        else:
            reasons.append("far from requester location")

        if success > 0.8:
            reasons.append("strong historical success rate")
        if reliability > 0.8:
            reasons.append("high reliability score")

        scored.append({
            "provider_id": p.get("id"),
            "provider_name": p.get("name", "Unknown"),
            "provider_city": p.get("city", ""),
            "stock_level": stock,
            "distance_km": round(dist_km, 1),
            "success_rate": round(success, 2),
            "reliability_score": round(reliability, 2),
            "ai_score": round(prob, 4),
            "reasoning": "; ".join(reasons),
        })

    scored.sort(key=lambda x: x["ai_score"], reverse=True)
    best = scored[0]
    confidence = min(99, int(best["ai_score"] * 100))

    # Top feature importances for explanation
    top_features_idx = np.argsort(importances)[::-1][:3]
    top_feats = [_feature_names[i] for i in top_features_idx]

    explanation = (
        f"Provider '{best['provider_name']}' recommended with {confidence}% confidence. "
        f"Reasoning: {best['reasoning']}. "
        f"Model used: RandomForestClassifier (80 trees). "
        f"Top predictive features: {', '.join(top_feats)}."
    )

    return {
        "recommended_provider": best,
        "all_scored": scored,
        "confidence_score": confidence,
        "explanation": explanation,
    }
