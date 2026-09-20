DROP TABLE sensor_readings;

CREATE TABLE sensor_readings (
    id TEXT NOT NULL,
    sensor_id TEXT NOT NULL REFERENCES sensors (id),
    city_id INTEGER NOT NULL REFERENCES cities (id),
    road_id INTEGER NOT NULL REFERENCES roads (id),
    speed_avg NUMERIC(5, 1) NOT NULL,
    vehicle_count INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

CREATE INDEX sensor_readings_sensor_id_recorded_at_idx
    ON sensor_readings (sensor_id, recorded_at DESC);

SELECT partman.create_parent(
    p_parent_table => 'public.sensor_readings',
    p_control => 'recorded_at',
    p_interval => '1 day',
    p_premake => 4,
    p_start_partition => (CURRENT_DATE - INTERVAL '14 days')::text
);
