import json
import os

import boto3
import psycopg2

from src.common import postgres
from src.common.accident_reports import (
    ALLOWED_ENGLISH_SEVERITIES,
    MAX_VEHICLES_INVOLVED,
)
from src.common.cities import ALLOWED_CITIES
from src.common.postgres_dimensions import (
    get_city_id,
    get_severity_id,
    upsert_road_id,
)
from src.common.validators import is_valid_iso_datetime

sqs_client = boto3.client('sqs')

RDS_CREDENTIALS_SECRET_NAME = os.environ['RDS_CREDENTIALS_SECRET_NAME']
TRANSFORMER_DLQ_URL = os.environ['TRANSFORMER_DLQ_URL']

REQUIRED_FIELDS = (
    '_id',
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
    document = json.loads(record['body'])
    errors = _validate(document)
    if errors:
        _send_to_dlq(document, errors)
        return

    connection = postgres.get_connection(RDS_CREDENTIALS_SECRET_NAME)
    try:
        _upsert(connection, document)
        connection.commit()
    except psycopg2.Error:
        connection.rollback()
        raise


def _validate(document):
    missing = [field for field in REQUIRED_FIELDS if field not in document]
    if missing:
        return [f'Missing field(s): {", ".join(missing)}']

    errors = []
    if not is_valid_iso_datetime(document['occurred_at']):
        errors.append(f'Invalid "occurred_at": {document["occurred_at"]!r}')

    if document['city'] not in ALLOWED_CITIES:
        errors.append(f'Invalid "city": {document["city"]!r}')

    road = document['road']
    if not isinstance(road, str) or not road.strip():
        errors.append('"road" cannot be empty')

    if document['severity'] not in ALLOWED_ENGLISH_SEVERITIES:
        errors.append(f'Invalid "severity": {document["severity"]!r}')

    vehicles_involved = document['vehicles_involved']
    if (not isinstance(vehicles_involved, int) or
            isinstance(vehicles_involved, bool) or
            not 1 <= vehicles_involved <= MAX_VEHICLES_INVOLVED):
        errors.append(f'Invalid "vehicles_involved": {vehicles_involved!r}')

    return errors


def _upsert(connection, document):
    city_id = get_city_id(connection, document['city'])
    road_id = upsert_road_id(connection, city_id, document['road'])
    severity_id = get_severity_id(connection, document['severity'])

    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO accident_reports (
                id, occurred_at, city_id, road_id, severity_id,
                vehicles_involved, source_s3_key, row_number,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                occurred_at = EXCLUDED.occurred_at,
                city_id = EXCLUDED.city_id,
                road_id = EXCLUDED.road_id,
                severity_id = EXCLUDED.severity_id,
                vehicles_involved = EXCLUDED.vehicles_involved,
                source_s3_key = EXCLUDED.source_s3_key,
                row_number = EXCLUDED.row_number,
                updated_at = EXCLUDED.updated_at
            ''', (
                document['_id'],
                document['occurred_at'],
                city_id,
                road_id,
                severity_id,
                document['vehicles_involved'],
                document['source_s3_key'],
                document['row_number'],
                document['created_at'],
                document['updated_at'],
            ))


def _send_to_dlq(document, errors):
    body = dict(document)
    body['validation_errors'] = errors
    sqs_client.send_message(QueueUrl=TRANSFORMER_DLQ_URL,
                            MessageBody=json.dumps(body))
