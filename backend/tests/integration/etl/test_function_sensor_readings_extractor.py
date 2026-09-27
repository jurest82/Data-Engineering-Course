import json
import os

from tests.repositories.sqs_connection import drain_queue


def test_sensor_readings_extractor_forwards_documents_to_dispatcher(sqs_client):
    # ARRANGE
    os.environ['DISPATCHER_QUEUE_URL'] = os.environ[
        'SENSOR_READINGS_DISPATCHER_QUEUE_URL']
    from src.common import mongo
    from src.sensor_readings_extractor import (
        handler as sensor_readings_extractor,
    )

    collection = mongo.get_collection(
        os.environ['MONGO_CREDENTIALS_SECRET_NAME'], 'trafficSensorReadings')
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
    sensor_readings_extractor.handler(event, None)

    # ASSERT
    messages = drain_queue(sqs_client,
                           os.environ['SENSOR_READINGS_DISPATCHER_QUEUE_URL'])
    assert len(messages) == 12
    forwarded_ids = {
        json.loads(message['Body'])['_id']
        for message in messages
    }
    assert forwarded_ids == {str(oid)
                             for oid in inserted.inserted_ids}
