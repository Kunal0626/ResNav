#!/usr/bin/env python3
"""Deterministic seed generator for ResNav.

Run it twice and you get byte-identical SQL. That matters for more than
tidiness: Phase 6's concurrency scripts and Phase 9's EXPLAIN comparisons are
only meaningful if the data they run against is the same every time, and a
reader who reproduces a number in the README has to get the number back.

Determinism comes from three rules, all of which are easy to break by
accident:

  1. One `random.Random(SEED)` instance, consumed in a fixed order. No
     module-level `random`, no second generator.
  2. No wall-clock time. Timestamps are offsets from a FIXED epoch, so the
     file does not change because a day passed.
  3. No iteration over anything unordered. Every loop is over a list or a
     sorted sequence.

Usage:  python3 db/seed/generate.py          # rewrite db/seed/0*.sql
        python3 db/seed/generate.py --check  # verify the files are current
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20261107

# A fixed point in time, not "now". Every generated timestamp is an offset
# from this, so regenerating tomorrow produces the same bytes.
EPOCH = datetime(2026, 11, 1, 6, 0, 0)

OUT = Path(__file__).resolve().parent

# ─── The real data, carried over from ResNav ────────────────────────────────
# These are the 18 relief centres the project has always shown. Real Indian
# cities and plausible coordinates; the organisations themselves are
# fictional, so nothing here can be mistaken for a claim about a real relief
# operation.

REAL_PROVIDERS = [
    (1, 'Annapurna Rasoi - Delhi', 'Free community kitchen and ration distribution for low-income families and homeless.', 28.613900, 77.209000, 'Connaught Place', 'Delhi', 'Delhi', '110001', '011-23456789', '6 AM - 9 PM', 0),
    (2, 'Karol Bagh Night Shelter', 'Government night shelter with beds, toilets, and basic amenities.', 28.704100, 77.102500, 'Karol Bagh', 'Delhi', 'Delhi', '110005', '011-28765432', '6 PM - 8 AM', 0),
    (3, 'Lajpat Nagar Health Centre', 'Free OPD, basic medicines, and referral to hospitals for needy.', 28.651900, 77.231500, 'Lajpat Nagar', 'Delhi', 'Delhi', '110024', '011-26435100', '8 AM - 4 PM', 0),
    (4, 'Noida Employment Exchange', 'Registration for jobs, skill training, and placement assistance.', 28.535500, 77.391000, 'Noida Sector 18', 'Delhi', 'Delhi', '201301', '0120-2456789', '10 AM - 5 PM', 0),
    (5, 'Dwarka Food Bank', 'Dry ration and cooked meal distribution; no-questions-asked policy.', 28.459500, 77.026600, 'Dwarka Sector 10', 'Delhi', 'Delhi', '110075', '011-25098765', '9 AM - 6 PM', 0),
    (6, 'Mumbai Central Relief Kitchen', 'Free meals for homeless and daily wage workers near CST.', 18.938800, 72.835400, 'CST Area', 'Mumbai', 'Maharashtra', '400001', '022-22612345', '7 AM - 10 PM', 0),
    (7, 'Bandra Shelter Home', 'Short-stay shelter for women and children in distress.', 19.076000, 72.877700, 'Bandra West', 'Mumbai', 'Maharashtra', '400050', '022-26456789', '24 hours', 1),
    (8, 'Andheri Free Clinic', 'Free general and emergency medical care; medicine aid available.', 19.113600, 72.869700, 'Andheri East', 'Mumbai', 'Maharashtra', '400069', '022-26801234', '9 AM - 8 PM', 0),
    (9, 'Dharavi Livelihood Centre', 'Job placement and skill training for local residents.', 18.989400, 72.822500, 'Dharavi', 'Mumbai', 'Maharashtra', '400017', '022-24098765', '10 AM - 6 PM', 0),
    (10, 'T Nagar Food Aid Society', 'Free lunch and ration kits for families in need.', 13.082700, 80.270700, 'T Nagar', 'Chennai', 'Tamil Nadu', '600017', '044-24351234', '11 AM - 3 PM', 0),
    (11, 'Egmore Government Hospital', 'Free emergency and OPD services for all.', 13.060400, 80.242500, 'Egmore', 'Chennai', 'Tamil Nadu', '600008', '044-28193111', '24 hours', 1),
    (12, 'Adyar Financial Aid Office', 'Disaster relief and one-time financial aid applications.', 13.006700, 80.220600, 'Adyar', 'Chennai', 'Tamil Nadu', '600020', '044-24412345', '9 AM - 5 PM', 0),
    (13, 'Guwahati Flood Relief Camp', 'Temporary shelter and food during floods; relief distribution.', 26.144500, 91.736200, 'Bharalumukh', 'Guwahati', 'Assam', '781009', '0361-2547890', '24 hours during floods', 1),
    (14, 'Dibrugarh District Hospital', 'Free medical care; emergency and maternity.', 27.472800, 94.912000, 'Town area', 'Dibrugarh', 'Assam', '786001', '0373-2324567', '24 hours', 1),
    (15, 'Jorhat Employment Office', 'Rural employment and MGNREGA registration.', 26.750000, 94.216700, 'Jorhat town', 'Jorhat', 'Assam', '785001', '0376-2321234', '10 AM - 4 PM', 0),
    (16, 'Bhubaneswar Cyclone Relief Cell', 'Financial aid and ration for cyclone-affected families.', 20.296100, 85.824500, 'Bapuji Nagar', 'Bhubaneswar', 'Odisha', '751009', '0674-2536789', '9 AM - 6 PM', 0),
    (17, 'Puri Shelter & Food Aid', 'Shelter and meals for pilgrims and disaster-affected.', 19.813400, 85.831200, 'Grand Road', 'Puri', 'Odisha', '752001', '06752-222345', '6 AM - 10 PM', 0),
    (18, 'Cuttack District Health Centre', 'Free OPD and medicine for BPL card holders.', 20.462500, 85.879000, 'Buxi Bazar', 'Cuttack', 'Odisha', '753001', '0671-2501234', '8 AM - 8 PM', 0),
]

# Further cities, to take the network from 18 centres to 30. Coordinates are
# the real city centres; the facilities are invented.
EXTRA_CITIES = [
    ('Kolkata',    'West Bengal',    22.572600, 88.363900, '700001'),
    ('Patna',      'Bihar',          25.594100, 85.137600, '800001'),
    ('Lucknow',    'Uttar Pradesh',  26.846700, 80.946200, '226001'),
    ('Ahmedabad',  'Gujarat',        23.022500, 72.571400, '380001'),
    ('Bengaluru',  'Karnataka',      12.971600, 77.594600, '560001'),
    ('Hyderabad',  'Telangana',      17.385000, 78.486700, '500001'),
    ('Kochi',      'Kerala',          9.931200, 76.267300, '682001'),
    ('Nagpur',     'Maharashtra',    21.145800, 79.088200, '440001'),
    ('Raipur',     'Chhattisgarh',   21.251400, 81.629600, '492001'),
    ('Dehradun',   'Uttarakhand',    30.316500, 78.032200, '248001'),
    ('Srinagar',   'Jammu & Kashmir',34.083700, 74.797300, '190001'),
    ('Visakhapatnam', 'Andhra Pradesh', 17.686800, 83.218500, '530001'),
]
FACILITY_KINDS = [
    ('Relief Kitchen',      'Cooked meals and dry ration for displaced families.', 'food',     '6 AM - 9 PM', 0),
    ('Emergency Shelter',   'Temporary shelter with bedding and sanitation.',      'shelter',  '24 hours', 1),
    ('Community Health Post', 'Primary care, dressings and essential medicines.',  'medical',  '8 AM - 8 PM', 0),
]

REAL_RESOURCES = [
    (1, 'Food (kg)',        'kg',     'food'),
    (2, 'Medicine (units)', 'units',  'medical'),
    (3, 'Blankets',         'units',  'shelter'),
    (4, 'Water (litres)',   'litres', 'food'),
    (5, 'Shelter (beds)',   'beds',   'shelter'),
]

# Taking the catalogue to 45 items, which is what makes Phase 9's index work
# worth doing: on five resources every plan is a table scan regardless.
EXTRA_RESOURCES = [
    ('Rice',                'kg',     'food'),     ('Wheat Flour',          'kg',     'food'),
    ('Lentils (dal)',       'kg',     'food'),     ('Cooking Oil',          'litres', 'food'),
    ('Salt',                'kg',     'food'),     ('Sugar',                'kg',     'food'),
    ('Milk Powder',         'kg',     'food'),     ('Ready-to-Eat Meals',   'packets','food'),
    ('Baby Formula',        'kg',     'food'),     ('Drinking Water Pouches','packets','food'),
    ('ORS Sachets',         'doses',  'medical'),  ('Paracetamol',          'doses',  'medical'),
    ('Antibiotics',         'doses',  'medical'),  ('Antiseptic Solution',  'litres', 'medical'),
    ('Bandages',            'packets','medical'),  ('Surgical Gloves',      'packets','medical'),
    ('Face Masks',          'packets','medical'),  ('Insulin',              'doses',  'medical'),
    ('Snake Antivenom',     'doses',  'medical'),  ('First Aid Kits',       'units',  'medical'),
    ('Tarpaulin Sheets',    'units',  'shelter'),  ('Tents',                'units',  'shelter'),
    ('Sleeping Mats',       'units',  'shelter'),  ('Mosquito Nets',        'units',  'shelter'),
    ('Bedsheets',           'units',  'shelter'),  ('Folding Cots',         'units',  'shelter'),
    ('Soap Bars',           'units',  'hygiene'),  ('Detergent',            'kg',     'hygiene'),
    ('Sanitary Napkins',    'packets','hygiene'),  ('Toothpaste',           'units',  'hygiene'),
    ('Disinfectant',        'litres', 'hygiene'),  ('Hand Sanitiser',       'litres', 'hygiene'),
    ('Kerosene',            'litres', 'fuel'),     ('LPG Cylinders',        'units',  'fuel'),
    ('Candles',             'packets','fuel'),     ('Torches',              'units',  'fuel'),
    ('Solar Lanterns',      'units',  'fuel'),     ('Water Purification Tablets', 'packets', 'hygiene'),
    ('Jerry Cans',          'units',  'hygiene'),  ('Rope Coils',           'units',  'shelter'),
]

REAL_ZONES = [
    (1, 'Assam Flood Zone',    'Northeast', 'Assam',      2000000, 5200.0, 'High',   26.144500, 91.736200),
    (2, 'Odisha Cyclone Area', 'East',      'Odisha',     1500000, 3800.0, 'High',   20.296100, 85.824500),
    (3, 'Delhi Relief',        'North',     'Delhi',       500000, 1484.0, 'Medium', 28.613900, 77.209000),
    (4, 'Mumbai Monsoon Zone', 'West',      'Maharashtra',1200000,  603.0, 'Medium', 19.076000, 72.877700),
    (5, 'Chennai Flood Zone',  'South',     'Tamil Nadu',  800000,  426.0, 'Medium', 13.082700, 80.270700),
]
EXTRA_ZONES = [
    ('Bihar Flood Belt',       'East',      'Bihar',          3100000, 7400.0, 'Critical', 25.594100, 85.137600),
    ('Kerala Landslide Belt',  'South',     'Kerala',          450000,  980.0, 'High',      9.931200, 76.267300),
    ('Uttarakhand Hill Zone',  'North',     'Uttarakhand',     320000, 2100.0, 'High',     30.316500, 78.032200),
    ('Gujarat Cyclone Coast',  'West',      'Gujarat',         900000, 3300.0, 'Medium',   23.022500, 72.571400),
    ('Vizag Coastal Strip',    'South',     'Andhra Pradesh',  700000, 1250.0, 'Medium',   17.686800, 83.218500),
    ('Sundarbans Delta',       'East',      'West Bengal',     600000, 4300.0, 'High',     22.572600, 88.363900),
    ('Kashmir Valley Winter',  'North',     'Jammu & Kashmir', 410000, 1900.0, 'Medium',   34.083700, 74.797300),
]

CATEGORIES = [
    (1, 'food',       'food,hunger,meal,ration,eat,starving,money for food,groceries'),
    (2, 'medical',    'medical,doctor,hospital,health,sick,medicine,ambulance,treatment'),
    (3, 'hygiene',    'hygiene,sanitary pad,pads,sanitary pads,menstrual,period,women health,essential supplies,soap,toiletries'),
    (4, 'shelter',    'shelter,sleep,night stay,homeless,roof,accommodation,housing'),
    (5, 'employment', 'job,employment,work,livelihood,income,hire'),
    (6, 'financial',  'financial,money,grant,loan,aid,cash,relief,compensation'),
    (7, 'education',  'education,school,training,books,learn,tuition'),
    (8, 'emergency',  'emergency,crisis,urgent,help immediately'),
]
CATEGORY_ID = {name: cid for cid, name, _ in CATEGORIES}

CONTACTS = [
    ('National Emergency', '112', None, 'national'),
    ('Police', '100', None, 'national'),
    ('Ambulance', '102', 2, 'national'),
    ('Disaster Management (NDMA)', '011-26701728', None, 'national'),
    ('Child Helpline', '1098', None, 'national'),
    ('Women Helpline', '181', None, 'national'),
]


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.6f}".rstrip("0").rstrip(".") or "0"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def rows(table: str, cols: list[str], data: list[tuple]) -> str:
    if not data:
        return ""
    body = ",\n".join("    (" + ", ".join(q(v) for v in row) + ")" for row in data)
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n{body};\n"


def ts(days_ago: float) -> str:
    """A timestamp as an offset from the fixed epoch, never from 'now'."""
    return (EPOCH - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


def header(title: str, note: str) -> str:
    return (f"-- {'=' * 73}\n-- {title}\n--\n"
            + "\n".join(f"-- {line}" for line in note.strip().splitlines())
            + f"\n-- GENERATED by db/seed/generate.py (seed {SEED}). Do not edit by hand.\n"
            + f"-- {'=' * 73}\n\n")


def build() -> dict[str, str]:
    rng = random.Random(SEED)
    files: dict[str, str] = {}

    # ── Providers ────────────────────────────────────────────────────────
    providers = [list(p) for p in REAL_PROVIDERS]
    next_id = len(REAL_PROVIDERS) + 1
    for city, state, lat, lon, pin in EXTRA_CITIES:
        kind, desc, _cat, hours, is247 = FACILITY_KINDS[(next_id - 1) % len(FACILITY_KINDS)]
        # Offset each facility slightly from the city centre, deterministically.
        dlat = round(rng.uniform(-0.06, 0.06), 6)
        dlon = round(rng.uniform(-0.06, 0.06), 6)
        providers.append([
            next_id, f"{city} {kind}", desc,
            round(lat + dlat, 6), round(lon + dlon, 6),
            f"{city} Central", city, state, pin,
            f"0{rng.randint(11, 99)}-{rng.randint(2000000, 2999999)}", hours, is247,
        ])
        next_id += 1

    # ── Resources ────────────────────────────────────────────────────────
    resources = [list(r) for r in REAL_RESOURCES]
    rid = len(REAL_RESOURCES) + 1
    for name, unit, cat in EXTRA_RESOURCES:
        resources.append([rid, name, unit, cat])
        rid += 1

    # ── Zones ────────────────────────────────────────────────────────────
    zones = [list(z) for z in REAL_ZONES]
    zid = len(REAL_ZONES) + 1
    for name, region, state, pop, area, risk, lat, lon in EXTRA_ZONES:
        zones.append([zid, name, region, state, pop, area, risk, lat, lon])
        zid += 1

    wipe = """SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM StockAlerts;
