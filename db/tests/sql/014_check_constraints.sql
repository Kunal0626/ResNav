-- CHECK constraints are ENFORCED, not merely parsed. Each statement below is
-- expected to fail with errno 3819, naming the constraint that caught it.
-- (MySQL before 8.0.16 accepted all four silently.)
INSERT INTO Requests (zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (1, 1, 5.000, 9.9, 2.0);
INSERT INTO Requests (zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (1, 1, 0.000, 2.0, 2.0);
INSERT INTO Zones (zone_name, state, population, latitude, longitude)
VALUES ('Impossible Place', 'Nowhere', 1, 99.9, 0.0);
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (903, 1, 1, 5.000, 2.0, 2.0);
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (903, 3, 1, 0.000);
