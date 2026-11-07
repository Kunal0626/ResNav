-- Allocating to a request that is already closed must be refused.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency, status)
VALUES (902, 1, 1, 5.000, 2.0, 2.0, 'rejected');
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (902, 3, 1, 1.000);
