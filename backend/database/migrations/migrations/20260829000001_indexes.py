# pylint: disable=invalid-name
import os

from mongodb_migrations.base import BaseMigration
from pymongo import ASCENDING, DESCENDING

from src.common.mongo import get_collection

DEPLOY_APP = os.environ['DEPLOY_APP']
MONGO_CREDENTIALS_SECRET_NAME = f'/{DEPLOY_APP}-secrets/MongoCredentials'
INDEX = [('sensor_id', ASCENDING), ('recorded_at', DESCENDING)]


class Migration(BaseMigration):
    """Speeds up "readings for sensor X, ordered by time" queries."""

    def upgrade(self):
        get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                       'trafficSensorReadings').create_index(INDEX)
        print('Created sensor_id+recorded_at index on trafficSensorReadings.')

    def downgrade(self):
        get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                       'trafficSensorReadings').drop_index(INDEX)
        print('Dropped sensor_id+recorded_at index on trafficSensorReadings.')