DELETE FROM StockHistory;
DELETE FROM Allocations;
DELETE FROM Requests;
DELETE FROM StockLevels;
DELETE FROM StockThresholds;
DELETE FROM ServicesOffered;
DELETE FROM EmergencyContact;
DELETE FROM ServiceCategory;
DELETE FROM RiskScores;
DELETE FROM ResourceConsumptionRate;
DELETE FROM ZoneSummary;
DELETE FROM Zones;
DELETE FROM Providers;
DELETE FROM Resources;
DELETE FROM AuditLog;
DELETE FROM UserQuery;
SET FOREIGN_KEY_CHECKS = 1;

"""

    # ── 01: reference data ───────────────────────────────────────────────
    out = [header("01_reference.sql -- entities that exist before any disaster",
                  """Relief centres, the resource catalogue, disaster zones, search
categories and emergency numbers. The 18 original centres and 5 original
resources are carried over unchanged; the rest extend the network to 30
centres, 45 resources and 12 zones so the indexing work in Phase 9 has
enough rows to say anything.

Cities and coordinates are real. Every facility name is invented, so
nothing here can be read as a claim about a real relief operation."""), wipe]
    out.append(rows("Resources", ["id", "name", "unit", "category"],
                    [tuple(r) for r in resources]))
    out.append("")
    out.append(rows("Providers",
                    ["id", "name", "description", "latitude", "longitude", "address",
                     "city", "state", "pincode", "phone", "operating_hours", "is_24_7"],
                    [tuple(p) for p in providers]))
    out.append("")
    out.append(rows("Zones",
                    ["id", "zone_name", "region", "state", "population", "area_sqkm",
                     "risk_level", "latitude", "longitude"],
                    [tuple(z) for z in zones]))
    out.append("")
    out.append(rows("ServiceCategory", ["id", "name", "keywords"],
                    [(c[0], c[1], c[2]) for c in CATEGORIES]))
    out.append("")
    out.append(rows("EmergencyContact", ["name", "number", "category_id", "scope"], CONTACTS))
    out.append("")

    offered = []
    for p in providers:
        pid, city = p[0], p[6]
        base = CATEGORY_ID[FACILITY_KINDS[(pid - 1) % len(FACILITY_KINDS)][2]] \
            if pid > len(REAL_PROVIDERS) else rng.choice([1, 2, 3, 4])
        cats = sorted({base, rng.choice([1, 2, 3, 4, 6, 8])})
        for c in cats:
            offered.append((pid, c, f"{city} service point"))
    out.append(rows("ServicesOffered", ["provider_id", "category_id", "details"], offered))
    files["01_reference.sql"] = "\n".join(out)

    # ── 02: thresholds and opening stock ─────────────────────────────────
    thresholds = []
    for r in resources:
        warn = rng.choice([20, 30, 40, 50, 60])
        thresholds.append((r[0], float(warn), float(warn // 4)))

    stock = []
    for p in providers:
        pid = p[0]
        # Each centre carries a deterministic slice of the catalogue, so the
        # allocator has real choices to make and real gaps to work around.
        held = sorted(rng.sample([r[0] for r in resources], rng.randint(14, 26)))
        for res_id in held:
            qty = float(rng.choice([0, 25, 50, 75, 100, 150, 200, 300, 400, 600]))
            low = float(rng.choice([10, 20, 30, 40, 50]))
            stock.append((pid, res_id, qty, low))

    out = [header("02_stock.sql -- opening inventory",
                  """Per-resource alert thresholds, then the opening stock position of
