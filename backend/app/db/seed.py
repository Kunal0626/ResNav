"""Schema application and reference-data seeding.

Idempotent: every statement is CREATE IF NOT EXISTS / INSERT OR IGNORE, so this
runs safely on both a fresh database and an existing one.
"""

import logging
import os
import sqlite3

log = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def _resolve_db_path(db_path=None):
    if db_path is not None:
        return str(db_path)
    from ..core.config import get_settings
    return str(get_settings().database_path)


def apply_schema(conn):
    """Apply the unified DBMS schema."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())


# ─────────────────────────────────────────────────────────────────────────────
# Service categories (used by AI classifier)
# ─────────────────────────────────────────────────────────────────────────────

def seed_categories(conn):
    categories = [
        ("food", "Food aid, meals, ration, nutrition",
         "food,hunger,meal,ration,eat,starving,money for food,groceries"),
        ("medical", "Medical care, health, doctor, hospital",
         "medical,doctor,hospital,health,sick,medicine,ambulance,treatment"),
        ("hygiene", "Hygiene products, sanitary pads, menstrual health",
         "hygiene,sanitary pad,pads,sanitary pads,menstrual,period,women health,essential supplies,soap,toiletries"),
        ("shelter", "Shelter, night stay, housing",
         "shelter,sleep,night stay,homeless,roof,accommodation,housing"),
        ("employment", "Jobs, employment, livelihood",
         "job,employment,work,livelihood,income,hire"),
        ("financial", "Financial aid, money, grants, loans",
         "financial,money,grant,loan,aid,cash,relief,compensation"),
        ("education", "Education, school, training, books",
         "education,school,training,books,learn,tuition"),
        ("emergency", "Emergency, crisis, urgent help",
         "emergency,crisis,urgent,help immediately"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO ServiceCategory (name, description, keywords) VALUES (?, ?, ?)",
        categories,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Providers (with embedded location)
# ─────────────────────────────────────────────────────────────────────────────

def seed_providers(conn):
    n = conn.execute("SELECT COUNT(*) FROM Providers").fetchone()[0]
    if n > 0:
        return

    providers = [
        # (name, description, lat, lon, address, city, state, pincode, phone, email, website, hours, is_24_7)
        ("Annapurna Rasoi - Delhi", "Free community kitchen and ration distribution for low-income families and homeless.",
         28.6139, 77.2090, "Connaught Place", "Delhi", "Delhi", "110001",
         "011-23456789", None, None, "6 AM - 9 PM", 0),
        ("Karol Bagh Night Shelter", "Government night shelter with beds, toilets, and basic amenities.",
         28.7041, 77.1025, "Karol Bagh", "Delhi", "Delhi", "110005",
         "011-28765432", None, None, "6 PM - 8 AM", 0),
        ("Lajpat Nagar Health Centre", "Free OPD, basic medicines, and referral to hospitals for needy.",
         28.6519, 77.2315, "Lajpat Nagar", "Delhi", "Delhi", "110024",
         "011-26435100", "lajpat.health@delhi.gov.in", None, "8 AM - 4 PM", 0),
        ("Noida Employment Exchange", "Registration for jobs, skill training, and placement assistance.",
         28.5355, 77.3910, "Noida Sector 18", "Delhi", "Delhi", "201301",
         "0120-2456789", "noida.exchange@gov.in", None, "10 AM - 5 PM", 0),
        ("Dwarka Food Bank", "Dry ration and cooked meal distribution; no-questions-asked policy.",
         28.4595, 77.0266, "Dwarka Sector 10", "Delhi", "Delhi", "110075",
         "011-25098765", None, None, "9 AM - 6 PM", 0),
        ("Mumbai Central Relief Kitchen", "Free meals for homeless and daily wage workers near CST.",
         18.9388, 72.8354, "CST Area", "Mumbai", "Maharashtra", "400001",
         "022-22612345", None, None, "7 AM - 10 PM", 0),
        ("Bandra Shelter Home", "Short-stay shelter for women and children in distress.",
         19.0760, 72.8777, "Bandra West", "Mumbai", "Maharashtra", "400050",
         "022-26456789", "bandra.shelter@maharashtra.gov.in", None, "24 hours", 1),
        ("Andheri Free Clinic", "Free general and emergency medical care; medicine aid available.",
         19.1136, 72.8697, "Andheri East", "Mumbai", "Maharashtra", "400069",
         "022-26801234", None, None, "9 AM - 8 PM", 0),
        ("Dharavi Livelihood Centre", "Job placement and skill training for local residents.",
         18.9894, 72.8225, "Dharavi", "Mumbai", "Maharashtra", "400017",
         "022-24098765", None, None, "10 AM - 6 PM", 0),
        ("T Nagar Food Aid Society", "Free lunch and ration kits for families in need.",
         13.0827, 80.2707, "T Nagar", "Chennai", "Tamil Nadu", "600017",
         "044-24351234", None, None, "11 AM - 3 PM", 0),
        ("Egmore Government Hospital", "Free emergency and OPD services for all.",
         13.0604, 80.2425, "Egmore", "Chennai", "Tamil Nadu", "600008",
         "044-28193111", None, None, "24 hours", 1),
        ("Adyar Financial Aid Office", "Disaster relief and one-time financial aid applications.",
         13.0067, 80.2206, "Adyar", "Chennai", "Tamil Nadu", "600020",
         "044-24412345", "adyar.relief@tn.gov.in", None, "9 AM - 5 PM", 0),
        ("Guwahati Flood Relief Camp", "Temporary shelter and food during floods; relief distribution.",
         26.1445, 91.7362, "Bharalumukh", "Guwahati", "Assam", "781009",
         "0361-2547890", None, None, "24 hours during floods", 1),
        ("Dibrugarh District Hospital", "Free medical care; emergency and maternity.",
         27.4728, 94.9120, "Town area", "Dibrugarh", "Assam", "786001",
         "0373-2324567", None, None, "24 hours", 1),
        ("Jorhat Employment Office", "Rural employment and MGNREGA registration.",
         26.7500, 94.2167, "Jorhat town", "Jorhat", "Assam", "785001",
         "0376-2321234", None, None, "10 AM - 4 PM", 0),
        ("Bhubaneswar Cyclone Relief Cell", "Financial aid and ration for cyclone-affected families.",
         20.2961, 85.8245, "Bapuji Nagar", "Bhubaneswar", "Odisha", "751009",
         "0674-2536789", "relief@odisha.gov.in", None, "9 AM - 6 PM", 0),
        ("Puri Shelter & Food Aid", "Shelter and meals for pilgrims and disaster-affected.",
         19.8134, 85.8312, "Grand Road", "Puri", "Odisha", "752001",
         "06752-222345", None, None, "6 AM - 10 PM", 0),
        ("Cuttack District Health Centre", "Free OPD and medicine for BPL card holders.",
         20.4625, 85.8790, "Buxi Bazar", "Cuttack", "Odisha", "753001",
         "0671-2501234", None, None, "8 AM - 8 PM", 0),
    ]
    for p in providers:
        conn.execute(
            """INSERT INTO Providers (name, description, latitude, longitude, address,
               city, state, pincode, phone, email, website, operating_hours, is_24_7)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            p,
        )


