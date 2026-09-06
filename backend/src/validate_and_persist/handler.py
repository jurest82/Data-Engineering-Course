import datetime as dt
import json
import os

import boto3

from src.common import mongo
from src.common.accident_reports import validate_row
from src.common.etl import publish_to_etl
from src.validate_and_persist import pii

sqs_client = boto3.client('sqs')
sns_client = boto3.client('sns')

MONGO_CREDENTIALS_SECRET_NAME = os.environ['MONGO_CREDENTIALS_SECRET_NAME']
ACCIDENT_REPORTS_DLQ_URL = os.environ['ACCIDENT_REPORTS_DLQ_URL']
ACCIDENT_REPORTS_ETL_TOPIC_ARN = os.environ['ACCIDENT_REPORTS_ETL_TOPIC_ARN']

MONGO_COLLECTION_NAME = 'accidentReports'

# Must match what the backfill's Extractor sends, for both paths to converge.
ETL_FIELDS = (
    'occurred_at',
    'city',
    'road',
    'severity',
    'vehicles_involved',
    'source_s3_key',
    'row_number',
    'created_at',
    'updated_at',
)


def handler(event, context):
    for record in event['Records']:
        _process_record(record)


def _process_record(record):
    row = json.loads(record['body'])
    errors = validate_row(row)
    if errors:
        _send_to_dlq(row, errors)
        return

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    document = dict(row)
    document['involved_person_name'] = pii.encrypt(
        document['involved_person_name'])
    document['involved_person_id'] = pii.encrypt(document['involved_person_id'])
    document['created_at'] = now
    document['updated_at'] = now

    collection = mongo.get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                      MONGO_COLLECTION_NAME)
    result = collection.insert_one(document)
    publish_to_etl(sns_client, ACCIDENT_REPORTS_ETL_TOPIC_ARN, document,
                   result.inserted_id, ETL_FIELDS)


def _send_to_dlq(row, errors):
    body = dict(row)
    body['validation_errors'] = errors
    sqs_client.send_message(QueueUrl=ACCIDENT_REPORTS_DLQ_URL,
                            MessageBody=json.dumps(body))
