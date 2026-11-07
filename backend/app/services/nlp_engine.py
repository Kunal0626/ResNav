"""ResNav NLP engine — intent classification and semantic provider ranking.

Pipeline (unchanged from the original design):
  1. Preprocess  → lowercase, strip punctuation, expand synonyms
  2. Embed       → pluggable encoder (TF-IDF by default, transformers opt-in)
  3. Intent      → cosine similarity vs. category vectors → best match
  4. Entities    → regex quantity extraction + weighted urgency keywords
  5. Rank        → 0.4×semantic + 0.3×stock + 0.2×proximity + 0.1×urgency

What changed: the encoder is injected rather than imported at call time, and
the vector index is a single cached object instead of three module globals that
could fall out of sync with one another.
"""

import logging
import re
import threading

import numpy as np

from ..core.config import get_settings
from .embeddings import build_encoder, cosine_scores

log = logging.getLogger(__name__)

# Below this cosine similarity the best category is not meaningfully better
# than the runner-up, so we report "unknown" rather than guessing.
MIN_INTENT_CONFIDENCE = 0.25

# Hybrid ranking weights. They sum to 1.0 so `hybrid_score` stays in [0, 1].
W_SEMANTIC, W_STOCK, W_DISTANCE, W_URGENCY = 0.4, 0.3, 0.2, 0.1

# ═══════════════════════════════════════════════════════════════════════
# SYNONYM DICTIONARY — expands user terms to canonical resource language
# ═══════════════════════════════════════════════════════════════════════

SYNONYM_MAP = {
    # Food
    "ration": "food supply", "rations": "food supply", "groceries": "food supply",
    "meals": "food", "rice": "food grain", "wheat": "food grain",
    "dal": "food grain", "bread": "food", "biscuits": "food",
    "hungry": "food needed", "starving": "food emergency",
    # Water
    "drinking water": "clean water supply", "paani": "water",
    "h2o": "water", "purified water": "clean water",
    # Medical
    "meds": "medicine", "medication": "medicine", "drugs": "medicine",
    "doctor": "medical healthcare", "hospital": "medical healthcare",
    "clinic": "medical healthcare", "first aid": "medical emergency",
    "ambulance": "medical emergency", "injury": "medical healthcare",
    "bleeding": "medical emergency", "injured": "medical healthcare",
    # Shelter
    "tent": "shelter temporary housing", "tents": "shelter temporary housing",
    "tarp": "shelter covering", "tarps": "shelter covering",
    "sleeping bag": "shelter bedding", "homeless": "shelter needed",
    "accommodation": "shelter housing", "house": "shelter housing",
    "roof": "shelter housing",
    # Hygiene
    "soap": "hygiene sanitation", "sanitizer": "hygiene sanitation",
    "sanitary pad": "hygiene feminine care", "sanitary pads": "hygiene feminine care",
    "toothbrush": "hygiene dental care", "toothpaste": "hygiene dental care",
    "hygiene kit": "hygiene supplies",
    # Financial
    "cash": "financial aid money", "money": "financial aid",
    "funds": "financial aid", "donation": "financial aid",
    "compensation": "financial aid",
    # Employment
    "job": "employment work", "jobs": "employment work",
    "work": "employment", "livelihood": "employment work",
    "skill training": "employment training",
    # Emergency
    "rescue": "emergency rescue", "evacuate": "emergency evacuation",
    "flood": "disaster flood emergency", "cyclone": "disaster cyclone emergency",
    "earthquake": "disaster earthquake emergency",
    "fire": "disaster fire emergency",
}

# ═══════════════════════════════════════════════════════════════════════
# INTENT DEFINITIONS — semantic descriptions for each category
# These are embedded once and cached. No keyword lists.
# ═══════════════════════════════════════════════════════════════════════

