SELECT cron.unschedule('sensor_readings_partman_maintenance');

DROP EXTENSION IF EXISTS pg_partman;
DROP SCHEMA IF EXISTS partman;

DROP EXTENSION IF EXISTS pg_cron;
