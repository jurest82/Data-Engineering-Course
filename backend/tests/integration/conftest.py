import os
import subprocess

import pytest

from tests.repositories.connection import delete_all

MIGRATE_SCRIPT = os.path.join(os.path.dirname(__file__), '..', '..', 'database',
                              'migrations', 'migrate.sh')


@pytest.fixture(autouse=True, scope='session')
def arrange():
    """Execute arrange at the beginning of test session."""
    subprocess.run([MIGRATE_SCRIPT], check=True)
    yield


@pytest.fixture(autouse=True)
def test_cleanup():
    yield
    delete_all('smokeTest')
    delete_all('accidentReports')
    delete_all('trafficSensorReadings')
