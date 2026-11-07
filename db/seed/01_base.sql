-- ===========================================================================
-- 01_base.sql -- reference and operational data.
--
-- Carried across from ResNav's SQLite seed so the numbers in the UI stay the
-- ones the project has always shown, with one addition the merged schema
-- requires: every zone now has real coordinates. Without them allocation
-- ranked suppliers by same-state-or-not, a boolean standing in for distance.
--
-- Deterministic: fixed ids, fixed values, no randomness, no timestamps. Load
-- it twice and you get the same database.
--
-- Phase 5 replaces this with a generator that also produces the larger data
-- set and a tiny hand-checkable one.
-- ===========================================================================

SET FOREIGN_KEY_CHECKS = 0;
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


-- Resources
INSERT INTO Resources (id, name, unit, category) VALUES
    (1, 'Food (kg)', 'kg', 'food'),
    (2, 'Medicine (units)', 'units', 'medical'),
    (3, 'Blankets', 'units', 'shelter'),
    (4, 'Water (litres)', 'litres', 'food'),
    (5, 'Shelter (beds)', 'beds', 'shelter');

-- Relief centres
INSERT INTO Providers (id, name, description, latitude, longitude, address, city, state, pincode, phone, email, website, operating_hours, is_24_7) VALUES
    (1, 'Annapurna Rasoi - Delhi', 'Free community kitchen and ration distribution for low-income families and homeless.', 28.6139, 77.209, 'Connaught Place', 'Delhi', 'Delhi', '110001', '011-23456789', NULL, NULL, '6 AM - 9 PM', 0),
    (2, 'Karol Bagh Night Shelter', 'Government night shelter with beds, toilets, and basic amenities.', 28.7041, 77.1025, 'Karol Bagh', 'Delhi', 'Delhi', '110005', '011-28765432', NULL, NULL, '6 PM - 8 AM', 0),
    (3, 'Lajpat Nagar Health Centre', 'Free OPD, basic medicines, and referral to hospitals for needy.', 28.6519, 77.2315, 'Lajpat Nagar', 'Delhi', 'Delhi', '110024', '011-26435100', 'lajpat.health@delhi.gov.in', NULL, '8 AM - 4 PM', 0),
    (4, 'Noida Employment Exchange', 'Registration for jobs, skill training, and placement assistance.', 28.5355, 77.391, 'Noida Sector 18', 'Delhi', 'Delhi', '201301', '0120-2456789', 'noida.exchange@gov.in', NULL, '10 AM - 5 PM', 0),
    (5, 'Dwarka Food Bank', 'Dry ration and cooked meal distribution; no-questions-asked policy.', 28.4595, 77.0266, 'Dwarka Sector 10', 'Delhi', 'Delhi', '110075', '011-25098765', NULL, NULL, '9 AM - 6 PM', 0),
    (6, 'Mumbai Central Relief Kitchen', 'Free meals for homeless and daily wage workers near CST.', 18.9388, 72.8354, 'CST Area', 'Mumbai', 'Maharashtra', '400001', '022-22612345', NULL, NULL, '7 AM - 10 PM', 0),
    (7, 'Bandra Shelter Home', 'Short-stay shelter for women and children in distress.', 19.076, 72.8777, 'Bandra West', 'Mumbai', 'Maharashtra', '400050', '022-26456789', 'bandra.shelter@maharashtra.gov.in', NULL, '24 hours', 1),
    (8, 'Andheri Free Clinic', 'Free general and emergency medical care; medicine aid available.', 19.1136, 72.8697, 'Andheri East', 'Mumbai', 'Maharashtra', '400069', '022-26801234', NULL, NULL, '9 AM - 8 PM', 0),
    (9, 'Dharavi Livelihood Centre', 'Job placement and skill training for local residents.', 18.9894, 72.8225, 'Dharavi', 'Mumbai', 'Maharashtra', '400017', '022-24098765', NULL, NULL, '10 AM - 6 PM', 0),
    (10, 'T Nagar Food Aid Society', 'Free lunch and ration kits for families in need.', 13.0827, 80.2707, 'T Nagar', 'Chennai', 'Tamil Nadu', '600017', '044-24351234', NULL, NULL, '11 AM - 3 PM', 0),
    (11, 'Egmore Government Hospital', 'Free emergency and OPD services for all.', 13.0604, 80.2425, 'Egmore', 'Chennai', 'Tamil Nadu', '600008', '044-28193111', NULL, NULL, '24 hours', 1),
    (12, 'Adyar Financial Aid Office', 'Disaster relief and one-time financial aid applications.', 13.0067, 80.2206, 'Adyar', 'Chennai', 'Tamil Nadu', '600020', '044-24412345', 'adyar.relief@tn.gov.in', NULL, '9 AM - 5 PM', 0),
    (13, 'Guwahati Flood Relief Camp', 'Temporary shelter and food during floods; relief distribution.', 26.1445, 91.7362, 'Bharalumukh', 'Guwahati', 'Assam', '781009', '0361-2547890', NULL, NULL, '24 hours during floods', 1),
    (14, 'Dibrugarh District Hospital', 'Free medical care; emergency and maternity.', 27.4728, 94.912, 'Town area', 'Dibrugarh', 'Assam', '786001', '0373-2324567', NULL, NULL, '24 hours', 1),
    (15, 'Jorhat Employment Office', 'Rural employment and MGNREGA registration.', 26.75, 94.2167, 'Jorhat town', 'Jorhat', 'Assam', '785001', '0376-2321234', NULL, NULL, '10 AM - 4 PM', 0),
    (16, 'Bhubaneswar Cyclone Relief Cell', 'Financial aid and ration for cyclone-affected families.', 20.2961, 85.8245, 'Bapuji Nagar', 'Bhubaneswar', 'Odisha', '751009', '0674-2536789', 'relief@odisha.gov.in', NULL, '9 AM - 6 PM', 0),
    (17, 'Puri Shelter & Food Aid', 'Shelter and meals for pilgrims and disaster-affected.', 19.8134, 85.8312, 'Grand Road', 'Puri', 'Odisha', '752001', '06752-222345', NULL, NULL, '6 AM - 10 PM', 0),
    (18, 'Cuttack District Health Centre', 'Free OPD and medicine for BPL card holders.', 20.4625, 85.879, 'Buxi Bazar', 'Cuttack', 'Odisha', '753001', '0671-2501234', NULL, NULL, '8 AM - 8 PM', 0);

