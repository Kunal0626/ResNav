"""
AI Module 6 — Natural Language Query Engine
=============================================
Allows users to ask questions in natural language.

Examples:
  "Which zone needs medicine urgently?"
  "Which provider has highest success rate?"

Converts query into data analysis using NLP. Returns summarized answer.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Query templates — each maps to a data analysis function
# ---------------------------------------------------------------------------
QUERY_TEMPLATES = [
    {
        "id": "zone_urgent_resource",
        "patterns": [
            "Which zone needs medicine urgently",
            "What area requires resources most",
            "Where is the highest demand for supplies",
            "Which region needs help urgently",
            "Most critical zone for resource allocation",
        ],
        "handler": "_handle_zone_urgent",
        "description": "Finds the zone with most urgent need for a specific resource",
    },
    {
        "id": "provider_success_rate",
        "patterns": [
            "Which provider has highest success rate",
            "Best performing provider",
            "Most reliable resource provider",
            "Provider with best allocation record",
            "Top provider by success",
        ],
        "handler": "_handle_provider_success",
        "description": "Identifies the provider with the best success rate",
    },
    {
        "id": "stock_status",
        "patterns": [
            "What is the current stock level",
            "How much resource is available",
            "Stock status for supplies",
            "Resource availability check",
            "Current inventory levels",
        ],
        "handler": "_handle_stock_status",
        "description": "Reports current stock levels across providers",
    },
    {
        "id": "depletion_forecast",
        "patterns": [
            "When will resources run out",
            "Resource depletion prediction",
            "How long until stock is empty",
            "Forecast supply shortage",
            "Days until stock depletion",
        ],
        "handler": "_handle_depletion_forecast",
        "description": "Predicts when resources will deplete",
    },
    {
        "id": "anomaly_report",
        "patterns": [
            "Any unusual activity detected",
            "Anomalies in resource demand",
            "Unusual patterns in supply",
            "Detect abnormal resource usage",
            "Report anomalies",
        ],
        "handler": "_handle_anomaly_report",
        "description": "Reports detected anomalies in resource patterns",
    },
    {
        "id": "risk_assessment",
        "patterns": [
            "What is the risk level",
            "Zone risk assessment",
            "Which zones are at risk",
            "Risk distribution across regions",
            "Disaster risk levels",
        ],
        "handler": "_handle_risk_assessment",
        "description": "Provides risk assessment across zones",
    },
]

# Pre-computed embeddings cache
_template_embeddings = None
_template_ids = None
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _model = None
    return _model


def _build_template_embeddings():
    """Pre-compute embeddings for all query template patterns."""
    global _template_embeddings, _template_ids
    model = _get_model()
    if model is None:
        return

    all_patterns = []
    all_ids = []
    for tmpl in QUERY_TEMPLATES:
        for pattern in tmpl["patterns"]:
            all_patterns.append(pattern)
            all_ids.append(tmpl["id"])

    _template_embeddings = model.encode(all_patterns, convert_to_numpy=True)
    _template_ids = all_ids


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------
def _handle_zone_urgent(context: dict) -> dict:
    zones = context.get("zones", [])
    if not zones:
        return {"answer": "No zone data available to determine urgent needs.", "data": []}

    # Find zone with highest pending/severity
    scored = []
    for z in zones:
        score = (
            int(z.get("pending_requests", 0)) * 2
            + float(z.get("avg_severity", 1)) * 3
            + int(z.get("population_affected", 0)) / 1000
        )
        scored.append((z, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[0][0]

    return {
        "answer": f"'{top.get('zone_name', 'Unknown')}' has the most urgent resource needs "
                  f"with {top.get('pending_requests', 0)} pending requests and "
                  f"severity level {top.get('avg_severity', 'N/A')}.",
        "data": [{"zone": s[0].get("zone_name"), "urgency_score": round(s[1], 1)} for s in scored[:5]],
    }


def _handle_provider_success(context: dict) -> dict:
    providers = context.get("providers", [])
    if not providers:
        return {"answer": "No provider performance data available.", "data": []}

    sorted_p = sorted(providers, key=lambda p: float(p.get("success_rate", 0)), reverse=True)
    top = sorted_p[0]

    return {
        "answer": f"'{top.get('name', 'Unknown')}' has the highest success rate "
                  f"at {float(top.get('success_rate', 0)):.0%} with "
                  f"{top.get('total_allocations', 0)} total allocations.",
        "data": [{"provider": p.get("name"), "success_rate": p.get("success_rate")} for p in sorted_p[:5]],
    }


def _handle_stock_status(context: dict) -> dict:
    stock = context.get("stock_levels", [])
    if not stock:
        return {"answer": "No stock data available.", "data": []}

    total = sum(float(s.get("quantity", 0)) for s in stock)
    low_stock = [s for s in stock if float(s.get("quantity", 0)) < float(s.get("threshold", 100))]

    return {
        "answer": f"Total stock across all providers: {total:,.0f} units. "
                  f"{len(low_stock)} items are below low-stock threshold.",
        "data": [{"provider": s.get("provider"), "resource": s.get("resource"),
                  "quantity": s.get("quantity")} for s in sorted(stock, key=lambda x: float(x.get("quantity", 0)))[:10]],
    }


def _handle_depletion_forecast(context: dict) -> dict:
    forecasts = context.get("forecasts", [])
    if not forecasts:
        return {"answer": "No forecast data available. Run resource forecasting first.", "data": []}

    critical = [f for f in forecasts if isinstance(f.get("days_until_depletion"), (int, float)) and f["days_until_depletion"] < 7]

    if critical:
        names = ", ".join([f"{f['resource']} at {f['provider']}" for f in critical[:3]])
        return {
            "answer": f"{len(critical)} resources at critical depletion risk (< 7 days): {names}.",
            "data": critical[:5],
        }
    return {
        "answer": "No resources are at critical depletion risk currently.",
        "data": forecasts[:5],
    }


def _handle_anomaly_report(context: dict) -> dict:
    anomalies = context.get("anomalies", [])
    if not anomalies:
        return {"answer": "No anomalies detected in current data.", "data": []}

    high = [a for a in anomalies if a.get("severity") == "high"]
    return {
        "answer": f"{len(anomalies)} anomalies detected ({len(high)} high severity). "
                  + (anomalies[0].get("description", "") if anomalies else ""),
        "data": anomalies[:5],
    }


def _handle_risk_assessment(context: dict) -> dict:
    risks = context.get("zone_risks", [])
    if not risks:
        return {"answer": "No risk assessment data available.", "data": []}

    critical = [r for r in risks if r.get("risk_level") == "Critical"]
    top = risks[0] if risks else {}

    return {
        "answer": f"{len(critical)} zones at critical risk. "
                  f"Highest risk: '{top.get('zone_name', 'Unknown')}' "
                  f"with score {top.get('risk_score', 0)}/100.",
        "data": risks[:5],
    }


# Handler dispatch
_HANDLERS = {
    "zone_urgent_resource": _handle_zone_urgent,
    "provider_success_rate": _handle_provider_success,
    "stock_status": _handle_stock_status,
    "depletion_forecast": _handle_depletion_forecast,
    "anomaly_report": _handle_anomaly_report,
    "risk_assessment": _handle_risk_assessment,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def answer_query(query: str, context: dict) -> dict:
    """
    Convert a natural language question into a data-driven answer.

    Args:
        query: user's free-text question
        context: dict with available data:
            zones, providers, stock_levels, forecasts, anomalies, zone_risks

    Returns:
        {
            "query": str,
            "matched_template": str,
            "match_confidence": float,
            "answer": str,
            "data": list | dict,
            "explanation": str,
        }
    """
    if not query or not query.strip():
        return {
            "query": "",
            "matched_template": None,
            "match_confidence": 0.0,
            "answer": "Please provide a question to analyze.",
            "data": [],
            "explanation": "Empty query — no analysis performed.",
        }

    query_clean = query.strip()
    model = _get_model()

    matched_id = None
    match_confidence = 0.0

    if model is not None:
        if _template_embeddings is None:
            _build_template_embeddings()

        if _template_embeddings is not None:
            query_emb = model.encode([query_clean], convert_to_numpy=True)[0]
            sims = np.dot(_template_embeddings, query_emb) / (
                np.linalg.norm(_template_embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-9
            )
            best_idx = int(np.argmax(sims))
            match_confidence = round(float(sims[best_idx]), 4)
            matched_id = _template_ids[best_idx]
    else:
        # Keyword fallback
        query_lower = query_clean.lower()
        best_score = 0
        for tmpl in QUERY_TEMPLATES:
            for pattern in tmpl["patterns"]:
                words = set(pattern.lower().split())
                query_words = set(query_lower.split())
                overlap = len(words & query_words) / max(len(words), 1)
                if overlap > best_score:
                    best_score = overlap
                    matched_id = tmpl["id"]
                    match_confidence = round(overlap, 4)

    if matched_id and match_confidence > 0.3:
        handler = _HANDLERS.get(matched_id)
        if handler:
            result = handler(context)
            template_desc = next(
                (t["description"] for t in QUERY_TEMPLATES if t["id"] == matched_id), ""
            )
            return {
                "query": query_clean,
                "matched_template": matched_id,
                "match_confidence": match_confidence,
                "answer": result.get("answer", "No answer generated."),
                "data": result.get("data", []),
                "explanation": (
                    f"Query matched to template '{matched_id}' ({template_desc}) "
                    f"with {match_confidence:.0%} confidence using "
                    f"{'Sentence-Transformer semantic similarity' if model else 'keyword matching'}. "
                    f"Result derived from available context data."
                ),
            }

    return {
        "query": query_clean,
        "matched_template": None,
        "match_confidence": match_confidence,
        "answer": (
            "I couldn't find a specific analysis for your question. "
            "Try asking about zone urgency, provider success rates, stock levels, "
            "depletion forecasts, anomalies, or risk assessments."
        ),
        "data": [],
        "explanation": (
            f"No query template exceeded the 30% confidence threshold. "
            f"Best match confidence: {match_confidence:.0%}. "
            f"Supported queries: zone urgency, provider success, stock status, "
            f"depletion forecast, anomaly detection, risk assessment."
        ),
    }
