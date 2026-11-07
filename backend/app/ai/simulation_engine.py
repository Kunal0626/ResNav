"""
AI Module 7 — AI Relief Simulation Engine + Module 8 — Insight Generator
=========================================================================
Monte Carlo simulation for disaster scenarios.

User selects: Flood, Cyclone, Earthquake.
AI predicts: resource demand, supply shortages, recommended allocations.

Also generates auto-insights (Module 8):
  "Delhi Relief Zone likely to run out of water in 2 days."
  "Medical supplies demand rising in coastal regions."
"""

import numpy as np

# ---------------------------------------------------------------------------
# Disaster scenario profiles
# ---------------------------------------------------------------------------
DISASTER_PROFILES = {
    "flood": {
        "name": "Flood",
        "description": "Major flooding event affecting low-lying areas",
        "resource_multipliers": {
            "water": 2.5, "food": 2.0, "medicine": 1.8,
            "shelter": 3.0, "clothing": 1.5, "rescue_equipment": 2.8,
            "sanitation": 2.2,
        },
        "duration_days": (7, 21),
        "affected_population_pct": (0.05, 0.25),
        "supply_chain_disruption": 0.4,
    },
    "cyclone": {
        "name": "Cyclone",
        "description": "Severe cyclonic storm with high wind and rain",
        "resource_multipliers": {
            "water": 2.0, "food": 2.2, "medicine": 2.0,
            "shelter": 3.5, "clothing": 2.0, "rescue_equipment": 3.0,
            "sanitation": 1.8,
        },
        "duration_days": (3, 14),
        "affected_population_pct": (0.08, 0.30),
        "supply_chain_disruption": 0.5,
    },
    "earthquake": {
        "name": "Earthquake",
        "description": "Seismic event causing structural damage",
        "resource_multipliers": {
            "water": 1.8, "food": 1.5, "medicine": 3.0,
            "shelter": 4.0, "clothing": 1.2, "rescue_equipment": 3.5,
            "sanitation": 2.5,
        },
        "duration_days": (1, 30),
        "affected_population_pct": (0.03, 0.20),
        "supply_chain_disruption": 0.6,
    },
    "drought": {
        "name": "Drought",
        "description": "Extended dry period causing water and food scarcity",
        "resource_multipliers": {
            "water": 4.0, "food": 2.5, "medicine": 1.3,
            "shelter": 1.0, "clothing": 1.0, "rescue_equipment": 1.0,
            "sanitation": 1.5,
        },
        "duration_days": (30, 120),
        "affected_population_pct": (0.10, 0.40),
        "supply_chain_disruption": 0.2,
    },
    "heatwave": {
        "name": "Heatwave",
        "description": "Extreme heat event affecting health and resources",
        "resource_multipliers": {
            "water": 3.0, "food": 1.3, "medicine": 2.0,
            "shelter": 1.5, "clothing": 1.0, "rescue_equipment": 1.2,
            "sanitation": 1.8,
        },
        "duration_days": (5, 30),
        "affected_population_pct": (0.05, 0.20),
        "supply_chain_disruption": 0.15,
    },
}


