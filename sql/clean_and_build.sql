-- sql/clean_and_build.sql
-- Cleans raw coordinate strings, builds CCW convex hulls, and materializes GeoJSON.
-- Run by scripts/ingest.py, in the same transaction that loads raw_farms.

CREATE EXTENSION IF NOT EXISTS postgis;

DROP VIEW IF EXISTS farm_rejections;
DROP MATERIALIZED VIEW IF EXISTS farms;
DROP VIEW IF EXISTS farm_candidates;
DROP FUNCTION IF EXISTS clean_corner(text);

CREATE FUNCTION clean_corner(coord text) RETURNS geometry(Point, 4326)
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE AS $$
DECLARE
    lat_str text;
    lon_str text;
    lat numeric;
    lon numeric;
    t numeric;
BEGIN
    coord := regexp_replace(coord, '[\s°]+', '', 'g');
    IF coord !~ '^\d+(\.\d+)?,\d+(\.\d+)?$' THEN
        RETURN NULL;
    END IF;

    lat_str := split_part(coord, ',', 1);
    lon_str := split_part(coord, ',', 2);

    -- Missing decimal point: assume a 2-digit integer part (India operating region)
    IF strpos(lat_str, '.') = 0 AND length(lat_str) > 2 THEN
        lat_str := left(lat_str, 2) || '.' || substr(lat_str, 3);
    END IF;
    IF strpos(lon_str, '.') = 0 AND length(lon_str) > 2 THEN
        lon_str := left(lon_str, 2) || '.' || substr(lon_str, 3);
    END IF;

    lat := lat_str::numeric;
    lon := lon_str::numeric;

    -- Swap lat/lon if entered in reverse (operating region: lat 6-38, lon 66-98)
    IF lat BETWEEN 66 AND 98 AND lon BETWEEN 6 AND 38 THEN
        t := lat;
        lat := lon;
        lon := t;
    END IF;

    -- Validate bounds within India region
    IF lat NOT BETWEEN 6 AND 38 OR lon NOT BETWEEN 66 AND 98 THEN
        RETURN NULL;
    END IF;

    RETURN ST_SetSRID(ST_MakePoint(lon, lat), 4326);
END $$;

CREATE VIEW farm_candidates AS
WITH raw_parsed AS (
    SELECT
        -- Rows with a serial number but no usable id get 'row <serial>' so they can be found.
        CASE WHEN id_missing THEN 'row ' || TRIM(serial_no)
             ELSE TRIM(phone) END AS farm_id,
        id_missing,
        clean_corner(corner_a) AS a,
        clean_corner(corner_b) AS b,
        clean_corner(corner_c) AS c,
        clean_corner(corner_d) AS d,
        -- Missing ids are never duplicates of each other.
        CASE WHEN id_missing THEN 1
             ELSE COUNT(*) OVER (PARTITION BY id_missing, TRIM(phone)) END AS n
    FROM (
        SELECT *,
            (phone IS NULL
             OR TRIM(phone) = ''
             OR TRIM(phone) IN ('NaN', 'None')) AS id_missing
        FROM raw_farms
        WHERE serial_no IS NOT NULL
    ) AS data_rows
),
hulls AS (
    SELECT
        farm_id,
        a, b, c, d, n, id_missing,
        CASE
            WHEN a IS NOT NULL AND b IS NOT NULL AND c IS NOT NULL AND d IS NOT NULL
            THEN ST_ForcePolygonCCW(ST_ConvexHull(ST_Collect(ARRAY[a, b, c, d])))
            ELSE NULL
        END AS geom
    FROM raw_parsed
)
SELECT farm_id, geom,
    CASE
        WHEN id_missing THEN 'missing farm_id'
        WHEN n > 1 THEN 'duplicate farm_id'
        WHEN a IS NULL THEN 'corner A unparseable'
        WHEN b IS NULL THEN 'corner B unparseable'
        WHEN c IS NULL THEN 'corner C unparseable'
        WHEN d IS NULL THEN 'corner D unparseable'
        WHEN GeometryType(geom) <> 'POLYGON' THEN 'corners collinear or identical'
    END AS reject_reason
FROM hulls;

CREATE MATERIALIZED VIEW farms AS
SELECT farm_id,
       geom::geometry(Polygon, 4326) AS geom,
       round(ST_Area(geom::geography)::numeric, 1) AS area_m2,
       ST_AsGeoJSON(geom)::json AS geojson
FROM farm_candidates
WHERE reject_reason IS NULL;

CREATE UNIQUE INDEX farms_farm_id_idx ON farms (farm_id);

CREATE VIEW farm_rejections AS
SELECT farm_id, reject_reason
FROM farm_candidates
WHERE reject_reason IS NOT NULL;
