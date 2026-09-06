import datetime as dt
import json
import os

import boto3

from src.common import mongo
from src.common.etl import publish_to_etl
from src.common.sensor_readings import validate_reading

sqs_client = boto3.client('sqs')
sns_client = boto3.client('sns')

MONGO_CREDENTIALS_SECRET_NAME = os.environ['MONGO_CREDENTIALS_SECRET_NAME']
SENSOR_READINGS_DLQ_URL = os.environ['SENSOR_READINGS_DLQ_URL']
SENSOR_READINGS_ETL_TOPIC_ARN = os.environ['SENSOR_READINGS_ETL_TOPIC_ARN']

MONGO_COLLECTION_NAME = 'trafficSensorReadings'

# Must match what the backfill's Extractor sends, for both paths to converge.
ETL_FIELDS = (
    'sensor_id',
    'city',
    'road',
    'speed_avg',
    'vehicle_count',
    'recorded_at',
    'created_at',
    'updated_at',
)


def handler(event, context):
    for record in event['Records']:
        _process_record(record)


def _process_record(record):
    reading = json.loads(record['body'])
    # The sensor's payload has no sensor_id field -- it's derived entirely from
    # thing_name, which the IoT topic rule's topic(3) adds and the
    # SensorReadingsPolicy guarantees matches the publishing certificate's
    # ThingName, so it can't be spoofed by the device.
    reading['sensor_id'] = reading.pop('thing_name', None)
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
    result = collection.insert_one(document)
    publish_to_etl(sns_client, SENSOR_READINGS_ETL_TOPIC_ARN, document,
                   result.inserted_id, ETL_FIELDS)


def _send_to_dlq(reading, errors):
    body = dict(reading)
    body['validation_errors'] = errors
    sqs_client.send_message(QueueUrl=SENSOR_READINGS_DLQ_URL,
                            MessageBody=json.dumps(body))
