-- fn_haversine_km against distances that can be checked against an atlas.
SELECT 'delhi_chennai' AS leg, fn_haversine_km(28.613900, 77.209000, 13.082700, 80.270700) AS km;
SELECT 'delhi_mumbai'  AS leg, fn_haversine_km(28.613900, 77.209000, 19.076000, 72.877700) AS km;
SELECT 'same_point'    AS leg, fn_haversine_km(13.082700, 80.270700, 13.082700, 80.270700) AS km;
SELECT 'antipodal'     AS leg, fn_haversine_km(0, 0, 0, 180) AS km;
SELECT 'null_input'    AS leg, fn_haversine_km(NULL, 77.209000, 13.082700, 80.270700) AS km;
-- Symmetry: distance does not depend on which end you start from.
SELECT 'symmetric'     AS leg,
       fn_haversine_km(28.613900, 77.209000, 13.082700, 80.270700)
     = fn_haversine_km(13.082700, 80.270700, 28.613900, 77.209000) AS same_both_ways;
