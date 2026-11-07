-- R1: stock can never go negative, even by a direct hand-typed UPDATE.
-- Expect errno 1644 / SQLSTATE 45000 from trg_stocklevels_bu_guard, naming
-- the provider, the resource and the value it refused.
UPDATE StockLevels SET quantity = -1 WHERE provider_id = 1 AND resource_id = 1;