-- Disaster zones, now with coordinates
INSERT INTO Zones (id, zone_name, region, state, population, area_sqkm, risk_level, latitude, longitude) VALUES
    (1, 'Assam Flood Zone', 'Northeast', 'Assam', 2000000, 5200.0, 'High', 26.1445, 91.7362),
    (2, 'Odisha Cyclone Area', 'East', 'Odisha', 1500000, 3800.0, 'High', 20.2961, 85.8245),
    (3, 'Delhi Relief', 'North', 'Delhi', 500000, 1484.0, 'Medium', 28.6139, 77.209),
    (4, 'Mumbai Monsoon Zone', 'West', 'Maharashtra', 1200000, 603.0, 'Medium', 19.076, 72.8777),
    (5, 'Chennai Flood Zone', 'South', 'Tamil Nadu', 800000, 426.0, 'Medium', 13.0827, 80.2707);

-- Search categories
INSERT INTO ServiceCategory (id, name, description, keywords) VALUES
    (1, 'food', 'Food aid, meals, ration, nutrition', 'food,hunger,meal,ration,eat,starving,money for food,groceries'),
    (2, 'medical', 'Medical care, health, doctor, hospital', 'medical,doctor,hospital,health,sick,medicine,ambulance,treatment'),
    (3, 'hygiene', 'Hygiene products, sanitary pads, menstrual health', 'hygiene,sanitary pad,pads,sanitary pads,menstrual,period,women health,essential supplies,soap,toiletries'),
    (4, 'shelter', 'Shelter, night stay, housing', 'shelter,sleep,night stay,homeless,roof,accommodation,housing'),
    (5, 'employment', 'Jobs, employment, livelihood', 'job,employment,work,livelihood,income,hire'),
    (6, 'financial', 'Financial aid, money, grants, loans', 'financial,money,grant,loan,aid,cash,relief,compensation'),
    (7, 'education', 'Education, school, training, books', 'education,school,training,books,learn,tuition'),
    (8, 'emergency', 'Emergency, crisis, urgent help', 'emergency,crisis,urgent,help immediately');

