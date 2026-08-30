# pylint: disable=invalid-name
import os

from mongodb_migrations.base import BaseMigration
from pymongo import ASCENDING, DESCENDING

from src.common.mongo import get_collection

DEPLOY_APP = os.environ['DEPLOY_APP']
MONGO_CREDENTIALS_SECRET_NAME = f'/{DEPLOY_APP}-secrets/MongoCredentials'
INDEX = [('city', ASCENDING), ('occurred_at', DESCENDING)]


class Migration(BaseMigration):
    """Speeds up "accidents in city X, most recent first" queries."""

    def upgrade(self):
        get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                       'accidentReports').create_index(INDEX)
        print('Created city+occurred_at index on accidentReports.')

    def downgrade(self):
        get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                       'accidentReports').drop_index(INDEX)
        print('Dropped city+occurred_at index on accidentReports.')
