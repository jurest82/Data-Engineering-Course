CREATE EXTENSION IF NOT EXISTS pg_cron;

CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;

SELECT cron.schedule(
    'sensor_readings_partman_maintenance',
    '0 3 * * *',
    $$CALL partman.run_maintenance_proc()$$
);
