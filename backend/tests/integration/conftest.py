import os
import subprocess

import pytest

from tests.repositories.connection import delete_all

MIGRATE_SCRIPT = os.path.join(os.path.dirname(__file__), '..', '..', 'database',
                              'migrations', 'migrate.sh')
RDS_MIGRATE_SCRIPT = os.path.join(os.path.dirname(__file__), '..', '..',
                                  'database', 'rds', 'migrate.sh')
# Only schema + indexes: pg_partman/pg_cron (needed by the partitioning
# migration) aren't available on the stock local Postgres image, and no
# Lambda's correctness depends on sensor_readings actually being partitioned.
# yoyo's --revision doesn't chain dependencies for these plain SQL migrations
# (no depends_on declared), so each target is applied in its own call.
RDS_TARGET_REVISIONS = ['20260830000000_schema', '20260830000001_indexes']


@pytest.fixture(autouse=True, scope='session')
def arrange():
    """Execute arrange at the beginning of test session."""
    subprocess.run([MIGRATE_SCRIPT], check=True)
    for revision in RDS_TARGET_REVISIONS:
        subprocess.run([RDS_MIGRATE_SCRIPT, '', revision], check=True)
    yield


@pytest.fixture(autouse=True)
def test_cleanup():
    yield
    delete_all('smokeTest')
    delete_all('accidentReports')
    delete_all('trafficSensorReadings')
