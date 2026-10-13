-- Load the generated CSVs. Run from the week2/seed directory:
--
--   psql "$DATABASE_URL" -f schema.sql
--   psql "$DATABASE_URL" -v dir="$(pwd)/data" -f load.sql
--
-- \copy runs client-side, so this works against a Postgres in Docker without
-- the server needing access to your filesystem.

\set riders_csv  :dir '/riders.csv'
\set drivers_csv :dir '/drivers.csv'
\set rides_csv   :dir '/rides.csv'
\set refunds_csv :dir '/refunds.csv'

\copy riders  (rider_id, name, joined_at, city, rating)                                        FROM :'riders_csv'  WITH (FORMAT csv, HEADER true)
\copy drivers (driver_id, name, joined_at, city, rating, vehicle_type)                         FROM :'drivers_csv' WITH (FORMAT csv, HEADER true)
\copy rides   (ride_id, rider_id, driver_id, requested_at, started_at, completed_at, pickup, dropoff, distance_km, duration_min, fare_amount, currency, status, cancelled_at, cancellation_reason) FROM :'rides_csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy refunds (refund_id, ride_id, amount, reason, issued_at, issued_by)                       FROM :'refunds_csv' WITH (FORMAT csv, HEADER true)

-- Sanity output. Compare these against facilitator/trap_key.md section 2.
SELECT 'riders'  AS table_name, count(*) FROM riders
UNION ALL SELECT 'drivers', count(*) FROM drivers
UNION ALL SELECT 'rides',   count(*) FROM rides
UNION ALL SELECT 'refunds', count(*) FROM refunds;

SELECT status, count(*) AS rides, round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM rides GROUP BY status ORDER BY rides DESC;