def seed_services_offered(conn):
    n = conn.execute("SELECT COUNT(*) FROM ServicesOffered").fetchone()[0]
    if n > 0:
        return

    def cat_id(name):
        row = conn.execute("SELECT id FROM ServiceCategory WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    links = [
        (1, "food", "Free meals and dry ration"),
        (2, "shelter", "Night shelter, beds"),
        (3, "medical", "OPD, basic medicines"),
        (3, "hygiene", "Hygiene kits, women health supplies"),
        (4, "employment", "Job registration, training"),
        (5, "food", "Ration and cooked meals"),
        (6, "food", "Free meals"),
        (7, "shelter", "Women and children shelter"),
        (7, "hygiene", "Sanitary pads, hygiene, women support"),
        (8, "medical", "Free clinic, medicines"),
        (8, "hygiene", "Essential supplies, hygiene"),
        (9, "employment", "Jobs and skills"),
        (10, "food", "Lunch and ration"),
        (11, "medical", "Emergency and OPD"),
        (11, "emergency", "Emergency care"),
        (12, "financial", "Disaster relief, financial aid"),
        (13, "food", "Flood relief food"),
        (13, "shelter", "Flood relief shelter"),
        (13, "hygiene", "Relief supplies, hygiene"),
        (14, "medical", "Hospital care"),
        (14, "hygiene", "Women health, essential supplies"),
        (15, "employment", "MGNREGA, employment"),
        (16, "financial", "Cyclone relief, compensation"),
        (16, "food", "Relief ration"),
        (17, "shelter", "Shelter"),
        (17, "food", "Meals"),
        (17, "hygiene", "Hygiene supplies"),
        (18, "medical", "OPD, medicines"),
        (18, "hygiene", "Health centre hygiene supplies"),
    ]
    for provider_id, cat_name, details in links:
        cid = cat_id(cat_name)
        if cid:
            conn.execute(
                "INSERT OR IGNORE INTO ServicesOffered (provider_id, category_id, details) VALUES (?, ?, ?)",
                (provider_id, cid, details),
            )


