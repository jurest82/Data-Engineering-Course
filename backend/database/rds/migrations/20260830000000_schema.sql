CREATE TABLE cities (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

INSERT INTO cities (name) VALUES
    ('Bogotá'),
    ('Medellín'),
    ('Cali'),
    ('Barranquilla');

CREATE TABLE severities (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code TEXT UNIQUE NOT NULL
);

INSERT INTO severities (code) VALUES
    ('minor'),
    ('moderate'),
    ('severe'),
    ('fatal');

CREATE TABLE roads (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities (id),
    name TEXT NOT NULL,
    UNIQUE (city_id, name)
);

CREATE TABLE sensors (
    id TEXT PRIMARY KEY
);

CREATE TABLE accident_reports (
    id TEXT PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL,
    city_id INTEGER NOT NULL REFERENCES cities (id),
    road_id INTEGER NOT NULL REFERENCES roads (id),
    severity_id INTEGER NOT NULL REFERENCES severities (id),
    vehicles_involved INTEGER NOT NULL,
    source_s3_key TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE sensor_readings (
    id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL REFERENCES sensors (id),
    city_id INTEGER NOT NULL REFERENCES cities (id),
    road_id INTEGER NOT NULL REFERENCES roads (id),
    speed_avg NUMERIC(5, 1) NOT NULL,
    vehicle_count INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