INTENT_DEFINITIONS = {
    "Food": (
        "food supply ration meals rice wheat grain groceries "
        "hunger starvation nutrition cooking distribution feeding"
    ),
    "Medical": (
        "medicine medical doctor hospital clinic healthcare "
        "injury treatment ambulance first aid health pharmacy drugs prescription"
    ),
    "Shelter": (
        "shelter housing tent tarp accommodation camp "
        "homeless temporary roofing building sleeping bedding protection"
    ),
    "Hygiene": (
        "hygiene sanitation soap sanitizer toothbrush toothpaste "
        "sanitary pad kit cleaning wash purification water treatment"
    ),
    "Water": (
        "water drinking clean purified supply distribution "
        "dehydration thirst liquid beverages hydration tanker"
    ),
    "Financial Aid": (
        "financial aid money cash funds donation compensation "
        "bank relief grant insurance monetary assistance"
    ),
    "Employment": (
        "employment job work livelihood training skill "
        "career placement opportunity wage labor hiring"
    ),
    "Emergency": (
        "emergency rescue evacuation disaster flood cyclone "
        "earthquake fire critical urgency immediate danger"
    ),
}

# ═══════════════════════════════════════════════════════════════════════
# URGENCY KEYWORDS — weighted for urgency multiplier (no if/else)
# ═══════════════════════════════════════════════════════════════════════

URGENCY_WEIGHTS = {
    "urgent": 0.3, "urgently": 0.3, "emergency": 0.4, "immediately": 0.35,
    "critical": 0.4, "asap": 0.3, "desperate": 0.35, "dying": 0.5,
    "life-threatening": 0.5, "dire": 0.35, "severe": 0.25,
    "crucial": 0.25, "help": 0.1, "need": 0.05, "required": 0.05,
}

# ═══════════════════════════════════════════════════════════════════════
# QUANTITY EXTRACTION PATTERNS
# ═══════════════════════════════════════════════════════════════════════

QUANTITY_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:kg|kilos?|kilogram)", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:liters?|litres?|ltr)", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:units?|pcs|pieces?|packets?|packs?|boxes?)", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:people|persons?|families|households?)", re.I),
    re.compile(r"(?:for|need|require|want)\s+(\d+(?:\.\d+)?)", re.I),
    re.compile(r"(\d+(?:\.\d+)?)\s+(?:of\s+)?(?:food|water|medicine|shelter|beds?|tents?)", re.I),
    re.compile(r"^(\d+(?:\.\d+)?)\b", re.I),  # leading number
]


# ═══════════════════════════════════════════════════════════════════════
# VECTOR INDEX — encoder + category/provider vectors, built once, reused
# ═══════════════════════════════════════════════════════════════════════


