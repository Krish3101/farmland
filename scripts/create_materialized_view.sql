-- Create a helper function for Silent Healing of coordinates
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

    -- Space Eradication
    coord := REPLACE(coord, ' ', '');
    IF coord NOT LIKE '%,%' THEN
        RETURN NULL;
    END IF;

    lat_str := SPLIT_PART(coord, ',', 1);
    lon_str := SPLIT_PART(coord, ',', 2);

    -- Decimal Auto-Injection for Lat
    IF STRPOS(lat_str, '.') = 0 AND LENGTH(lat_str) > 2 THEN
        lat_str := SUBSTRING(lat_str FROM 1 FOR 2) || '.' || SUBSTRING(lat_str FROM 3);
    END IF;

    -- Decimal Auto-Injection for Lon
    IF STRPOS(lon_str, '.') = 0 AND LENGTH(lon_str) > 2 THEN
        lon_str := SUBSTRING(lon_str FROM 1 FOR 2) || '.' || SUBSTRING(lon_str FROM 3);
    END IF;

    -- Convert to numeric for bounds checking
    BEGIN
        lat_val := lat_str::numeric;
        lon_val := lon_str::numeric;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;

    -- India Bounds Lat/Lon Swap
    -- India Lat: 6 to 38, Lon: 66 to 98
    -- If values are reversed, swap them back
    IF (lat_val >= 66 AND lat_val <= 98) AND (lon_val >= 6 AND lon_val <= 38) THEN
        temp := lat_val;
        lat_val := lon_val;
        lon_val := temp;
    END IF;

    -- Return PostGIS text format: Lon Lat
    RETURN lon_val::text || ' ' || lat_val::text;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Recreate the materialized view
DROP MATERIALIZED VIEW IF EXISTS processed_farm_geojson;

CREATE MATERIALIZED VIEW processed_farm_geojson AS
WITH raw_parsed AS (
    SELECT 
        "Unnamed: 3"::text AS farm_id,
        clean_coordinate("Unnamed: 7"::text) AS p1,
        clean_coordinate("Unnamed: 8"::text) AS p2,
        clean_coordinate("Unnamed: 9"::text) AS p3,
        clean_coordinate("Unnamed: 10"::text) AS p4
    FROM raw_farmers_data
    WHERE "Unnamed: 1" NOT IN ('Sr. No.', 'NaN') AND "Unnamed: 1" IS NOT NULL
      AND "Unnamed: 3" IS NOT NULL
),
geometries AS (
    SELECT 
        farm_id,
        -- Group points as a MULTIPOINT and let ST_ConvexHull draw the correct outer boundary
        ST_ConvexHull(ST_GeomFromText('MULTIPOINT(' || p1 || ',' || p2 || ',' || p3 || ',' || p4 || ')')) as geometry
    FROM raw_parsed
    WHERE p1 IS NOT NULL AND p2 IS NOT NULL AND p3 IS NOT NULL AND p4 IS NOT NULL
)
SELECT 
    farm_id,
    ST_AsGeoJSON(ST_MakeValid(ST_SetSRID(geometry, 4326)))::json AS geojson
FROM geometries;

-- Create unique index to allow concurrent refreshes
CREATE UNIQUE INDEX idx_processed_farm_geojson_farm_id ON processed_farm_geojson (farm_id);
