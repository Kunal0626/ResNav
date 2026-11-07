-- sp_allocate_request must drain the NEAREST centre before touching a
-- farther one. The zone sits exactly on centre 1 (0 km); centre 2 is
-- ~1459 km away and centre 3 ~1756 km.
--
-- Centre 1 holds 10, centre 2 holds 40. A request for 45 must therefore take
-- all 10 from centre 1 and 35 from centre 2, and never touch centre 3.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (920, 1, 1, 45.000, 2.0, 2.0);

CALL sp_allocate_request(920, @alloc, @legs, @st);

SELECT 'allocated' AS check_name, @alloc;
SELECT 'legs'      AS check_name, @legs;
SELECT 'status'    AS check_name, @st;
SELECT 'per_provider' AS check_name, provider_id, quantity_allocated
  FROM Allocations WHERE request_id = 920 ORDER BY provider_id;
SELECT 'stock_after'  AS check_name, provider_id, quantity
  FROM StockLevels WHERE resource_id = 1 ORDER BY provider_id;