class _VectorIndex:
    """Holds the fitted encoder and the vectors derived from it.

    Category and provider vectors must come from the *same* fitted encoder, so
    they live together and are rebuilt together whenever the provider set
    changes. Keeping them in separate globals (as before) meant a provider
    refresh could leave stale category vectors from a different vocabulary.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._encoder = None
        self._category_names: list[str] = []
        self._category_vectors = None
        self._provider_ids: tuple = ()
        self._provider_vectors = None

    @staticmethod
    def _provider_text(provider: dict) -> str:
        return " ".join(filter(None, (
            provider.get("name", ""),
            provider.get("description", ""),
            provider.get("services_text", ""),
            provider.get("city", ""),
            provider.get("state", ""),
        )))

    def _rebuild(self, providers: list[dict]) -> None:
        settings = get_settings()
        encoder = build_encoder(prefer_transformers=settings.enable_transformers)

        category_names = list(INTENT_DEFINITIONS)
        category_texts = [INTENT_DEFINITIONS[name] for name in category_names]
        provider_texts = [self._provider_text(p) for p in providers]

        # Fit on everything the encoder will ever see, so provider vocabulary is
        # in-vocabulary for the query encoder and vice versa.
        encoder.fit(category_texts + provider_texts + list(SYNONYM_MAP.values()))

        self._encoder = encoder
        self._category_names = category_names
        self._category_vectors = encoder.encode(category_texts)
        self._provider_ids = tuple(p.get("id") for p in providers)
        self._provider_vectors = encoder.encode(provider_texts) if provider_texts else None
        log.info("Vector index built: encoder=%s, %d categories, %d providers.",
                 encoder.name, len(category_names), len(providers))

    def ensure(self, providers: list[dict] | None = None) -> None:
        providers = providers or []
        ids = tuple(p.get("id") for p in providers)
        with self._lock:
            needs_rebuild = self._encoder is None or (providers and ids != self._provider_ids)
            if needs_rebuild:
                self._rebuild(providers)

    def encode_query(self, text: str):
        with self._lock:
            return self._encoder.encode([text])[0]

    @property
    def categories(self):
        return self._category_names, self._category_vectors

    @property
    def provider_vectors(self):
        return self._provider_vectors

    def invalidate(self) -> None:
        with self._lock:
            self._encoder = None
            self._provider_ids = ()
            self._provider_vectors = None


_index = _VectorIndex()


def invalidate_caches() -> None:
    """Drop cached vectors — call after providers or services change."""
    _index.invalidate()


# ═══════════════════════════════════════════════════════════════════════
# PREPROCESSING — synonym expansion, normalization
# ═══════════════════════════════════════════════════════════════════════

def preprocess(text):
    """Lowercase, strip punctuation, expand synonyms."""
    if not text or not isinstance(text, str):
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Synonym expansion: replace known terms with canonical language
    tokens = text.split()
    expanded = []
    i = 0
    while i < len(tokens):
        # Try 3-gram, 2-gram, 1-gram synonym matches
        matched = False
        for n in (3, 2):
            if i + n <= len(tokens):
                phrase = " ".join(tokens[i:i + n])
                if phrase in SYNONYM_MAP:
                    expanded.append(SYNONYM_MAP[phrase])
                    i += n
                    matched = True
                    break
        if not matched:
            token = tokens[i]
            expanded.append(SYNONYM_MAP.get(token, token))
            i += 1

    result = " ".join(expanded)
    return result


# ═══════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION — quantity + urgency (regex, no keyword if/else)
# ═══════════════════════════════════════════════════════════════════════

def extract_quantity(text):
    """Extract numeric quantity from text. Returns float or None."""
    for pattern in QUANTITY_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


def compute_urgency(text):
    """Compute urgency multiplier (1.0–2.0) from keyword weights.
    No if/else — pure weighted sum capped at 2.0."""
    if not text:
        return 1.0
    tokens = set(text.lower().split())
    score = sum(weight for word, weight in URGENCY_WEIGHTS.items() if word in tokens)
    return round(min(2.0, 1.0 + score), 3)


# ═══════════════════════════════════════════════════════════════════════
# SEMANTIC INTENT CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════

def classify_intent(query_text):
    """
    Classify user intent using transformer semantic similarity.
    Returns dict with detected_intent, confidence, top_3 scores, explanation.
    No keyword matching — pure embedding cosine similarity.
    """
    preprocessed = preprocess(query_text)
    if not preprocessed:
        return {
            "detected_intent": "unknown",
            "confidence": 0.0,
            "top_3": [],
            "explanation": "Empty query",
        }

    _index.ensure()
    category_names, category_vectors = _index.categories
    sims = cosine_scores(_index.encode_query(preprocessed), category_vectors)

    scored = [(category_names[i], float(sims[i])) for i in range(len(category_names))]
    scored.sort(key=lambda x: -x[1])

    best_name, best_score = scored[0]
    top_3 = scored[:3]

    if best_score < MIN_INTENT_CONFIDENCE:
        return {
            "detected_intent": "unknown",
            "confidence": round(best_score, 4),
            "top_3": [(n, round(s, 4)) for n, s in top_3],
            "explanation": f"Low confidence ({best_score:.0%}). Closest: {best_name}.",
        }

    # Check for multi-resource: if top-2 are close (within 15%)
    is_multi = len(scored) >= 2 and (scored[0][1] - scored[1][1]) < 0.15 * scored[0][1]

    return {
        "detected_intent": "Multi-resource" if is_multi else best_name,
        "confidence": round(best_score, 4),
        "top_3": [(n, round(s, 4)) for n, s in top_3],
        "is_multi_resource": is_multi,
        "secondary_intent": scored[1][0] if is_multi else None,
        "explanation": (
            f"Matched semantically with {best_score:.0%} similarity to {best_name}"
            + (f" and {scored[1][1]:.0%} to {scored[1][0]}" if is_multi else "")
        ),
    }


# ═══════════════════════════════════════════════════════════════════════
# SEMANTIC PROVIDER RANKING
# ═══════════════════════════════════════════════════════════════════════

def rank_providers_semantic(query_text, providers, user_lat, user_lon,
                            stock_by_provider=None, urgency_score=1.0):
    """
    Hybrid semantic ranking:
      final_score = 0.4 × semantic_sim + 0.3 × stock_ratio + 0.2 × dist_score + 0.1 × urgency

    Returns list of provider dicts with `semantic_score`, `hybrid_score`, `ranking_explanation`.
    No keyword matching — pure transformer embeddings.
    """
    from .geo import haversine_km

    if not providers:
        return []

    _index.ensure(providers)
    sims = cosine_scores(_index.encode_query(preprocess(query_text)), _index.provider_vectors)

    distances = [
        haversine_km(user_lat, user_lon, p.get("latitude") or 0.0, p.get("longitude") or 0.0)
        for p in providers
    ]

    # Fold the (provider, resource) stock map into a per-provider total once,
    # instead of rescanning the whole map for every provider.
    totals: dict = {}
    for (provider_id, _resource_id), qty in (stock_by_provider or {}).items():
        totals[provider_id] = totals.get(provider_id, 0.0) + float(qty or 0.0)
    stocks = [totals.get(p.get("id"), 0.0) for p in providers]

    max_stock = max(stocks) if stocks and max(stocks) > 0 else 1.0

    # Hybrid scoring
    ranked = []
    for i, p in enumerate(providers):
        semantic = float(np.clip(sims[i], 0, 1))
        stock_ratio = stocks[i] / max_stock
        dist_score = 1.0 / (1.0 + distances[i])  # bounded 0-1
        urgency_norm = min(1.0, (urgency_score - 1.0) / 1.0)  # 0-1

        hybrid = (
            W_SEMANTIC * semantic
            + W_STOCK * stock_ratio
            + W_DISTANCE * dist_score
            + W_URGENCY * urgency_norm
        )

        p["semantic_score"] = round(semantic, 4)
        p["stock_ratio"] = round(stock_ratio, 4)
        p["distance_km"] = round(distances[i], 2)
        p["distance_score"] = round(dist_score, 4)
        p["hybrid_score"] = round(hybrid, 4)
        p["ai_score"] = round(hybrid, 4)
        p["total_stock"] = stocks[i]

        # Explainable breakdown
        reasons = []
        if semantic > 0.5:
            reasons.append(f"High semantic match ({semantic:.0%})")
        elif semantic > 0.3:
            reasons.append(f"Moderate semantic match ({semantic:.0%})")
        if stock_ratio > 0.6:
            reasons.append("High stock")
        if distances[i] < 10:
            reasons.append(f"Close ({distances[i]:.1f} km)")
        if urgency_score > 1.3:
            reasons.append("Urgency boost")
        if not reasons:
            reasons.append("Available resource")

        p["ranking_explanation"] = (
            f"AI Ranked: {', '.join(reasons)} "
            f"[Sem: {semantic:.2f}, Stock: {stock_ratio:.2f}, "
            f"Dist: {dist_score:.2f}, Urg: {urgency_norm:.2f}]"
        )
        ranked.append(p)

    ranked.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return ranked


# ═══════════════════════════════════════════════════════════════════════
# FULL PIPELINE — single entry point
# ═══════════════════════════════════════════════════════════════════════

def process(query_text):
    """
    Full NLP pipeline: preprocess → intent → entities → structured output.
    Lightweight entry point for non-ranking use (e.g., intent-only queries).
    """
    preprocessed = preprocess(query_text)
    intent_result = classify_intent(query_text)
    quantity = extract_quantity(query_text)
    urgency = compute_urgency(query_text)

    return {
        "original_query": query_text,
        "preprocessed_query": preprocessed,
        "detected_intent": intent_result["detected_intent"],
        "confidence": intent_result["confidence"],
        "confidence_pct": round(intent_result["confidence"] * 100, 1),
        "is_multi_resource": intent_result.get("is_multi_resource", False),
        "secondary_intent": intent_result.get("secondary_intent"),
        "top_3": intent_result["top_3"],
        "extracted_quantity": quantity,
        "urgency_score": urgency,
        "explanation": intent_result["explanation"],
    }
