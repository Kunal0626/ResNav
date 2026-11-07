-- The views must survive ONLY_FULL_GROUP_BY and report the same numbers the
-- base tables do.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (930, 1, 1, 45.000, 2.0, 2.0);
CALL sp_allocate_request(930, @a, @l, @s);

SELECT 'stock_summary' AS check_name, provider_name, quantity, is_low
  FROM v_center_stock_summary WHERE resource_id = 1 ORDER BY provider_id;
SELECT 'low_stock' AS check_name, provider_name, quantity, threshold, shortfall
  FROM v_low_stock ORDER BY provider_id, resource_id;
SELECT 'reliability' AS check_name, provider_name, total_allocations, reliability
  FROM v_provider_reliability ORDER BY provider_id;
SELECT 'fulfilment' AS check_name, request_id, quantity_requested, quantity_allocated, outstanding, status
  FROM v_request_fulfilment ORDER BY request_id;
SELECT 'zone_shortage' AS check_name, zone_name, total_requested, total_allocated, shortage_ratio
  FROM v_zone_shortage_analysis ORDER BY zone_id;
SELECT 'rollup' AS check_name, resource_name, requests, fulfilled, fulfilment_rate
  FROM v_allocation_performance;
