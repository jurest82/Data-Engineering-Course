import datetime as dt
import json
import os

import boto3

from src.common import mongo
from src.common.sensor_readings import validate_reading

sqs_client = boto3.client('sqs')

MONGO_CREDENTIALS_SECRET_NAME = os.environ['MONGO_CREDENTIALS_SECRET_NAME']
SENSOR_READINGS_DLQ_URL = os.environ['SENSOR_READINGS_DLQ_URL']

MONGO_COLLECTION_NAME = 'trafficSensorReadings'


def handler(event, context):
    for record in event['Records']:
        _process_record(record)


def _process_record(record):
    reading = json.loads(record['body'])
    errors = validate_reading(reading)
    if errors:
        _send_to_dlq(reading, errors)
        return

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    document = dict(reading)
    document['created_at'] = now
    document['updated_at'] = now

    collection = mongo.get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                      MONGO_COLLECTION_NAME)
    collection.insert_one(document)


def _send_to_dlq(reading, errors):
    body = dict(reading)
    body['validation_errors'] = errors
    sqs_client.send_message(QueueUrl=SENSOR_READINGS_DLQ_URL,
                            MessageBody=json.dumps(body))