# ---------------------------------------------------------------------------
# Monte Carlo Simulation
# ---------------------------------------------------------------------------
def run_simulation(
    scenario: str,
    current_stock: dict = None,
    population: int = 100000,
    num_simulations: int = 1000,
) -> dict:
    """
    Run Monte Carlo simulation for a disaster scenario.

    Args:
        scenario: "flood" | "cyclone" | "earthquake" | "drought" | "heatwave"
        current_stock: dict {resource_name: quantity} for current inventory
        population: total population in affected area
        num_simulations: number of Monte Carlo iterations

    Returns:
        {
            "scenario": str,
            "scenario_description": str,
            "demand_forecast": { resource: { mean, p50, p90, p95 } },
            "shortages": [ { resource, shortage_amount, shortage_probability } ],
            "recommended_allocations": [ { resource, recommended_qty, priority } ],
            "simulation_stats": { iterations, duration_range, population },
            "insights": [str],
            "explanation": str,
        }
    """
    scenario = scenario.lower().strip()
    profile = DISASTER_PROFILES.get(scenario)

    if not profile:
        return {
            "scenario": scenario,
            "scenario_description": f"Unknown scenario: {scenario}",
            "demand_forecast": {},
            "shortages": [],
            "recommended_allocations": [],
            "simulation_stats": {},
            "insights": [f"Scenario '{scenario}' not recognized. Available: {', '.join(DISASTER_PROFILES.keys())}"],
            "explanation": f"Unknown disaster scenario. Supported: {', '.join(DISASTER_PROFILES.keys())}.",
        }

    if current_stock is None:
        current_stock = {
            "water": 5000, "food": 4000, "medicine": 2000,
            "shelter": 1500, "clothing": 1000, "rescue_equipment": 800,
            "sanitation": 1200,
        }

    rng = np.random.RandomState(42)
    duration_min, duration_max = profile["duration_days"]
    pop_pct_min, pop_pct_max = profile["affected_population_pct"]
    disruption = profile["supply_chain_disruption"]

    demand_results = {res: [] for res in profile["resource_multipliers"]}

    for _ in range(num_simulations):
        duration = rng.uniform(duration_min, duration_max)
        affected_pct = rng.uniform(pop_pct_min, pop_pct_max)
        affected_pop = population * affected_pct

        # Supply chain disruption adds uncertainty
        disruption_factor = 1.0 + rng.uniform(0, disruption)

        for resource, multiplier in profile["resource_multipliers"].items():
            # Base demand per person per day (simplified)
            base_demand_per_person = 0.5  # units
            daily_demand = affected_pop * base_demand_per_person * multiplier
            total_demand = daily_demand * duration * disruption_factor
            demand_results[resource].append(total_demand)

    # Aggregate simulation results
    demand_forecast = {}
    shortages = []
    recommended_allocations = []

    for resource, demands in demand_results.items():
        arr = np.array(demands)
        mean_d = float(np.mean(arr))
        p50 = float(np.percentile(arr, 50))
        p90 = float(np.percentile(arr, 90))
        p95 = float(np.percentile(arr, 95))

        demand_forecast[resource] = {
            "mean": round(mean_d),
            "median": round(p50),
            "p90": round(p90),
            "p95": round(p95),
        }

        # Check shortage against current stock
        stock = current_stock.get(resource, 0)
        shortage_prob = float(np.mean(arr > stock)) * 100

        if shortage_prob > 10:
            shortage_amount = max(0, round(p90 - stock))
            shortages.append({
                "resource": resource,
                "current_stock": stock,
                "projected_demand_p90": round(p90),
                "shortage_amount": shortage_amount,
                "shortage_probability": round(shortage_prob, 1),
                "explanation": (
                    f"{resource}: {shortage_prob:.0f}% chance of shortage. "
                    f"Current stock: {stock:,.0f}, P90 demand: {p90:,.0f}. "
                    f"Potential shortfall: {shortage_amount:,.0f} units."
                ),
            })

        # Recommended allocation (P90 coverage)
        recommended = max(0, round(p90 - stock))
        priority = "critical" if shortage_prob > 70 else ("high" if shortage_prob > 40 else "medium" if shortage_prob > 10 else "low")
        recommended_allocations.append({
            "resource": resource,
            "recommended_qty": recommended,
            "priority": priority,
            "coverage_target": "P90",
            "explanation": f"Allocate {recommended:,} units of {resource} to achieve P90 coverage under {profile['name']} scenario.",
        })

    shortages.sort(key=lambda x: x["shortage_probability"], reverse=True)
    recommended_allocations.sort(key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 4))

    # Generate insights
    insights = _generate_simulation_insights(profile, demand_forecast, shortages, population)

    explanation = (
        f"Monte Carlo simulation with {num_simulations} iterations for {profile['name']} scenario. "
        f"Affected population range: {pop_pct_min:.0%}-{pop_pct_max:.0%} of {population:,}. "
        f"Duration range: {duration_min}-{duration_max} days. "
        f"Supply chain disruption factor: up to {disruption:.0%}. "
        f"Demand based on per-capita daily need × resource-specific multiplier × disruption."
    )

    return {
        "scenario": profile["name"],
        "scenario_description": profile["description"],
        "demand_forecast": demand_forecast,
        "shortages": shortages,
        "recommended_allocations": recommended_allocations,
        "simulation_stats": {
            "iterations": num_simulations,
            "duration_range": f"{duration_min}-{duration_max} days",
            "population": population,
            "supply_chain_disruption": f"up to {disruption:.0%}",
        },
        "insights": insights,
        "explanation": explanation,
    }


def _generate_simulation_insights(profile, demand_forecast, shortages, population):
    """Generate context-aware insights from simulation results."""
    insights = []
    name = profile["name"]

    # Critical shortages
    critical = [s for s in shortages if s["shortage_probability"] > 70]
    if critical:
        resources = ", ".join([s["resource"] for s in critical])
        insights.append(
            f"CRITICAL: {len(critical)} resources ({resources}) have >70% shortage "
            f"probability under {name} scenario. Immediate pre-positioning required."
        )

    # Highest demand resource
    if demand_forecast:
        max_resource = max(demand_forecast.items(), key=lambda x: x[1]["p90"])
        insights.append(
            f"Highest demand: {max_resource[0]} with projected P90 requirement of "
            f"{max_resource[1]['p90']:,} units during {name}."
        )

    # Population impact
    pop_range = profile["affected_population_pct"]
    avg_affected = population * (pop_range[0] + pop_range[1]) / 2
    insights.append(
        f"Estimated {avg_affected:,.0f} people affected on average "
        f"({pop_range[0]:.0%}-{pop_range[1]:.0%} of population)."
    )

    # Supply chain warning
    disruption = profile["supply_chain_disruption"]
    if disruption > 0.3:
        insights.append(
            f"Supply chain disruption expected: up to {disruption:.0%} increase "
            f"in logistics costs and delays during {name}."
        )

    return insights


