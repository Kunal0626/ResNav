-- An allocation larger than the source centre holds must be refused.
-- Centre 1 holds 10 Blankets; ask it for 11.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (900, 1, 1, 50.000, 2.0, 2.0);
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (900, 1, 1, 11.000);