every centre. Some lines open at zero on purpose: a seed where everything
is in stock never exercises partial fulfilment or the low-stock alert."""),
           rows("StockThresholds", ["resource_id", "warning_level", "critical_level"], thresholds),
           "",
           rows("StockLevels", ["provider_id", "resource_id", "quantity", "low_stock_threshold"], stock)]
    files["02_stock.sql"] = "\n".join(out)

    # ── 03: historical stock movements ───────────────────────────────────
    # These describe movements that happened BEFORE the snapshot above, which
    # is why they are inserted directly rather than produced by the triggers:
    # they are history, not current activity. The forecast engine fits a
    # regression over them, and with no history at all it correctly reports
    # that it cannot forecast -- true, but it exercises nothing.
    history = []
    series = [(pid, rid_) for (pid, rid_, qty, _low) in stock if qty > 0]
    rng.shuffle(series)
    for pid, res_id in series[:260]:
        level = float(rng.choice([400, 500, 600, 800, 1000]))
        burn = rng.uniform(6.0, 30.0)
        points = rng.randint(6, 12)
        for step in range(points):
            days_ago = 30 - step * (28 / max(points - 1, 1))
            before = level
            level = max(0.0, round(level - burn * rng.uniform(0.6, 1.4), 3))
            history.append((pid, res_id, round(before, 3), level, 'allocation',
                            f'historical draw-down day {30 - int(days_ago)}', ts(days_ago)))
    files["03_history.sql"] = header(
        "03_history.sql -- stock movements preceding the snapshot",
        """Inserted directly rather than produced by triggers, because they are
