-- ON DELETE RESTRICT: a request that has allocations cannot be deleted, so
-- relief history cannot be erased by tidying up. This is why
-- sp_cancel_request exists -- cancelling is a state change, not a DELETE.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (904, 1, 1, 5.000, 2.0, 2.0);
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (904, 3, 1, 5.000);
DELETE FROM Requests WHERE id = 904;
