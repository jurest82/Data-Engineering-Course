DELETE FROM partman.part_config WHERE parent_table = 'public.sensor_readings';

DROP TABLE sensor_readings;

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

CREATE INDEX sensor_readings_sensor_id_recorded_at_idx
    ON sensor_readings (sensor_id, recorded_at DESC);
