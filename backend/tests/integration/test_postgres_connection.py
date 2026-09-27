import os

from src.common import postgres
from src.common.accident_reports import SEVERITY_TRANSLATIONS
from src.common.cities import ALLOWED_CITIES
from tests.repositories.postgres_connection import fetch_all


def test_get_connection_connects_to_the_local_postgres():
    # ARRANGE
    secret_name = os.environ['RDS_CREDENTIALS_SECRET_NAME']

    # ACT
    connection = postgres.get_connection(secret_name)
    connection.rollback()
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        result = cursor.fetchone()

    # ASSERT
    assert result == (1, )


def test_cities_and_severities_are_pre_seeded():
    # ARRANGE / ACT
    cities = {row[0]
              for row in fetch_all('SELECT name FROM cities')}
    severities = {row[0]
                  for row in fetch_all('SELECT code FROM severities')}

    # ASSERT
    assert cities == ALLOWED_CITIES
    assert severities == set(SEVERITY_TRANSLATIONS.values())
