-- R5: exactly one OPEN alert per (provider, resource), however many times
-- the stock falls further. MySQL has no partial index, so this is enforced
-- by a unique index over generated columns that go NULL when resolved, and
-- the trigger uses an upsert so hitting it is harmless rather than fatal.
UPDATE StockLevels SET quantity = 4.000 WHERE provider_id = 1 AND resource_id = 1;
SELECT 'after_first_drop' AS check_name, COUNT(*) FROM StockAlerts WHERE status = 'open';

UPDATE StockLevels SET quantity = 3.000 WHERE provider_id = 1 AND resource_id = 1;
UPDATE StockLevels SET quantity = 2.000 WHERE provider_id = 1 AND resource_id = 1;
SELECT 'after_three_drops' AS check_name, COUNT(*) FROM StockAlerts WHERE status = 'open';
SELECT 'alert_detail'      AS check_name, provider_id, resource_id, quantity_at_alert, threshold_at_alert FROM StockAlerts WHERE status = 'open';

-- Recovering above the threshold resolves it and frees the unique slot.
UPDATE StockLevels SET quantity = 50.000 WHERE provider_id = 1 AND resource_id = 1;
SELECT 'after_recovery' AS check_name, status, COUNT(*) FROM StockAlerts GROUP BY status;

-- ... and a second shortage can then raise a new one.
UPDATE StockLevels SET quantity = 1.000 WHERE provider_id = 1 AND resource_id = 1;
SELECT 'second_shortage' AS check_name, status, COUNT(*) FROM StockAlerts GROUP BY status ORDER BY status;