records of movements that already happened: the opening stock in 02 is the
position AFTER them. Timestamps are offsets from a fixed epoch, so this
file does not change because a day passed.""") + rows(
        "StockHistory",
        ["provider_id", "resource_id", "quantity_before", "quantity_after",
         "change_type", "details", "created_at"], history)

    # ── 04: the request queue ────────────────────────────────────────────
    requests = []
    total_stock_by_resource: dict[int, float] = {}
    for _pid, res_id, qty, _low in stock:
        total_stock_by_resource[res_id] = total_stock_by_resource.get(res_id, 0.0) + qty

    for i in range(1, 601):
        zone = zones[rng.randrange(len(zones))]
        res = resources[rng.randrange(len(resources))]
        qty = float(rng.choice([20, 40, 60, 80, 100, 150, 200, 250, 400]))
        severity = round(rng.uniform(0.5, 3.0), 2)
        urgency = round(rng.uniform(0.5, 3.0), 2)
        pop = int(zone[4] * rng.uniform(0.01, 0.2))
        # The same formula the API uses, so a request created through the UI
        # is scored the same way as a seeded one.
        priority = round((severity * max(pop, 1) * urgency)
                         / max(1.0, total_stock_by_resource.get(res[0], 1.0)), 4)
        created = ts(rng.uniform(0.2, 25.0))
        requests.append((i, zone[0], res[0], qty, severity, pop, urgency,
                         priority, 'pending', created))

    files["04_requests.sql"] = header(
        "04_requests.sql -- the open request queue",
        """600 requests across 12 zones and 45 resources, all left 'pending'.
