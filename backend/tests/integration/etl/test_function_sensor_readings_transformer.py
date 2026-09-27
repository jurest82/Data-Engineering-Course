import json
import os

import psycopg2
import pytest

from tests.mocks.functions.etl.sensor_readings_transformer.valid import (
    DOCUMENT as VALID_DOCUMENT, )

INVALID_FIELD_CASES = [
    pytest.param({
        'sensor_id': '   '
    },
                 '"sensor_id" cannot be empty',
                 id='blank_sensor_id'),
    pytest.param({
        'road': '   '
    }, '"road" cannot be empty', id='blank_road'),
    pytest.param({
        'speed_avg': 500
    },
                 'Invalid "speed_avg": 500',
                 id='invalid_speed_avg'),
    pytest.param({
        'vehicle_count': -1
    },
                 'Invalid "vehicle_count": -1',
                 id='invalid_vehicle_count'),
    pytest.param({
        'recorded_at': 'not-a-date'
    },
                 'Invalid "recorded_at": \'not-a-date\'',
                 id='invalid_recorded_at'),
]

FACT_QUERY = '''
    SELECT sr.recorded_at, se.id, c.name, r.name, sr.speed_avg,
           sr.vehicle_count
    FROM sensor_readings sr
    JOIN sensors se ON se.id = sr.sensor_id
    JOIN cities c ON c.id = sr.city_id
    JOIN roads r ON r.id = sr.road_id
    WHERE sr.id = %s
'''


def test_sensor_readings_transformer_valid_document_is_upserted(sqs_client):  # pylint: disable=unused-argument
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'SENSOR_READINGS_TRANSFORMER_DLQ_URL']
    from src.sensor_readings_transformer import (
        handler as sensor_readings_transformer, )
    from tests.mocks.functions.etl.sensor_readings_transformer.valid import (
        DOCUMENT,
        EVENT,
    )
    from tests.repositories.postgres_connection import fetch_all

    # ACT
    sensor_readings_transformer.handler(EVENT, None)

    # ASSERT
    rows = fetch_all(FACT_QUERY, (DOCUMENT['_id'], ))
    assert len(rows) == 1
    (recorded_at, sensor_id, city, road, speed_avg, vehicle_count) = rows[0]
    assert recorded_at.isoformat() == DOCUMENT['recorded_at']
    assert sensor_id == DOCUMENT['sensor_id']
    assert city == DOCUMENT['city']
    assert road == DOCUMENT['road']
    assert float(speed_avg) == DOCUMENT['speed_avg']
    assert vehicle_count == DOCUMENT['vehicle_count']


def test_sensor_readings_transformer_invalid_document_is_sent_to_dlq(
        sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'SENSOR_READINGS_TRANSFORMER_DLQ_URL']
    from src.sensor_readings_transformer import (
        handler as sensor_readings_transformer, )
    from tests.mocks.functions.etl.sensor_readings_transformer.invalid import (
        DOCUMENT,
        EVENT,
    )
    from tests.repositories.postgres_connection import fetch_all

    # ACT
    sensor_readings_transformer.handler(EVENT, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['SENSOR_READINGS_TRANSFORMER_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    assert len(messages) == 1
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == [
        f'Invalid "city": {DOCUMENT["city"]!r}'
    ]

    rows = fetch_all('SELECT id FROM sensor_readings WHERE id = %s',
                     (DOCUMENT['_id'], ))
    assert not rows


def test_sensor_readings_transformer_rejects_missing_fields(sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'SENSOR_READINGS_TRANSFORMER_DLQ_URL']
    from src.sensor_readings_transformer import (
        handler as sensor_readings_transformer, )

    document = dict(VALID_DOCUMENT)
    del document['vehicle_count']
    event = {
        'Records': [{
            'body': json.dumps(document)
        }]
    }

    # ACT
    sensor_readings_transformer.handler(event, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['SENSOR_READINGS_TRANSFORMER_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == ['Missing field(s): vehicle_count']


@pytest.mark.parametrize('overrides, expected_error', INVALID_FIELD_CASES)
def test_sensor_readings_transformer_rejects_invalid_field(
        sqs_client, overrides, expected_error):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'SENSOR_READINGS_TRANSFORMER_DLQ_URL']
    from src.sensor_readings_transformer import (
        handler as sensor_readings_transformer, )

    document = {
        **VALID_DOCUMENT,
        **overrides
    }
    event = {
        'Records': [{
            'body': json.dumps(document)
        }]
    }

    # ACT
    sensor_readings_transformer.handler(event, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['SENSOR_READINGS_TRANSFORMER_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == [expected_error]


def test_sensor_readings_transformer_rolls_back_on_database_error(
        mocker, sqs_client):  # pylint: disable=unused-argument
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'SENSOR_READINGS_TRANSFORMER_DLQ_URL']
    from src.sensor_readings_transformer import (
        handler as sensor_readings_transformer, )

    mock_connection = mocker.MagicMock()
    mocker.patch.object(sensor_readings_transformer.postgres,
                        'get_connection',
                        return_value=mock_connection)
    mocker.patch.object(sensor_readings_transformer,
                        '_upsert',
                        side_effect=psycopg2.Error('boom'))
    event = {
        'Records': [{
            'body': json.dumps(VALID_DOCUMENT)
        }]
    }

    # ACT / ASSERT
    with pytest.raises(psycopg2.Error):
        sensor_readings_transformer.handler(event, None)
    mock_connection.rollback.assert_called_once()
    mock_connection.commit.assert_not_called()
