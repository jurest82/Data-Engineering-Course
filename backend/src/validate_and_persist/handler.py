import datetime as dt
import json
import os

import boto3
from pymongo import MongoClient

from src.common.accident_reports import validate_row
from src.validate_and_persist import pii

secrets_client = boto3.client('secretsmanager')
sqs_client = boto3.client('sqs')

MONGO_CREDENTIALS_SECRET_NAME = os.environ['MONGO_CREDENTIALS_SECRET_NAME']
ACCIDENT_REPORTS_DLQ_URL = os.environ['ACCIDENT_REPORTS_DLQ_URL']

MONGO_COLLECTION_NAME = 'accidentReports'

_MONGO_CLIENT = None
_MONGO_DBNAME = None


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

    _get_collection().insert_one(document)


def _send_to_dlq(row, errors):
    body = dict(row)
    body['validation_errors'] = errors
    sqs_client.send_message(QueueUrl=ACCIDENT_REPORTS_DLQ_URL,
                            MessageBody=json.dumps(body))


def _get_collection():
    global _MONGO_CLIENT, _MONGO_DBNAME
    if _MONGO_CLIENT is None:
        secret = json.loads(
            secrets_client.get_secret_value(
                SecretId=MONGO_CREDENTIALS_SECRET_NAME)['SecretString'])
        uri = (f"mongodb+srv://{secret['username']}:{secret['password']}"
               f"@{secret['host']}/?retryWrites=true&w=majority")
        _MONGO_CLIENT = MongoClient(uri)
        _MONGO_DBNAME = secret['dbname']
    return _MONGO_CLIENT[_MONGO_DBNAME][MONGO_COLLECTION_NAME]
