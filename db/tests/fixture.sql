-- ===========================================================================
-- fixture.sql -- the tiny, hand-checkable data set the SQL tests run against.
--
-- Small enough that every expected number can be worked out on paper, and
-- reloaded before each test so results never depend on test order. (The
-- Python suite's inability to do exactly this is the defect recorded in
-- docs/AUDIT.md.)
--
-- Geography is chosen so distance ordering is unambiguous:
--   zone  Z1  sits exactly on top of centre P1
--   P2 is ~1459 km away (Delhi), P3 ~1756 km (Chennai)
-- so "nearest first" must always pick P1, then P2, then P3.
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
DELETE FROM Requests;
DELETE FROM Zones;
DELETE FROM Providers;
DELETE FROM Resources;
DELETE FROM AuditLog;
DELETE FROM UserQuery;
SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO Resources (id, name, unit, category) VALUES
    (1, 'Blankets',   'units',  'shelter'),
    (2, 'Water Cans', 'litres', 'water');

INSERT INTO Providers (id, name, latitude, longitude, city, state, pincode) VALUES
    (1, 'Guwahati Relief Centre', 26.144500, 91.736200, 'Guwahati', 'Assam',       '781001'),
    (2, 'Delhi Relief Centre',    28.613900, 77.209000, 'Delhi',    'Delhi',       '110001'),
    (3, 'Chennai Relief Centre',  13.082700, 80.270700, 'Chennai',  'Tamil Nadu',  '600001');

INSERT INTO Zones (id, zone_name, region, state, population, latitude, longitude, risk_level) VALUES
    (1, 'Guwahati Flood Zone', 'Northeast', 'Assam', 100000, 26.144500, 91.736200, 'High');

-- Deliberate quantities: 10 + 40 + 100 = 150 units of Blankets in total.
INSERT INTO StockLevels (provider_id, resource_id, quantity, low_stock_threshold) VALUES
    (1, 1,  10.000,  5.000),
    (2, 1,  40.000,  5.000),
    (3, 1, 100.000,  5.000),
    (1, 2,  60.000, 20.000);

INSERT INTO StockThresholds (resource_id, warning_level, critical_level) VALUES
    (1, 20.000, 5.000),
    (2, 30.000, 10.000);
