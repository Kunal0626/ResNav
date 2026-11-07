-- sp_restock_center adds stock, records why, and refuses a non-positive
-- quantity.
CALL sp_restock_center(1, 1, 25.000, @total);
SELECT 'new_total'   AS check_name, @total;
SELECT 'history'     AS check_name, change_type, quantity_before, quantity_after FROM StockHistory;
SELECT 'audit'       AS check_name, action_type FROM AuditLog WHERE action_type = 'restock';

-- Creates the stock row when the centre did not previously hold the resource.
CALL sp_restock_center(2, 2, 15.000, @total2);
SELECT 'created_row' AS check_name, provider_id, resource_id, quantity
  FROM StockLevels WHERE provider_id = 2 AND resource_id = 2;

CALL sp_restock_center(1, 1, -5.000, @bad);
