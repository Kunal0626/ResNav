-- R3: an allocation cannot exceed what is still outstanding on the request.
-- Request 901 asks for 5; centre 3 holds 100, so stock is not the limit.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (901, 1, 1, 5.000, 2.0, 2.0);
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (901, 3, 1, 6.000);
