import json
import os

import pytest

from tests.repositories.sqs_connection import drain_queue


def test_accident_reports_extractor_forwards_documents_to_dispatcher(
        sqs_client):
    # ARRANGE
    os.environ['DISPATCHER_QUEUE_URL'] = os.environ[
        'ACCIDENT_REPORTS_DISPATCHER_QUEUE_URL']
    from src.accident_reports_extractor import (
        handler as accident_reports_extractor, )
    from src.common import mongo

    collection = mongo.get_collection(
        os.environ['MONGO_CREDENTIALS_SECRET_NAME'], 'accidentReports')
    inserted = collection.insert_many([{
        'seed_index': index
    } for index in range(12)])
    event = {
        'Records': [{
            'body': json.dumps({
                'skip': 0,
                'limit': 20
            })
        }]
    }

    # ACT
    accident_reports_extractor.handler(event, None)

    # ASSERT
    messages = drain_queue(sqs_client,
                           os.environ['ACCIDENT_REPORTS_DISPATCHER_QUEUE_URL'])
    assert len(messages) == 12
    forwarded_ids = {
        json.loads(message['Body'])['_id']
        for message in messages
    }
    assert forwarded_ids == {str(oid)
                             for oid in inserted.inserted_ids}


def test_accident_reports_extractor_raises_on_malformed_message(sqs_client):
    # ARRANGE
    os.environ['DISPATCHER_QUEUE_URL'] = os.environ[
        'ACCIDENT_REPORTS_DISPATCHER_QUEUE_URL']
    from src.accident_reports_extractor import (
        handler as accident_reports_extractor, )

    event = {
        'Records': [{
            'body': 'not-json'
        }]
    }

    # ACT / ASSERT
    with pytest.raises(json.JSONDecodeError):
        accident_reports_extractor.handler(event, None)

    messages = drain_queue(sqs_client,
                           os.environ['ACCIDENT_REPORTS_DISPATCHER_QUEUE_URL'])
    assert not messages
