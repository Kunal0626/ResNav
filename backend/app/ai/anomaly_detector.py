"""
AI Module 5 — Anomaly Detection
=================================
Detects abnormal resource patterns using IsolationForest.

Examples:
- Sudden spike in requests
- Unexpected stock depletion
- Provider failure patterns

Displays warnings: "Anomaly detected in water demand."
"""

import numpy as np
from sklearn.ensemble import IsolationForest


def detect_anomalies(data: dict) -> dict:
    """
    Detect anomalies across multiple data streams.

    Args:
        data: dict with optional keys:
            request_volumes: list of int (daily request counts per resource)
                             OR list of dicts {resource: str, volumes: [int]}
            stock_levels: list of dicts {provider: str, resource: str, current: float, previous: float}
            provider_performance: list of dicts {provider: str, success_rate: float, total: int}

    Returns:
        {
            "anomalies": [
                {
                    "type": "request_spike" | "stock_depletion" | "provider_failure",
                    "entity": str,
                    "description": str,
                    "severity": "high" | "medium" | "low",
                    "explanation": str,
                },
                ...
            ],
            "total_anomalies": int,
            "summary": str,
            "explanation": str,
        }
    """
    anomalies = []

    # ── 1. Request volume anomalies ──
    request_data = data.get("request_volumes", [])

    if request_data:
        # Handle flat list or list of dicts
        if isinstance(request_data[0], dict):
            for r in request_data:
                resource = r.get("resource", "Unknown")
                volumes = r.get("volumes", [])
                _detect_volume_anomalies(volumes, resource, anomalies)
        elif isinstance(request_data[0], (int, float)):
            _detect_volume_anomalies(request_data, "overall_requests", anomalies)

    # ── 2. Stock depletion anomalies ──
    stock_data = data.get("stock_levels", [])
    for s in stock_data:
        provider = s.get("provider", "Unknown")
        resource = s.get("resource", "Unknown")
        current = float(s.get("current", 0))
        previous = float(s.get("previous", current))

        if previous > 0:
            drop_pct = ((previous - current) / previous) * 100
            if drop_pct > 50:
                severity = "high" if drop_pct > 80 else "medium"
                anomalies.append({
                    "type": "stock_depletion",
                    "entity": f"{resource} at {provider}",
                    "description": f"Anomaly detected in {resource.lower()} supply: "
                                   f"{drop_pct:.0f}% stock drop at {provider}.",
                    "severity": severity,
                    "explanation": (
                        f"Stock for {resource} at {provider} dropped from {previous:.0f} to {current:.0f} "
                        f"({drop_pct:.0f}% decrease). Threshold for anomaly: >50% drop. "
                        f"This may indicate unexpected consumption or data entry error."
                    ),
                })

    # ── 3. Provider failure patterns ──
    provider_data = data.get("provider_performance", [])
    for p in provider_data:
        name = p.get("provider", "Unknown")
        success = float(p.get("success_rate", 1.0))
        total = int(p.get("total", 0))

        if total >= 3 and success < 0.4:
            severity = "high" if success < 0.2 else "medium"
            anomalies.append({
                "type": "provider_failure",
                "entity": name,
                "description": f"Provider failure pattern detected: {name} "
                               f"has only {success:.0%} success rate across {total} allocations.",
                "severity": severity,
                "explanation": (
                    f"Provider '{name}' shows {success:.0%} success rate over {total} allocations. "
                    f"Normal threshold: >60%. Low success may indicate supply chain issues, "
                    f"logistics failures, or reporting problems."
                ),
            })

    summary = f"{len(anomalies)} anomalies detected"
    high_count = sum(1 for a in anomalies if a["severity"] == "high")
    if high_count:
        summary += f" ({high_count} high severity)"
    summary += "."

    return {
        "anomalies": anomalies,
        "total_anomalies": len(anomalies),
        "summary": summary,
        "explanation": (
            "Anomaly detection uses IsolationForest (contamination=0.1) for request volume "
            "spikes, percentage-drop thresholds (>50%) for stock depletion, and success rate "
            "thresholds (<40%) for provider failure patterns."
        ),
    }


def _detect_volume_anomalies(volumes: list, label: str, anomalies: list):
    """Use IsolationForest to detect spikes in a volume time-series."""
    if len(volumes) < 5:
        return

    X = np.array(volumes, dtype=float).reshape(-1, 1)
    clf = IsolationForest(contamination=0.1, random_state=42)
    clf.fit(X)
    preds = clf.predict(X)

    anomaly_indices = np.where(preds == -1)[0]
    if len(anomaly_indices) == 0:
        return

    mean_val = float(np.mean(X))
    for idx in anomaly_indices:
        val = float(volumes[idx])
        if val > mean_val * 1.3:  # only report spikes above mean
            deviation = ((val - mean_val) / mean_val) * 100 if mean_val > 0 else 0
            severity = "high" if deviation > 100 else ("medium" if deviation > 50 else "low")
            anomalies.append({
                "type": "request_spike",
                "entity": label,
                "description": f"Anomaly detected in {label.replace('_', ' ')} demand: "
                               f"spike of {val:.0f} (mean: {mean_val:.0f}, +{deviation:.0f}%).",
                "severity": severity,
                "explanation": (
                    f"IsolationForest identified data point at index {idx} ({val:.0f}) as anomalous. "
                    f"Mean volume: {mean_val:.0f}, deviation: +{deviation:.0f}%. "
                    f"Contamination parameter: 0.1 (10% expected anomaly rate)."
                ),
            })
