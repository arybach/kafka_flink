-- this code runs in the sql-client, so should be able to communicate via broker:29092 unencrypted port

DROP TABLE IF EXISTS fhv_trips;
CREATE TABLE fhv_trips (
  pickup_location_id INT,
  pickup_datetime TIMESTAMP(3),
  proctime AS PROCTIME()
) WITH (
  'connector' = 'kafka',
  'topic' = 'fhv-trips',
  'properties.bootstrap.servers' = 'broker:29092',
  'properties.group.id' = 'tripsdata',
  'properties.auto.offset.reset' = 'earliest',
  'json.timestamp-format.standard' = 'ISO-8601',
  'format' = 'json'
);

DROP TABLE IF EXISTS green_trips;
CREATE TABLE green_trips (
  pickup_location_id INT,
  pickup_datetime TIMESTAMP(3),
  proctime AS PROCTIME()
) WITH (
  'connector' = 'kafka',
  'topic' = 'green-trips',
  'properties.bootstrap.servers' = 'broker:29092',
  'properties.group.id' = 'tripsdata',
  'properties.auto.offset.reset' = 'earliest',
  'json.timestamp-format.standard' = 'ISO-8601',
  'format' = 'json'
);

-- test: union + count
-- SELECT
--   TUMBLE_START(proctime, INTERVAL '1' MINUTE) AS window_start,
--   TUMBLE_END(proctime, INTERVAL '1' MINUTE) AS window_end,
--   pickup_location_id,
--   COUNT(*) AS pickup_count
-- FROM (
--   SELECT pickup_location_id, proctime
--   FROM fhv_trips
--   UNION ALL
--   SELECT pickup_location_id, proctime
--   FROM green_trips
-- )
-- GROUP BY TUMBLE(proctime, INTERVAL '1' MINUTE), pickup_location_id;

-- test - read from topic
-- SELECT 
--   TUMBLE_START(proctime, INTERVAL '1' MINUTE) AS window_start, 
--   pickup_location_id, 
--   COUNT(*) AS pickup_count 
-- FROM fhv_trips 
-- GROUP BY 
--   TUMBLE(proctime, INTERVAL '1' MINUTE), 
--   pickup_location_id;

-- DROP TABLE IF EXISTS rolling_pickup_counts;
-- CREATE TABLE rolling_pickup_counts (
--     window_start TIMESTAMP(3),
--     window_end TIMESTAMP(3),
--     pickup_location_id BIGINT,
--     pickup_count BIGINT,
--     proctime AS PROCTIME()
-- ) WITH (
--     'connector' = 'filesystem',
--     'format' = 'csv',
--     'path' = '/data/rolling_pickup_counts',
--     'sink.rolling-policy.file-size' = '128MB',
--     'sink.rolling-policy.rollover-interval' = '1h',
--     'sink.rolling-policy.check-interval' = '10s',
--     'sink.parallelism' = '4'
-- );

-- popular location window
DROP TABLE IF EXISTS popular_pickup_location;
CREATE TABLE popular_pickup_location (
    window_start TIMESTAMP(3),
    window_end TIMESTAMP(3),
    pickup_location_id INT,
    pickup_count BIGINT
) WITH (
    'connector' = 'kafka',
    'topic' = 'popular-pickup-location',
    'properties.bootstrap.servers' = 'broker:29092',
    'properties.group.id' = 'tripsdata',
    'properties.auto.offset.reset' = 'earliest',
    'format' = 'json',
    'json.fail-on-missing-field' = 'false',
    'json.ignore-parse-errors' = 'true'
);

-- create to count all pickups for each location id during a rolling time interval
INSERT INTO popular_pickup_location
SELECT
    TUMBLE_START(proctime, INTERVAL '10' MINUTE) AS window_start,
    TUMBLE_END(proctime, INTERVAL '10' MINUTE) AS window_end,
    pickup_location_id,
    CAST(COUNT(*) AS BIGINT) AS pickup_count
FROM (
    SELECT pickup_location_id, proctime
    FROM fhv_trips
    UNION ALL
    SELECT pickup_location_id, proctime
    FROM green_trips
)
GROUP BY TUMBLE(proctime, INTERVAL '10' MINUTE), pickup_location_id;

-- highest count location id for each interval
-- SELECT window_start, window_end, pickup_location_id, pickup_count
-- FROM (
--     SELECT TUMBLE_START(proctime, INTERVAL '30' MINUTE) AS window_start,
--            TUMBLE_END(proctime, INTERVAL '30' MINUTE) AS window_end,
--            pickup_location_id,
--            CAST(COUNT(*) AS BIGINT) AS pickup_count,
--            ROW_NUMBER() OVER (PARTITION BY TUMBLE_START(proctime, INTERVAL '30' MINUTE), pickup_location_id
--                               ORDER BY COUNT(*) DESC) as row_num
--     FROM (
--         SELECT pickup_location_id, proctime
--         FROM fhv_trips
--         UNION ALL
--         SELECT pickup_location_id, proctime
--         FROM green_trips
--     )
--     GROUP BY TUMBLE(proctime, INTERVAL '30' MINUTE), pickup_location_id
-- )
-- WHERE row_num = 1;

-- create table for top locations aggregated over previous data
DROP TABLE IF EXISTS top_pickup_location;
CREATE TABLE top_pickup_location (
    pickup_location_id INT,
    pickup_count BIGINT,
    window_start TIMESTAMP(3),
    window_end TIMESTAMP(3)
) WITH (
    'connector' = 'kafka',
    'topic' = 'top-pickup-location',
    'properties.bootstrap.servers' = 'broker:29092',
    'properties.group.id' = 'tripsdata',
    'properties.auto.offset.reset' = 'earliest',
    'format' = 'json',
    'json.fail-on-missing-field' = 'false',
    'json.ignore-parse-errors' = 'true'
);

-- aggregate windowed 
INSERT INTO top_pickup_location
SELECT
    pickup_location_id,
    SUM(pickup_count) AS total_pickup_count,
    TUMBLE_START(proctime(), INTERVAL '60' MINUTE) AS window_start,
    TUMBLE_END(proctime(), INTERVAL '60' MINUTE) AS window_end
FROM popular_pickup_location
GROUP BY
    pickup_location_id,
    TUMBLE(proctime(), INTERVAL '60' MINUTE);

SELECT * FROM top_pickup_location;