# ---------------------------------------------------------------------------
# Module 8: AI Insight Generator (integrated)
# ---------------------------------------------------------------------------
def generate_insights(
    forecasts: list = None,
    zone_risks: list = None,
    anomalies: list = None,
    stock_levels: list = None,
) -> dict:
    """
    Automatically generate actionable insights from AI analysis results.

    Args:
        forecasts: list of forecast dicts from forecast_engine
        zone_risks: list of zone risk dicts from risk_predictor
        anomalies: list of anomaly dicts from anomaly_detector
        stock_levels: list of stock level dicts

    Returns:
        {
            "insights": [
                {
                    "message": str,
                    "category": "forecast" | "risk" | "anomaly" | "stock",
                    "severity": "critical" | "warning" | "info",
                    "explanation": str,
                },
                ...
            ],
            "summary": str,
            "explanation": str,
        }
    """
    insights = []

    # ── Forecast-based insights ──
    if forecasts:
        critical_depletions = [
            f for f in forecasts
            if isinstance(f.get("days_until_depletion"), (int, float))
            and f["days_until_depletion"] < 7
        ]
        for f in critical_depletions[:3]:
            insights.append({
                "message": f"{f.get('provider', 'Unknown')} likely to run out of "
                           f"{f.get('resource', 'resources')} in {f['days_until_depletion']:.0f} days.",
                "category": "forecast",
                "severity": "critical" if f["days_until_depletion"] < 3 else "warning",
                "explanation": f"Based on linear regression: daily consumption rate = "
                               f"{f.get('daily_consumption_rate', 'N/A')} units/day, "
                               f"current stock = {f.get('current_stock', 'N/A')}.",
            })

        rising = [f for f in forecasts if f.get("trend") == "declining" and f.get("shortage_probability_pct", 0) > 50]
        if rising:
            res_names = ", ".join(set(f.get("resource", "?") for f in rising[:3]))
            insights.append({
                "message": f"Demand rising for {res_names} — shortage probability exceeds 50%.",
                "category": "forecast",
                "severity": "warning",
                "explanation": "Multiple resource/provider pairs show declining stock trends with >50% shortage probability.",
            })

    # ── Risk-based insights ──
    if zone_risks:
        critical_zones = [z for z in zone_risks if z.get("risk_level") == "Critical"]
        for z in critical_zones[:2]:
            insights.append({
                "message": f"Zone '{z.get('zone_name', 'Unknown')}' at critical risk "
                           f"(score: {z.get('risk_score', 0)}/100). Immediate attention required.",
                "category": "risk",
                "severity": "critical",
                "explanation": f"Contributing factors: {'; '.join(z.get('contributing_factors', []))}",
            })

    # ── Anomaly-based insights ──
    if anomalies:
        high_anomalies = [a for a in anomalies if a.get("severity") == "high"]
        for a in high_anomalies[:3]:
            insights.append({
                "message": a.get("description", "Anomaly detected."),
                "category": "anomaly",
                "severity": "warning",
                "explanation": a.get("explanation", "Detected by anomaly detection system."),
            })

    # ── Stock-based insights ──
    if stock_levels:
        low = [s for s in stock_levels if float(s.get("quantity", 999)) < float(s.get("threshold", 100))]
        if low:
            names = ", ".join(set(s.get("resource", "?") for s in low[:3]))
            insights.append({
                "message": f"{len(low)} stock items below threshold. Affected: {names}.",
                "category": "stock",
                "severity": "warning" if len(low) < 5 else "critical",
                "explanation": f"Stock levels compared against low-stock thresholds. {len(low)} items require replenishment.",
            })

    # If no data at all, provide a default insight
    if not insights:
        insights.append({
            "message": "All systems operating within normal parameters. No critical issues detected.",
            "category": "info",
            "severity": "info",
            "explanation": "No forecast, risk, anomaly, or stock alerts triggered.",
        })

    critical_count = sum(1 for i in insights if i["severity"] == "critical")
    warning_count = sum(1 for i in insights if i["severity"] == "warning")

    return {
        "insights": insights,
        "summary": f"{len(insights)} insights generated ({critical_count} critical, {warning_count} warnings).",
        "explanation": (
            "Insights auto-generated from AI module outputs: forecast depletion predictions, "
            "zone risk assessments, anomaly detection alerts, and stock level monitoring. "
            "Uses rule-based summarization combined with model predictions."
        ),
    }
