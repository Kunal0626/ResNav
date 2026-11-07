"""
AI Module 4 — Disaster Risk Prediction
========================================
Predicts which zones/regions will require resources soon.

Inputs: historical request counts, demand trends, population impact,
        disaster category.
Output: risk score per region with explanation.
"""



# ---------------------------------------------------------------------------
# Disaster category weights
# ---------------------------------------------------------------------------
DISASTER_WEIGHTS = {
    "flood": 1.8,
    "cyclone": 1.7,
    "earthquake": 2.0,
    "drought": 1.3,
    "heatwave": 1.2,
    "landslide": 1.5,
    "pandemic": 1.6,
    "unknown": 1.0,
}


def predict_zone_risks(zones: list) -> dict:
    """
    Predict risk scores for each zone/region.

    Args:
        zones: list of dicts, each with:
            zone_name: str
            total_requests: int
            pending_requests: int
            population_affected: int
            avg_severity: float (1-5)
            disaster_category: str (flood/cyclone/earthquake/...)
            stock_shortage_ratio: float (0-1, 1 = fully stocked)
            recent_request_trend: float (positive = increasing demand)

    Returns:
        {
            "zone_risks": [
                {
                    "zone_name": str,
                    "risk_score": float (0-100),
                    "risk_level": "Critical" | "High" | "Medium" | "Low",
                    "contributing_factors": [str],
                    "explanation": str,
                },
                ...
            ],
            "highest_risk_zone": str,
            "summary": str,
            "explanation": str,
        }
    """
    if not zones:
        return {
            "zone_risks": [],
            "highest_risk_zone": None,
            "summary": "No zone data available for risk prediction.",
            "explanation": "Risk prediction requires zone-level data including request counts, severity, and stock levels.",
        }

    results = []

    for z in zones:
        name = z.get("zone_name", "Unknown Zone")
        total_req = int(z.get("total_requests", 0))
        pending = int(z.get("pending_requests", 0))
        population = int(z.get("population_affected", 0))
        severity = float(z.get("avg_severity", 1.0))
        disaster = z.get("disaster_category", "unknown").lower()
        shortage = float(z.get("stock_shortage_ratio", 0.5))
        trend = float(z.get("recent_request_trend", 0.0))

        disaster_w = DISASTER_WEIGHTS.get(disaster, 1.0)

        # Weighted risk score computation
        # Components (normalized to 0-1 roughly):
        pending_factor = min(1.0, pending / max(1, total_req + 1))        # ratio of pending
        severity_factor = min(1.0, severity / 5.0)                        # severity normalized
        shortage_factor = 1.0 - min(1.0, max(0.0, shortage))             # inverted: high shortage = high risk
        population_factor = min(1.0, population / 10000) if population > 0 else 0.1
        trend_factor = min(1.0, max(0.0, trend / 5.0))                   # rising demand

        raw_score = (
            0.25 * pending_factor
            + 0.20 * severity_factor
            + 0.20 * shortage_factor
            + 0.15 * population_factor
            + 0.10 * trend_factor
            + 0.10 * (disaster_w / 2.0)  # normalized disaster weight
        )

        risk_score = round(min(100, raw_score * 100), 1)

        # Risk level
        if risk_score > 70:
            risk_level = "Critical"
        elif risk_score > 50:
            risk_level = "High"
        elif risk_score > 30:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Contributing factors for explanation
        factors = []
        if pending_factor > 0.5:
            factors.append(f"high pending request ratio ({pending}/{total_req})")
        if severity_factor > 0.6:
            factors.append(f"high average severity ({severity:.1f}/5)")
        if shortage_factor > 0.5:
            factors.append(f"significant stock shortage ({shortage_factor:.0%} depleted)")
        if population_factor > 0.3:
            factors.append(f"large affected population ({population:,})")
        if trend_factor > 0.3:
            factors.append(f"rising demand trend (+{trend:.1f})")
        if disaster_w > 1.3:
            factors.append(f"{disaster} disaster multiplier ({disaster_w}x)")
        if not factors:
            factors.append("all indicators within normal range")

        explanation = (
            f"Zone '{name}' risk score: {risk_score}/100 ({risk_level}). "
            f"Contributing factors: {'; '.join(factors)}. "
            f"Score computed as weighted sum of pending ratio, severity, "
            f"stock shortage, population impact, demand trend, and disaster type."
        )

        results.append({
            "zone_name": name,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "contributing_factors": factors,
            "explanation": explanation,
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)
    highest = results[0]["zone_name"] if results else None

    critical_count = sum(1 for r in results if r["risk_level"] == "Critical")
    high_count = sum(1 for r in results if r["risk_level"] == "High")

    summary = (
        f"{len(results)} zones analyzed. "
        f"{critical_count} critical, {high_count} high risk. "
        f"Highest risk: {highest}."
    )

    return {
        "zone_risks": results,
        "highest_risk_zone": highest,
        "summary": summary,
        "explanation": (
            "Risk prediction uses weighted factor model combining pending requests, "
            "severity levels, stock shortage ratios, population impact, demand trends, "
            "and disaster type multipliers. Weights: pending=0.25, severity=0.20, "
            "shortage=0.20, population=0.15, trend=0.10, disaster=0.10."
        ),
    }