def seed_emergency_contacts(conn):
    n = conn.execute("SELECT COUNT(*) FROM EmergencyContact").fetchone()[0]
    if n > 0:
        return
    contacts = [
        ("National Emergency", "112", None, "national", None),
        ("Police", "100", None, "national", None),
        ("Ambulance", "102", 2, "national", None),
        ("Disaster Management (NDMA)", "011-26701728", None, "national", None),
        ("Child Helpline", "1098", None, "national", None),
        ("Women Helpline", "181", None, "national", None),
    ]
    conn.executemany(
        "INSERT INTO EmergencyContact (name, number, category_id, scope, region) VALUES (?, ?, ?, ?, ?)",
        contacts,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resources, StockLevels, Zones, Requests
# ─────────────────────────────────────────────────────────────────────────────

def seed_resources(conn):
    types = [
        ("Food (kg)", "kg", "food"),
        ("Medicine (units)", "units", "medical"),
        ("Blankets", "units", "shelter"),
        ("Water (litres)", "litres", "food"),
        ("Shelter (beds)", "beds", "shelter"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO Resources (name, unit, category) VALUES (?, ?, ?)",
        types,
    )


def seed_stock_levels(conn):
    n = conn.execute("SELECT COUNT(*) FROM StockLevels").fetchone()[0]
    if n > 0:
        return
    providers = conn.execute("SELECT id FROM Providers ORDER BY id").fetchall()
    if not providers:
        return
    rows = []
    for p in providers:
        pid = p[0]
        if pid % 2 == 1:
            rows.append((pid, 1, 50.0, 10.0))   # Food
        if pid in (3, 8, 11, 14, 18):
            rows.append((pid, 2, 100.0, 20.0))  # Medicine
        if pid in (2, 7, 13, 17):
            rows.append((pid, 3, 30.0, 5.0))    # Blankets
        if pid in (1, 5, 6, 10, 13, 16, 17):
            rows.append((pid, 4, 200.0, 50.0))  # Water
        if pid in (2, 7, 13, 17):
            rows.append((pid, 5, 20.0, 3.0))    # Shelter beds
    for r in rows:
        conn.execute(
            "INSERT OR IGNORE INTO StockLevels (provider_id, resource_id, quantity, low_stock_threshold) VALUES (?, ?, ?, ?)",
            r,
        )


def seed_zones(conn):
    n = conn.execute("SELECT COUNT(*) FROM Zones").fetchone()[0]
    if n > 0:
        return
    zones = [
        ("Assam Flood Zone", "Northeast", "Assam", 2000000, 5200.0, "High"),
        ("Odisha Cyclone Area", "East", "Odisha", 1500000, 3800.0, "High"),
        ("Delhi Relief", "North", "Delhi", 500000, 1484.0, "Medium"),
        ("Mumbai Monsoon Zone", "West", "Maharashtra", 1200000, 603.0, "Medium"),
        ("Chennai Flood Zone", "South", "Tamil Nadu", 800000, 426.0, "Medium"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO Zones (zone_name, region, state, population, area_sqkm, risk_level) VALUES (?, ?, ?, ?, ?, ?)",
        zones,
    )


def seed_requests(conn):
    n = conn.execute("SELECT COUNT(*) FROM Requests").fetchone()[0]
    if n > 0:
        return

    def zone_id(name):
        row = conn.execute("SELECT id FROM Zones WHERE zone_name = ?", (name,)).fetchone()
        return row[0] if row else 1

    requests = [
        (zone_id("Assam Flood Zone"), 1, 500.0, 1.5, 2000, 1.2, "pending"),
        (zone_id("Odisha Cyclone Area"), 2, 200.0, 1.8, 1500, 1.5, "pending"),
        (zone_id("Delhi Relief"), 4, 1000.0, 1.0, 500, 1.0, "pending"),
    ]
    for r in requests:
        conn.execute(
            """INSERT INTO Requests (zone_id, resource_id, quantity_requested,
               severity, population_affected, urgency, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            r,
        )
    # Compute priority scores
    conn.execute("""
        UPDATE Requests SET priority_score = (
            severity * population_affected * urgency /
            MAX(1, (SELECT COALESCE(SUM(quantity), 0) FROM StockLevels
                     WHERE resource_id = Requests.resource_id))
        ) WHERE priority_score IS NULL
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Enterprise tables initialization
# ─────────────────────────────────────────────────────────────────────────────

def seed_stock_thresholds(conn):
    n = conn.execute("SELECT COUNT(*) FROM StockThresholds").fetchone()[0]
    if n > 0:
        return
    thresholds = {
        "Food (kg)": (30, 8),
        "Medicine (units)": (40, 10),
        "Blankets": (10, 3),
        "Water (litres)": (80, 20),
        "Shelter (beds)": (5, 2),
    }
    for row in conn.execute("SELECT id, name FROM Resources ORDER BY id").fetchall():
        w, c = thresholds.get(row[1], (20, 5))
        conn.execute(
            "INSERT OR IGNORE INTO StockThresholds (resource_id, warning_level, critical_level, auto_alert) VALUES (?, ?, ?, 1)",
            (row[0], w, c),
        )


def initialize_zone_summaries(conn):
    n = conn.execute("SELECT COUNT(*) FROM ZoneSummary").fetchone()[0]
    if n > 0:
        return
    conn.execute("""
        INSERT OR IGNORE INTO ZoneSummary
            (zone_id, zone_name, total_requests, total_allocated, pending_requests,
             shortage_ratio, avg_severity, avg_urgency, last_updated)
        SELECT
            z.id, z.zone_name,
            COUNT(DISTINCT r.id),
            COALESCE(SUM(a.quantity_allocated), 0),
            COUNT(DISTINCT CASE WHEN r.status = 'pending' THEN r.id END),
            CASE WHEN SUM(r.quantity_requested) = 0 THEN 0
                 ELSE ROUND(1.0 - (COALESCE(SUM(a.quantity_allocated), 0) / SUM(r.quantity_requested)), 4)
            END,
            ROUND(AVG(r.severity), 2),
            ROUND(AVG(r.urgency), 2),
            datetime('now')
        FROM Zones z
        LEFT JOIN Requests r ON r.zone_id = z.id
        LEFT JOIN Allocations a ON a.request_id = r.id
        GROUP BY z.id, z.zone_name
    """)


def initialize_consumption_rates(conn):
    n = conn.execute("SELECT COUNT(*) FROM ResourceConsumptionRate").fetchone()[0]
    if n > 0:
        return
    conn.execute("""
        INSERT OR IGNORE INTO ResourceConsumptionRate
            (resource_id, provider_id, daily_rate, weekly_rate, monthly_rate, trend_direction)
        SELECT resource_id, provider_id, 0, 0, 0, 'stable' FROM StockLevels
    """)


def initialize_risk_scores(conn):
    n = conn.execute("SELECT COUNT(*) FROM RiskScores").fetchone()[0]
    if n > 0:
        return
    conn.execute("""
        INSERT OR IGNORE INTO RiskScores
            (resource_id, provider_id, depletion_probability, average_consumption,
             risk_index, classification, last_calculated)
        SELECT
            sl.resource_id, sl.provider_id,
            CASE
                WHEN sl.quantity <= 0 THEN 1.0
                WHEN sl.low_stock_threshold <= 0 THEN 0.1
                ELSE MIN(1.0, ROUND(MAX(0, 1.0 - (sl.quantity / (sl.low_stock_threshold * 3))), 4))
            END,
            0,
            CASE
                WHEN sl.quantity <= 0 THEN 100
                ELSE MIN(100, MAX(0, ROUND((1.0 - (sl.quantity / (sl.low_stock_threshold * 3))) * 100, 2)))
            END,
            CASE
                WHEN sl.quantity <= 0 THEN 'Critical'
                WHEN sl.quantity < COALESCE(
                    (SELECT critical_level FROM StockThresholds WHERE resource_id = sl.resource_id), 5
                ) THEN 'Critical'
                WHEN sl.quantity < sl.low_stock_threshold THEN 'High'
                WHEN sl.quantity < sl.low_stock_threshold * 1.5 THEN 'Medium'
                ELSE 'Low'
            END,
            datetime('now')
        FROM StockLevels sl
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry points
# ─────────────────────────────────────────────────────────────────────────────

def seed_all(conn):
    """Full seed: schema + all data."""
    apply_schema(conn)
    seed_categories(conn)
    seed_providers(conn)
    seed_services_offered(conn)
    seed_emergency_contacts(conn)
    seed_resources(conn)
    seed_stock_levels(conn)
    seed_zones(conn)
    seed_requests(conn)
    seed_stock_thresholds(conn)
    initialize_zone_summaries(conn)
    initialize_consumption_rates(conn)
    initialize_risk_scores(conn)
    conn.commit()
    log.info("Database schema applied and reference data seeded.")


def main(db_path=None):
    """Create (or top up) the database at `db_path` and seed reference data."""
    path = _resolve_db_path(db_path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        seed_all(conn)
    finally:
        conn.close()


def migrate(db_path=None):
    """Apply schema + missing seed data to an existing database. No-op if absent."""
    path = _resolve_db_path(db_path)
    if not os.path.isfile(path):
        return
    main(path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
