#!/usr/bin/env python3
"""Capture the API's responses as static JSON for the read-only Vercel demo.

The demo is the real SPA with a frozen backend: every GET below is recorded
exactly as the live API returned it, so the deployed pages show real seeded
data rather than hand-written fixtures. Writes cannot be frozen this way --
a static file answers GET and nothing else -- so the demo client refuses
them with a message instead of faking a result.

Search is a POST and is the landing page's whole purpose, so a fixed set of
example queries is recorded too. Those answers are real: the live ranker
produced them. Free-text search still needs the live backend, and the demo
says so rather than pretending otherwise.

    python3 tools/snapshot_demo.py --base-url http://localhost:8080

Re-run it after changing the seed, or the demo drifts from the database.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "demo"

# Every GET the SPA makes. Keys are the logical names the demo client asks
# for; values are the live paths.
GETS = {
    "health":            "/api/health",
    "ready":             "/api/ready",
    "overview":          "/api/overview",
    "reference":         "/api/reference",
    "dashboard":         "/api/dashboard",
    "forecast":          "/api/forecast",
    "forecast-series":   "/api/forecast/series",
    "explorer":          "/api/explorer",
    "stock":             "/api/stock",
    "stock-low":         "/api/stock?low_only=1",
    "requests":          "/api/requests",
    "allocations":       "/api/allocations",
    "logs":              "/api/logs",
    "ai-forecast":       "/api/ai/forecast",
    "ai-risk":           "/api/ai/risk-predict",
    "ai-anomaly":        "/api/ai/anomaly-detect",
    "ai-insights":       "/api/ai/insights",
}

# Queries recorded for the demo's example searches. Chosen to cover
# different resources and phrasings rather than to flatter the ranker.
SEARCHES = [
    "we urgently need 500 water packets for a flooded village",
    "300 blankets for a relief camp tonight",
    "medical kits near Patna",
    "food supplies for 2000 people",
    "tents and tarpaulin after the cyclone",
    "oxygen cylinders urgently",
]

# Delhi, matching the app's own fallback when the browser denies location.
FALLBACK_COORDS = (28.6139, 77.2090)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def fetch(base: str, path: str, payload: dict | None = None):
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def write(name: str, obj) -> int:
    path = OUT / f"{name}.json"
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text)
    return len(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080",
                    help="A running ResNav API (default: the Docker stack on 8080)")
    ap.add_argument("--recommendations", type=int, default=12,
                    help="How many per-request recommendations to record")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": args.base_url,
        "searches": {},
        "recommendations": [],
        "statuses": [],
    }
    total = 0

    print("==> GET endpoints")
    for name, path in GETS.items():
        try:
            size = write(name, fetch(args.base_url, path))
        except urllib.error.URLError as exc:
            print(f"    {name:18} FAILED  {exc}")
            return 1
        total += size
        print(f"    {name:18} {size:>9,} bytes")

    # Status-filtered request lists, driven by what the data actually holds
    # rather than by a guessed list of status names.
    print("==> request lists by status")
    rows = fetch(args.base_url, "/api/requests")
    items = rows if isinstance(rows, list) else next(
        (v for v in rows.values() if isinstance(v, list)), [])
    statuses = sorted({r.get("status") for r in items if r.get("status")})
    for st in statuses:
        size = write(f"requests-{slug(st)}", fetch(args.base_url, f"/api/requests?status={st}"))
        total += size
        manifest["statuses"].append(st)
        print(f"    {st:18} {size:>9,} bytes")

    print("==> per-request recommendations")
    for r in items[: args.recommendations]:
        rid = r.get("id")
        if rid is None:
            continue
        size = write(f"recommendation-{rid}", fetch(args.base_url, f"/api/requests/{rid}/recommendation"))
        total += size
        manifest["recommendations"].append(rid)
    print(f"    recorded {len(manifest['recommendations'])} of {len(items)} requests")

    print("==> example searches (POST, recorded from the live ranker)")
    lat, lon = FALLBACK_COORDS
    for q in SEARCHES:
        s = slug(q)
        size = write(f"search-{s}", fetch(args.base_url, "/api/search",
                                          {"query": q, "latitude": lat, "longitude": lon}))
        total += size
        manifest["searches"][q] = s
        print(f"    {s:42} {size:>9,} bytes")

    size = write("manifest", manifest)
    total += size
    print(f"\n==> {len(list(OUT.glob('*.json')))} files, {total:,} bytes total")
    print(f"    written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
