import json
import os

import boto3
import psycopg2

from src.common import postgres
from src.common.cities import ALLOWED_CITIES
from src.common.postgres_dimensions import (
    get_city_id,
    upsert_road_id,
    upsert_sensor_id,
)
from src.common.sensor_readings import MAX_SPEED_AVG, MIN_VEHICLE_COUNT
from src.common.validators import is_valid_iso_datetime

sqs_client = boto3.client('sqs')

RDS_CREDENTIALS_SECRET_NAME = os.environ['RDS_CREDENTIALS_SECRET_NAME']
TRANSFORMER_DLQ_URL = os.environ['TRANSFORMER_DLQ_URL']

REQUIRED_FIELDS = (
    '_id',
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
    sensor_id = document['sensor_id']
    if not isinstance(sensor_id, str) or not sensor_id.strip():
        errors.append('"sensor_id" cannot be empty')

    if document['city'] not in ALLOWED_CITIES:
        errors.append(f'Invalid "city": {document["city"]!r}')

    road = document['road']
    if not isinstance(road, str) or not road.strip():
        errors.append('"road" cannot be empty')

    speed_avg = document['speed_avg']
    if (isinstance(speed_avg, bool) or not isinstance(speed_avg,
                                                      (int, float)) or
            not 0 <= speed_avg <= MAX_SPEED_AVG):
        errors.append(f'Invalid "speed_avg": {speed_avg!r}')

    vehicle_count = document['vehicle_count']
    if (not isinstance(vehicle_count, int) or isinstance(vehicle_count, bool) or
            vehicle_count < MIN_VEHICLE_COUNT):
        errors.append(f'Invalid "vehicle_count": {vehicle_count!r}')

    if not is_valid_iso_datetime(document['recorded_at']):
        errors.append(f'Invalid "recorded_at": {document["recorded_at"]!r}')

    return errors


def _upsert(connection, document):
    city_id = get_city_id(connection, document['city'])
    road_id = upsert_road_id(connection, city_id, document['road'])
    sensor_id = upsert_sensor_id(connection, document['sensor_id'])

    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO sensor_readings (
                id, sensor_id, city_id, road_id, speed_avg,
                vehicle_count, recorded_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                sensor_id = EXCLUDED.sensor_id,
                city_id = EXCLUDED.city_id,
                road_id = EXCLUDED.road_id,
                speed_avg = EXCLUDED.speed_avg,
                vehicle_count = EXCLUDED.vehicle_count,
                recorded_at = EXCLUDED.recorded_at,
                updated_at = EXCLUDED.updated_at
            ''', (
                document['_id'],
                sensor_id,
                city_id,
                road_id,
                document['speed_avg'],
                document['vehicle_count'],
                document['recorded_at'],
                document['created_at'],
                document['updated_at'],
            ))


def _send_to_dlq(document, errors):
    body = dict(document)
    body['validation_errors'] = errors
    sqs_client.send_message(QueueUrl=TRANSFORMER_DLQ_URL,
                            MessageBody=json.dumps(body))