-- Centre -> category
INSERT INTO ServicesOffered (provider_id, category_id, details) VALUES
    (1, 1, 'Free meals and dry ration'),
    (2, 4, 'Night shelter, beds'),
    (3, 2, 'OPD, basic medicines'),
    (3, 3, 'Hygiene kits, women health supplies'),
    (4, 5, 'Job registration, training'),
    (5, 1, 'Ration and cooked meals'),
    (6, 1, 'Free meals'),
    (7, 3, 'Sanitary pads, hygiene, women support'),
    (7, 4, 'Women and children shelter'),
    (8, 2, 'Free clinic, medicines'),
    (8, 3, 'Essential supplies, hygiene'),
    (9, 5, 'Jobs and skills'),
    (10, 1, 'Lunch and ration'),
    (11, 2, 'Emergency and OPD'),
    (11, 8, 'Emergency care'),
    (12, 6, 'Disaster relief, financial aid'),
    (13, 1, 'Flood relief food'),
    (13, 3, 'Relief supplies, hygiene'),
    (13, 4, 'Flood relief shelter'),
    (14, 2, 'Hospital care'),
    (14, 3, 'Women health, essential supplies'),
    (15, 5, 'MGNREGA, employment'),
    (16, 1, 'Relief ration'),
    (16, 6, 'Cyclone relief, compensation'),
    (17, 1, 'Meals'),
    (17, 3, 'Hygiene supplies'),
    (17, 4, 'Shelter'),
    (18, 2, 'OPD, medicines'),
    (18, 3, 'Health centre hygiene supplies');

-- Emergency contacts
INSERT INTO EmergencyContact (id, name, number, category_id, scope, region) VALUES
    (1, 'National Emergency', '112', NULL, 'national', NULL),
    (2, 'Police', '100', NULL, 'national', NULL),
    (3, 'Ambulance', '102', 2, 'national', NULL),
    (4, 'Disaster Management (NDMA)', '011-26701728', NULL, 'national', NULL),
    (5, 'Child Helpline', '1098', NULL, 'national', NULL),
    (6, 'Women Helpline', '181', NULL, 'national', NULL);

-- Per-resource thresholds
INSERT INTO StockThresholds (resource_id, warning_level, critical_level, auto_alert) VALUES
    (1, 30.0, 8.0, 1),
    (2, 40.0, 10.0, 1),
    (3, 10.0, 3.0, 1),
    (4, 80.0, 20.0, 1),
    (5, 5.0, 2.0, 1);

-- Live stock
INSERT INTO StockLevels (provider_id, resource_id, quantity, low_stock_threshold) VALUES
    (1, 1, 50.0, 10.0),
    (1, 4, 200.0, 50.0),
    (2, 3, 15.0, 5.0),
    (2, 5, 20.0, 3.0),
    (3, 1, 50.0, 10.0),
    (3, 2, 100.0, 20.0),
    (5, 1, 50.0, 10.0),
    (5, 4, 200.0, 50.0),
    (6, 4, 200.0, 50.0),
    (7, 1, 50.0, 10.0),
    (7, 3, 30.0, 5.0),
    (7, 5, 20.0, 3.0),
    (8, 2, 100.0, 20.0),
    (9, 1, 50.0, 10.0),
    (10, 4, 200.0, 50.0),
    (11, 1, 50.0, 10.0),
    (11, 2, 100.0, 20.0),
    (13, 1, 50.0, 10.0),
    (13, 3, 0.0, 5.0),
    (13, 4, 200.0, 50.0),
    (13, 5, 20.0, 3.0),
    (14, 2, 100.0, 20.0),
    (15, 1, 50.0, 10.0),
    (16, 4, 200.0, 50.0),
    (17, 1, 50.0, 10.0),
    (17, 3, 30.0, 5.0),
    (17, 4, 200.0, 50.0),
    (17, 5, 20.0, 3.0),
    (18, 2, 100.0, 20.0);

-- Open requests
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, population_affected, urgency, priority_score, status) VALUES
    (1, 1, 1, 500.0, 1.5, 2000, 1.2, 8.0, 'pending'),
    (2, 2, 2, 200.0, 1.8, 1500, 1.5, 8.1, 'pending'),
    (3, 3, 4, 1000.0, 1.0, 500, 1.0, 0.35714285714285715, 'pending');
