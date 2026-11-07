-- ===========================================================================
-- 01_functions.sql -- stored functions.
-- Applied before triggers and procedures, both of which call them.
-- ===========================================================================

DROP FUNCTION IF EXISTS fn_haversine_km;

DELIMITER $$

-- Great-circle distance between two points, in kilometres.
--
-- DETERMINISTIC and NO SQL are not decoration. With binary logging enabled
-- MySQL refuses to create a function it cannot prove is replication-safe
-- unless the creator has SUPER, and these two characteristics are how a
-- function proves it: same inputs always give the same output, and it reads
-- no tables. They also let the optimiser treat calls as constant-foldable.
--
-- Haversine, not the simpler equirectangular approximation, because the
-- distances here span India (Delhi to Chennai is ~1760 km) where the flat
-- approximation is several percent out. It is straight-line distance: real
-- routing needs a road graph and is listed under Limitations.
CREATE FUNCTION fn_haversine_km(
    lat1 DECIMAL(9,6), lon1 DECIMAL(9,6),
    lat2 DECIMAL(9,6), lon2 DECIMAL(9,6)
) RETURNS DECIMAL(10,3)
    DETERMINISTIC
    NO SQL
BEGIN
    -- IAU mean Earth radius. The choice matters at the third decimal place,
    -- so it is named rather than left as a magic number.
    DECLARE earth_radius_km DOUBLE DEFAULT 6371.0088;
    DECLARE dlat DOUBLE;
    DECLARE dlon DOUBLE;
    DECLARE a    DOUBLE;

    IF lat1 IS NULL OR lon1 IS NULL OR lat2 IS NULL OR lon2 IS NULL THEN
        RETURN NULL;
    END IF;

    SET dlat = RADIANS(lat2 - lat1);
    SET dlon = RADIANS(lon2 - lon1);

    SET a = POW(SIN(dlat / 2), 2)
          + COS(RADIANS(lat1)) * COS(RADIANS(lat2)) * POW(SIN(dlon / 2), 2);

    -- ATAN2 rather than ASIN: ASIN loses precision for nearly-antipodal
    -- points, and LEAST() guards a > 1 from floating-point rounding, which
    -- would make SQRT(1 - a) the square root of a negative number.
    RETURN earth_radius_km * 2 * ATAN2(SQRT(LEAST(a, 1.0)), SQRT(GREATEST(1.0 - a, 0.0)));
END$$

DELIMITER ;
