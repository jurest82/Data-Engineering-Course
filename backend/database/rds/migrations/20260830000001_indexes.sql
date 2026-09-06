CREATE INDEX accident_reports_city_id_occurred_at_idx
    ON accident_reports (city_id, occurred_at DESC);

CREATE INDEX sensor_readings_sensor_id_recorded_at_idx
    ON sensor_readings (sensor_id, recorded_at DESC);
