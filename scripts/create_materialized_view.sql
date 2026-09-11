-- Helper function to clean and validate individual coordinate strings
CREATE OR REPLACE FUNCTION clean_coordinate(coord text) RETURNS text AS $$
DECLARE
    lat_str text;
    lon_str text;
    lat_val numeric;
    lon_val numeric;
    temp numeric;
BEGIN
    IF coord IS NULL THEN
        RETURN NULL;
    END IF;

    -- Remove all whitespace (spaces, tabs, newlines)
    coord := REGEXP_REPLACE(coord, '\s+', '', 'g');

    -- Must be exactly one comma separating two non-empty parts
    IF coord NOT LIKE '%,%' OR coord LIKE '%,%,%' THEN
        RETURN NULL;
    END IF;

    lat_str := SPLIT_PART(coord, ',', 1);
    lon_str := SPLIT_PART(coord, ',', 2);

    IF lat_str = '' OR lon_str = '' THEN
        RETURN NULL;
    END IF;

    -- Insert the decimal point when it is missing and the value is longer than 2 digits
    IF STRPOS(lat_str, '.') = 0 AND LENGTH(lat_str) > 2 THEN
        lat_str := SUBSTRING(lat_str FROM 1 FOR 2) || '.' || SUBSTRING(lat_str FROM 3);
    END IF;

    IF STRPOS(lon_str, '.') = 0 AND LENGTH(lon_str) > 2 THEN
        lon_str := SUBSTRING(lon_str FROM 1 FOR 2) || '.' || SUBSTRING(lon_str FROM 3);
    END IF;

    -- Reject anything that is not numeric
    BEGIN
        lat_val := lat_str::numeric;
        lon_val := lon_str::numeric;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;

    -- Swap lat/lon when they were entered the wrong way round
    -- Operating region: Latitude 6 to 38, Longitude 66 to 98
    -- If first value is in longitude range and second in latitude range, swap
    IF (lat_val >= 66 AND lat_val <= 98) AND (lon_val >= 6 AND lon_val <= 38) THEN
        temp := lat_val;
        lat_val := lon_val;
        lon_val := temp;
    END IF;

    -- Return PostGIS WKT text: Lon Lat (X Y)
    RETURN lon_val::text || ' ' || lat_val::text;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Drop and recreate the materialized view
DROP MATERIALIZED VIEW IF EXISTS processed_farm_geojson;

CREATE MATERIALIZED VIEW processed_farm_geojson AS
WITH raw_parsed AS (
    SELECT 
        TRIM("Unnamed: 3"::text) AS farm_id,
        clean_coordinate("Unnamed: 7"::text) AS p1,
        clean_coordinate("Unnamed: 8"::text) AS p2,
        clean_coordinate("Unnamed: 9"::text) AS p3,
        clean_coordinate("Unnamed: 10"::text) AS p4
    FROM raw_farmers_data
    WHERE "Unnamed: 1" NOT IN ('Sr. No.', 'NaN') AND "Unnamed: 1" IS NOT NULL
      AND "Unnamed: 3" IS NOT NULL
      AND TRIM("Unnamed: 3"::text) != ''
      AND TRIM("Unnamed: 3"::text) NOT IN ('NaN', 'None', 'Sr. No.')
),
geometries AS (
    SELECT 
        farm_id,
        -- Smallest shape enclosing all four corners
        ST_ConvexHull(ST_GeomFromText('MULTIPOINT(' || p1 || ',' || p2 || ',' || p3 || ',' || p4 || ')')) AS geometry
    FROM raw_parsed
    -- Only usable if all four corners cleaned successfully
    WHERE p1 IS NOT NULL AND p2 IS NOT NULL AND p3 IS NOT NULL AND p4 IS NOT NULL
),
valid_polygons AS (
    SELECT 
        -- One row per farm
        DISTINCT ON (farm_id) farm_id,
        -- Valid geometry, tagged as EPSG:4326
        ST_MakeValid(ST_SetSRID(geometry, 4326)) AS valid_geom
    FROM geometries
    -- Polygons only
    WHERE ST_GeometryType(geometry) IN ('ST_Polygon', 'ST_MultiPolygon')
    ORDER BY farm_id
)
SELECT 
    farm_id,
    ST_AsGeoJSON(valid_geom)::json AS geojson
FROM valid_polygons;

-- Unique index: needed for fast lookups and for REFRESH ... CONCURRENTLY
CREATE UNIQUE INDEX idx_processed_farm_geojson_farm_id ON processed_farm_geojson (farm_id);
