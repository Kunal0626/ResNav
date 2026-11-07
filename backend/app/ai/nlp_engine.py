"""
AI Module 1 — Semantic NLP Request Understanding
=================================================
Replaces rule-based keyword detection with semantic NLP.
Uses Sentence-Transformers (all-MiniLM-L6-v2).

Process: User text → embedding → cosine similarity → resource category.
Includes confidence score and explainable reasoning.
"""

import re

import numpy as np

# ---------------------------------------------------------------------------
# Lazy model loader (shared with services/nlp_engine.py if available)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Resource category definitions with semantic descriptions
# ---------------------------------------------------------------------------
RESOURCE_CATEGORIES = {
    "water": {
        "keywords": ["water", "drinking water", "clean water", "water supply",
                      "water packets", "hydration", "purified water"],
        "description": "Water supply and purification resources",
        "intents": ["disaster relief", "daily supply", "emergency hydration"],
    },
    "medicine": {
        "keywords": ["medicine", "medical", "first aid", "medical kits",
                      "pharmaceutical", "drugs", "healthcare", "hospital supplies",
                      "antibiotics", "painkillers", "bandages"],
        "description": "Medical supplies and healthcare resources",
        "intents": ["injury treatment", "disease prevention", "emergency care"],
    },
    "food": {
        "keywords": ["food", "rations", "meals", "food packets", "nutrition",
                      "groceries", "rice", "wheat", "dal", "canned food"],
        "description": "Food supplies and nutrition resources",
        "intents": ["hunger relief", "nutritional support", "emergency feeding"],
    },
    "shelter": {
        "keywords": ["shelter", "tarpaulin", "tarpaulins", "tents", "housing",
                      "temporary shelter", "blankets", "bedding", "roof"],
        "description": "Shelter materials and housing resources",
        "intents": ["displacement support", "temporary housing", "weather protection"],
    },
    "clothing": {
        "keywords": ["clothing", "clothes", "garments", "blankets", "warm clothing",
                      "winter wear", "jackets"],
        "description": "Clothing and warmth resources",
        "intents": ["cold protection", "basic needs", "dignity support"],
    },
    "rescue_equipment": {
        "keywords": ["rescue", "boats", "life jackets", "rope", "torches",
                      "flashlights", "generators", "pumps", "equipment"],
        "description": "Rescue and emergency equipment",
        "intents": ["search and rescue", "evacuation", "emergency operations"],
    },
    "sanitation": {
        "keywords": ["sanitation", "hygiene", "soap", "sanitizer", "toilets",
                      "cleaning", "disinfectant", "masks", "gloves"],
        "description": "Sanitation and hygiene supplies",
        "intents": ["disease prevention", "hygiene maintenance", "infection control"],
    },
}

# Pre-compute category label sentences for embedding
_category_sentences = None
_category_keys = None
_category_embeddings = None


def _build_category_embeddings():
    """Pre-compute category embeddings."""
    global _category_sentences, _category_keys, _category_embeddings
    model = _get_model()
    if model is None:
        return

    _category_keys = list(RESOURCE_CATEGORIES.keys())
    _category_sentences = []
    for key in _category_keys:
        cat = RESOURCE_CATEGORIES[key]
        sentence = f"{cat['description']}. Related to: {', '.join(cat['keywords'][:5])}"
        _category_sentences.append(sentence)

    _category_embeddings = model.encode(_category_sentences, convert_to_numpy=True)


# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------
INTENT_LABELS = {
    "disaster_relief_request": "Urgent request for disaster relief supplies",
    "supply_check": "Checking supply availability or stock status",
    "allocation_request": "Requesting allocation of specific resources",
    "status_inquiry": "Inquiring about status of existing requests",
    "provider_search": "Searching for nearby resource providers",
    "general_query": "General information query",
}

_intent_keys = None
_intent_embeddings = None


def _build_intent_embeddings():
    """Pre-compute intent embeddings."""
    global _intent_keys, _intent_embeddings
    model = _get_model()
    if model is None:
        return

    _intent_keys = list(INTENT_LABELS.keys())
    _intent_embeddings = model.encode(
        list(INTENT_LABELS.values()), convert_to_numpy=True
    )


# ---------------------------------------------------------------------------
# Urgency detection
# ---------------------------------------------------------------------------
URGENCY_WORDS = {
    "urgent": 1.8, "emergency": 2.0, "critical": 2.0, "immediately": 1.9,
    "asap": 1.7, "desperate": 1.9, "dying": 2.0, "severe": 1.6,
    "life-threatening": 2.0, "flood": 1.5, "earthquake": 1.7,
    "cyclone": 1.7, "disaster": 1.5, "crisis": 1.6,
}


def _compute_urgency(text: str) -> float:
    """Compute urgency score (1.0–2.0) from keyword weights."""
    words = text.lower().split()
    scores = [URGENCY_WORDS[w] for w in words if w in URGENCY_WORDS]
    if not scores:
        return 1.0
    return min(2.0, max(scores))