Nothing is allocated here on purpose: allocation is what the demo, the
tests and the concurrency scripts DO, and a seed that has already run it
would hide whether it works. priority_score uses the same formula as the
API, so a request raised through the UI is scored identically.""") + rows(
        "Requests",
        ["id", "zone_id", "resource_id", "quantity_requested", "severity",
         "population_affected", "urgency", "priority_score", "status", "created_at"],
        requests)

    # ── MANIFEST ─────────────────────────────────────────────────────────
    # The totals this seed produces, written down so nothing has to hardcode
    # them. The tests read it, the README quotes it, and it cannot drift from
    # the data because both come out of this function.
    manifest = {
        "seed": SEED,
        "epoch": EPOCH.strftime("%Y-%m-%d %H:%M:%S"),
        "providers": len(providers),
        "resources": len(resources),
        "zones": len(zones),
        "stock_rows": len(stock),
        "stock_rows_at_zero": sum(1 for r in stock if r[2] == 0),
        "total_units_held": round(sum(r[2] for r in stock), 3),
        "stock_history_rows": len(history),
        "requests": len(requests),
        "service_links": len(offered),
    }
    files["MANIFEST.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    return files


def main(argv: list[str]) -> int:
    check = "--check" in argv
    files = build()
    changed = []
    for name, content in sorted(files.items()):
        path = OUT / name
        old = path.read_text() if path.exists() else None
        if old != content:
            changed.append(name)
            if not check:
                path.write_text(content)
    digest = hashlib.sha256(
        "".join(files[k] for k in sorted(files)).encode()).hexdigest()[:16]

    if check:
        if changed:
            print("OUT OF DATE: " + ", ".join(changed))
            print("Run: python3 db/seed/generate.py")
            return 1
        print(f"seed files are current (sha256 {digest})")
        return 0

    for name in sorted(files):
        path = OUT / name
        print(f"  {name:<22} {len(path.read_text().splitlines()):>5} lines")
    print(f"\n  seed {SEED}, sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
