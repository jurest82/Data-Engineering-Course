import os

from src.common import mongo
from tests.repositories.connection import get_database


def test_get_collection_connects_to_the_local_mongo(secrets_manager_client):
    # ARRANGE
    secret_name = os.environ['MONGO_CREDENTIALS_SECRET_NAME']

    # ACT
    collection = mongo.get_collection(secret_name, 'smokeTest')
    collection.insert_one({
        'value': 'hello'
    })

    # ASSERT
    document = get_database()['smokeTest'].find_one({
        'value': 'hello'
    })
    assert document is not None


def test_accident_reports_index_is_applied():
    # ARRANGE / ACT
    indexes = get_database()['accidentReports'].index_information()

    # ASSERT
    keys = [info['key'] for info in indexes.values()]
    assert [('city', 1), ('occurred_at', -1)] in keys