def _extract_quantity(text: str):
    """Extract numeric quantity from text."""
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:units?|packets?|kits?|kg|liters?|litres?|tons?|boxes?)?', text, re.I)
    return float(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Main API: understand_request
# ---------------------------------------------------------------------------
def understand_request(text: str) -> dict:
    """
    Semantic NLP Request Understanding.

    Process: text → embedding → cosine similarity → resource categories + intent.

    Returns:
        {
            "input_text": str,
            "resources": [{"category": str, "confidence": float, "description": str}],
            "intent": str,
            "intent_confidence": float,
            "urgency_score": float,
            "quantity": float | None,
            "confidence": float,         # overall confidence
            "explanation": str,           # Explainable AI (Module 10)
        }
    """
    if not text or not text.strip():
        return {
            "input_text": "",
            "resources": [],
            "intent": "general_query",
            "intent_confidence": 0.0,
            "urgency_score": 1.0,
            "quantity": None,
            "confidence": 0.0,
            "explanation": "Empty input — no analysis possible.",
        }

    model = _get_model()
    text_clean = text.strip()

    # Urgency + quantity extraction (works without model)
    urgency = _compute_urgency(text_clean)
    quantity = _extract_quantity(text_clean)

    # ── Transformer-based semantic matching ──
    if model is not None:
        # Ensure embeddings are built
        if _category_embeddings is None:
            _build_category_embeddings()
        if _intent_embeddings is None:
            _build_intent_embeddings()

        query_emb = model.encode([text_clean], convert_to_numpy=True)[0]

        # Resource category matching
        resources = []
        if _category_embeddings is not None:
            sims = np.dot(_category_embeddings, query_emb) / (
                np.linalg.norm(_category_embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-9
            )
            for i, sim in enumerate(sims):
                if sim > 0.25:  # threshold
                    resources.append({
                        "category": _category_keys[i],
                        "confidence": round(float(sim), 4),
                        "description": RESOURCE_CATEGORIES[_category_keys[i]]["description"],
                    })
            resources.sort(key=lambda x: x["confidence"], reverse=True)

        # Intent classification
        intent = "general_query"
        intent_conf = 0.0
        if _intent_embeddings is not None:
            intent_sims = np.dot(_intent_embeddings, query_emb) / (
                np.linalg.norm(_intent_embeddings, axis=1) * np.linalg.norm(query_emb) + 1e-9
            )
            best_idx = int(np.argmax(intent_sims))
            intent = _intent_keys[best_idx]
            intent_conf = round(float(intent_sims[best_idx]), 4)

        overall_conf = round(float(resources[0]["confidence"] if resources else intent_conf), 4)

        # Build explanation
        res_str = ", ".join([f"{r['category']} ({r['confidence']:.0%})" for r in resources[:3]]) or "none detected"
        explanation = (
            f"Semantic analysis using Sentence-Transformer embeddings. "
            f"Detected resources: {res_str}. "
            f"Intent classified as '{intent}' with {intent_conf:.0%} confidence. "
            f"Urgency level: {urgency:.1f}/2.0."
        )

        return {
            "input_text": text_clean,
            "resources": resources[:5],
            "intent": intent,
            "intent_confidence": intent_conf,
            "urgency_score": urgency,
            "quantity": quantity,
            "confidence": overall_conf,
            "explanation": explanation,
        }

    # ── Fallback: keyword-based matching (no model) ──
    text_lower = text_clean.lower()
    resources = []
    for key, cat in RESOURCE_CATEGORIES.items():
        matches = sum(1 for kw in cat["keywords"] if kw in text_lower)
        if matches > 0:
            conf = min(0.95, 0.3 + matches * 0.15)
            resources.append({
                "category": key,
                "confidence": round(conf, 4),
                "description": cat["description"],
            })
    resources.sort(key=lambda x: x["confidence"], reverse=True)

    # Keyword intent detection
    intent = "general_query"
    intent_conf = 0.5
    if any(w in text_lower for w in ["need", "require", "want", "send", "provide"]):
        if urgency > 1.3:
            intent = "disaster_relief_request"
            intent_conf = 0.75
        else:
            intent = "allocation_request"
            intent_conf = 0.65

    overall_conf = round(resources[0]["confidence"] if resources else 0.3, 4)
    res_str = ", ".join([r["category"] for r in resources[:3]]) or "none"
    explanation = (
        f"Keyword-based fallback analysis (transformer model not loaded). "
        f"Matched resources: {res_str}. "
        f"Intent inferred as '{intent}'. Urgency: {urgency:.1f}/2.0."
    )

    return {
        "input_text": text_clean,
        "resources": resources[:5],
        "intent": intent,
        "intent_confidence": intent_conf,
        "urgency_score": urgency,
        "quantity": quantity,
        "confidence": overall_conf,
        "explanation": explanation,
    }
