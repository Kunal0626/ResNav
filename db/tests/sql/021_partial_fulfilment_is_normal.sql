-- R7: asking for more than one centre holds leaves the request 'allocated',
-- not 'fulfilled', and not an error.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (911, 1, 1, 100.000, 2.0, 2.0);
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (911, 1, 1, 10.000);

SELECT 'status'      AS check_name, status FROM Requests WHERE id = 911;
SELECT 'allocated'   AS check_name, quantity_allocated FROM v_request_fulfilment WHERE request_id = 911;
SELECT 'outstanding' AS check_name, outstanding        FROM v_request_fulfilment WHERE request_id = 911;
SELECT 'ratio'       AS check_name, fulfilment_ratio   FROM v_request_fulfilment WHERE request_id = 911;
