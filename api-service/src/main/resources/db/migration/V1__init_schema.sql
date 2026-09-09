-- V1__init_schema.sql
-- Part 2: Initial DynaFare database schema

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'RIDER',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE drivers (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    license_no   VARCHAR(50) NOT NULL UNIQUE,
    vehicle_type VARCHAR(50) NOT NULL DEFAULT 'SEDAN',
    status       VARCHAR(20) NOT NULL DEFAULT 'OFFLINE',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE quotes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rider_id        UUID NOT NULL REFERENCES users(id),
    pickup_lat      DOUBLE PRECISION NOT NULL,
    pickup_lon      DOUBLE PRECISION NOT NULL,
    dropoff_lat     DOUBLE PRECISION NOT NULL,
    dropoff_lon     DOUBLE PRECISION NOT NULL,
    predicted_price NUMERIC(10,2) NOT NULL,
    predicted_eta   NUMERIC(6,1) NOT NULL,
    surge_multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    confidence      NUMERIC(4,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE trips (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rider_id    UUID NOT NULL REFERENCES users(id),
    driver_id   UUID REFERENCES drivers(id),
    pickup_lat  DOUBLE PRECISION NOT NULL,
    pickup_lon  DOUBLE PRECISION NOT NULL,
    dropoff_lat DOUBLE PRECISION NOT NULL,
    dropoff_lon DOUBLE PRECISION NOT NULL,
    status      VARCHAR(30) NOT NULL DEFAULT 'REQUESTED',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE bookings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id          UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    quote_id         UUID REFERENCES quotes(id),
    quoted_price     NUMERIC(10,2) NOT NULL,
    final_price      NUMERIC(10,2),
    surge_multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    status           VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_quotes_rider_id ON quotes(rider_id);
CREATE INDEX idx_trips_rider_id ON trips(rider_id);
CREATE INDEX idx_trips_driver_id ON trips(driver_id);
CREATE INDEX idx_trips_status ON trips(status);
CREATE INDEX idx_bookings_trip_id ON bookings(trip_id);
CREATE INDEX idx_drivers_status ON drivers(status);
