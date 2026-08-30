"""Fills accidentReports/trafficSensorReadings with realistic synthetic data.

Run via database/seeders/seed.sh, not directly -- that wrapper refuses to run
outside dev/test, and exports PII_ENCRYPTION_KEY_SECRET_NAME before invoking
this module (src.validate_and_persist.pii reads it at import time).
"""
import argparse
import datetime as dt
import os
import random

from faker import Faker

from src.common.accident_reports import (
    ALLOWED_ENGLISH_SEVERITIES,
    MAX_ROWS,
    MAX_VEHICLES_INVOLVED,
    validate_row,
)
from src.common.cities import ALLOWED_CITIES
from src.common.mongo import get_collection
from src.common.sensor_readings import (
    MAX_SPEED_AVG,
    MIN_VEHICLE_COUNT,
    validate_reading,
)
from src.validate_and_persist import pii

DEPLOY_APP = os.environ['DEPLOY_APP']
MONGO_CREDENTIALS_SECRET_NAME = f'/{DEPLOY_APP}-secrets/MongoCredentials'
ACCIDENT_REPORTS_COLLECTION = 'accidentReports'
SENSOR_READINGS_COLLECTION = 'trafficSensorReadings'
# A single insert_many() with tens of thousands of documents can outlast what
# an Atlas M0 (free tier) connection tolerates and gets dropped mid-request
# (pymongo.errors.AutoReconnect: connection closed). Batching avoids that and
# keeps memory use bounded regardless of how large --accident-reports/
# --sensor-readings is.
INSERT_BATCH_SIZE = 500

ROADS_BY_CITY = {
    'Bogotá': ['Autopista Norte', 'Carrera 7', 'Avenida Boyacá', 'Calle 80'],
    'Medellín': [
        'Avenida El Poblado', 'Autopista Sur', 'Carrera 70', 'Calle 33'
    ],
    'Cali': ['Avenida 6 Norte', 'Carrera 100', 'Autopista Sur', 'Calle 5'],
    'Barranquilla': ['Vía 40', 'Calle 84', 'Carrera 51B', 'Calle 30'],
}

fake = Faker('es_ES')


def _random_recent_datetime(days_back):
    seconds_back = random.randint(0, days_back * 24 * 3600)
    return dt.datetime.now() - dt.timedelta(seconds=seconds_back)


def _utc_now_isoformat():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _build_accident_report(index):
    city = random.choice(list(ALLOWED_CITIES))
    row = {
        'occurred_at': _random_recent_datetime(90).isoformat(),
        'city': city,
        'road': random.choice(ROADS_BY_CITY[city]),
        'severity': random.choice(list(ALLOWED_ENGLISH_SEVERITIES)),
        'vehicles_involved': random.randint(1, MAX_VEHICLES_INVOLVED),
        'involved_person_name': fake.name(),
        'involved_person_id': fake.numerify('#' * random.randint(6, 10)),
    }
    errors = validate_row(row)
    if errors:
        raise ValueError(f'Generated an invalid accident report: {errors}')

    document = dict(row)
    document['involved_person_name'] = pii.encrypt(
        document['involved_person_name'])
    document['involved_person_id'] = pii.encrypt(document['involved_person_id'])
    # SplitAndEnqueue adds these two to every real row, for traceability back
    # to the uploaded Excel file -- simulate batches of up to MAX_ROWS rows
    # so seeded documents carry them too, instead of silently omitting them.
    document['source_s3_key'] = f'processed/seed-batch-{index // MAX_ROWS}.xlsx'
    document['row_number'] = (index % MAX_ROWS) + 1
    now = _utc_now_isoformat()
    document['created_at'] = now
    document['updated_at'] = now
    return document


def _build_sensor_reading(sensor_id, city):
    reading = {
        'sensor_id': sensor_id,
        'city': city,
        'road': random.choice(ROADS_BY_CITY[city]),
        'speed_avg': round(random.uniform(0, MAX_SPEED_AVG), 1),
        'vehicle_count': random.randint(MIN_VEHICLE_COUNT, 40),
        'recorded_at': _random_recent_datetime(14).isoformat(),
    }
    errors = validate_reading(reading)
    if errors:
        raise ValueError(f'Generated an invalid sensor reading: {errors}')

    document = dict(reading)
    now = _utc_now_isoformat()
    document['created_at'] = now
    document['updated_at'] = now
    return document


def _insert_in_batches(collection, documents):
    inserted = 0
    batch = []
    for document in documents:
        batch.append(document)
        if len(batch) >= INSERT_BATCH_SIZE:
            collection.insert_many(batch)
            inserted += len(batch)
            batch = []
    if batch:
        collection.insert_many(batch)
        inserted += len(batch)
    return inserted


def seed_accident_reports(count):
    collection = get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                ACCIDENT_REPORTS_COLLECTION)
    documents = (_build_accident_report(i) for i in range(count))
    return _insert_in_batches(collection, documents)


def seed_sensor_readings(count, sensor_count):
    sensor_ids = [f'sensor-{i:03d}' for i in range(1, sensor_count + 1)]
    collection = get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                SENSOR_READINGS_COLLECTION)
    documents = (_build_sensor_reading(random.choice(sensor_ids),
                                       random.choice(list(ALLOWED_CITIES)))
                 for _ in range(count))
    return _insert_in_batches(collection, documents)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accident-reports', type=int, default=500)
    parser.add_argument('--sensor-readings', type=int, default=3000)
    parser.add_argument('--sensors', type=int, default=5)
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Delete all existing documents in both collections first')
    args = parser.parse_args()

    if args.reset:
        for name in (ACCIDENT_REPORTS_COLLECTION, SENSOR_READINGS_COLLECTION):
            deleted = get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                     name).delete_many({}).deleted_count
            print(f'Deleted {deleted} existing documents from {name}.')

    reports_inserted = seed_accident_reports(args.accident_reports)
    readings_inserted = seed_sensor_readings(args.sensor_readings, args.sensors)

    print(f'Inserted {reports_inserted} documents into '
          f'{ACCIDENT_REPORTS_COLLECTION}.')
    print(f'Inserted {readings_inserted} documents into '
          f'{SENSOR_READINGS_COLLECTION} across {args.sensors} sensors.')


if __name__ == '__main__':
    main()
