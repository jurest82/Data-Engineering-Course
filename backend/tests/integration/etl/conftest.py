import os

import pytest

from tests.repositories.postgres_connection import (
    fetch_all,
    get_connection,
    truncate,
)

QUEUE_URL_ENV_VARS = (
    'ACCIDENT_REPORTS_EXTRACTOR_QUEUE_URL',
    'ACCIDENT_REPORTS_DISPATCHER_QUEUE_URL',
    'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL',
    'SENSOR_READINGS_EXTRACTOR_QUEUE_URL',
    'SENSOR_READINGS_DISPATCHER_QUEUE_URL',
    'SENSOR_READINGS_TRANSFORMER_DLQ_URL',
)

PRIMARY_KEY_COLUMNS_QUERY = '''
    SELECT a.attname
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
    WHERE i.indrelid = 'sensor_readings'::regclass AND i.indisprimary
'''


@pytest.fixture(autouse=True, scope='session')
def ensure_sensor_readings_composite_pk(arrange):
    """Reproduce migration 20260830000003's composite key, sans pg_partman."""
    columns = {row[0]
               for row in fetch_all(PRIMARY_KEY_COLUMNS_QUERY)}
    if columns != {'id', 'recorded_at'}:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE sensor_readings '
                           'DROP CONSTRAINT sensor_readings_pkey')
            cursor.execute(
                'ALTER TABLE sensor_readings ADD PRIMARY KEY (id, recorded_at)')
        connection.commit()


@pytest.fixture(autouse=True)
def etl_cleanup(sqs_client):
    yield
    for env_var in QUEUE_URL_ENV_VARS:
        sqs_client.purge_queue(QueueUrl=os.environ[env_var])
    truncate('accident_reports', 'sensor_readings', 'roads', 'sensors')
