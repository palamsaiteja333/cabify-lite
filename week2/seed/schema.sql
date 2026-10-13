-- Cabify-Lite — Week 2 seed schema
--
-- Extends the Week 1 database. The `rides` table here is a superset of the
-- Week 1 one; if your Week 1 schema differs, reconcile rather than replacing —
-- reconciling someone else's schema with your own is the actual exercise.
--
-- Run:  psql "$DATABASE_URL" -f seed/schema.sql

BEGIN;

DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS rides;
DROP TABLE IF EXISTS riders;
DROP TABLE IF EXISTS drivers;

CREATE TABLE riders (
    rider_id   integer PRIMARY KEY,
    name       text        NOT NULL,
    joined_at  timestamptz NOT NULL,
    city       text        NOT NULL,
    rating     numeric(3,2)
);

CREATE TABLE drivers (
    driver_id    integer PRIMARY KEY,
    name         text        NOT NULL,
    joined_at    timestamptz NOT NULL,
    city         text        NOT NULL,
    rating       numeric(3,2),
    vehicle_type text        NOT NULL
);

CREATE TABLE rides (
    ride_id             integer PRIMARY KEY,
    rider_id            integer     NOT NULL REFERENCES riders(rider_id),
    -- nullable on purpose: some bookings are cancelled before allocation
    driver_id           integer     REFERENCES drivers(driver_id),
    requested_at        timestamptz NOT NULL,
    started_at          timestamptz,
    completed_at        timestamptz,
    pickup              text        NOT NULL,
    dropoff             text        NOT NULL,
    distance_km         numeric(6,2),
    duration_min        integer,
    fare_amount         numeric(10,2) NOT NULL DEFAULT 0,
    currency            char(3)     NOT NULL DEFAULT 'INR',
    status              text        NOT NULL,
    cancelled_at        timestamptz,
    cancellation_reason text,
    CONSTRAINT rides_status_chk CHECK (status IN (
        'completed', 'cancelled_by_rider', 'cancelled_by_driver', 'no_show', 'disputed'
    ))
    -- NOTE: there is deliberately NO constraint enforcing completed_at > started_at.
    -- Two rows violate it. Adding the constraint is a legitimate thing to propose;
    -- doing so before you have noticed the rows is not.
);

CREATE TABLE refunds (
    refund_id integer PRIMARY KEY,
    ride_id   integer       NOT NULL REFERENCES rides(ride_id),
    amount    numeric(10,2) NOT NULL,
    reason    text          NOT NULL,
    issued_at timestamptz   NOT NULL,
    issued_by text          NOT NULL,
    CONSTRAINT refunds_reason_chk CHECK (reason IN (
        'driver_cancelled', 'service_issue', 'no_show_contested', 'goodwill'
    ))
);

CREATE INDEX rides_requested_at_idx ON rides (requested_at);
CREATE INDEX rides_status_idx       ON rides (status);
CREATE INDEX rides_rider_idx        ON rides (rider_id);
CREATE INDEX refunds_ride_idx       ON refunds (ride_id);
CREATE INDEX refunds_issued_at_idx  ON refunds (issued_at);

COMMIT;