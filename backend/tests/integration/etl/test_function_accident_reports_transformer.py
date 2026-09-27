import json
import os

import psycopg2
import pytest

from tests.mocks.functions.etl.accident_reports_transformer.valid import (
    DOCUMENT as VALID_DOCUMENT,
)

INVALID_FIELD_CASES = [
    pytest.param({
        'occurred_at': 'not-a-date'
    },
                 'Invalid "occurred_at": \'not-a-date\'',
                 id='invalid_occurred_at'),
    pytest.param({
        'road': '   '
    }, '"road" cannot be empty', id='blank_road'),
    pytest.param({
        'severity': 'not-a-severity'
    },
                 'Invalid "severity": \'not-a-severity\'',
                 id='invalid_severity'),
    pytest.param({
        'vehicles_involved': 0
    },
                 'Invalid "vehicles_involved": 0',
                 id='invalid_vehicles_involved'),
]

FACT_QUERY = '''
    SELECT ar.occurred_at, c.name, r.name, s.code, ar.vehicles_involved,
           ar.source_s3_key, ar.row_number
    FROM accident_reports ar
    JOIN cities c ON c.id = ar.city_id
    JOIN roads r ON r.id = ar.road_id
    JOIN severities s ON s.id = ar.severity_id
    WHERE ar.id = %s
'''


def test_accident_reports_transformer_valid_document_is_upserted(sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL']
    from src.accident_reports_transformer import (
        handler as accident_reports_transformer,
    )
    from tests.mocks.functions.etl.accident_reports_transformer.valid import (
        DOCUMENT,
        EVENT,
    )
    from tests.repositories.postgres_connection import fetch_all

    # ACT
    accident_reports_transformer.handler(EVENT, None)

    # ASSERT
    rows = fetch_all(FACT_QUERY, (DOCUMENT['_id'], ))
    assert len(rows) == 1
    (occurred_at, city, road, severity, vehicles_involved, source_s3_key,
     row_number) = rows[0]
    assert occurred_at.isoformat() == DOCUMENT['occurred_at']
    assert city == DOCUMENT['city']
    assert road == DOCUMENT['road']
    assert severity == DOCUMENT['severity']
    assert vehicles_involved == DOCUMENT['vehicles_involved']
    assert source_s3_key == DOCUMENT['source_s3_key']
    assert row_number == DOCUMENT['row_number']


def test_accident_reports_transformer_reprocessing_updates_the_row(sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL']
    from src.accident_reports_transformer import (
        handler as accident_reports_transformer,
    )
    from tests.mocks.functions.etl.accident_reports_transformer.valid import (
        DOCUMENT,
    )
    from tests.repositories.postgres_connection import fetch_all

    updated_document = dict(DOCUMENT)
    updated_document['vehicles_involved'] = 5

    # ACT
    accident_reports_transformer.handler(
        {
            'Records': [{
                'body': json.dumps(DOCUMENT)
            }]
        }, None)
    accident_reports_transformer.handler(
        {
            'Records': [{
                'body': json.dumps(updated_document)
            }]
        }, None)

    # ASSERT
    rows = fetch_all(
        'SELECT vehicles_involved FROM accident_reports WHERE id = %s',
        (DOCUMENT['_id'], ))
    assert len(rows) == 1
    assert rows[0][0] == 5


def test_accident_reports_transformer_invalid_document_is_sent_to_dlq(
        sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL']
    from src.accident_reports_transformer import (
        handler as accident_reports_transformer,
    )
    from tests.mocks.functions.etl.accident_reports_transformer.invalid import (
        DOCUMENT,
        EVENT,
    )
    from tests.repositories.postgres_connection import fetch_all

    # ACT
    accident_reports_transformer.handler(EVENT, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    assert len(messages) == 1
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == [
        f'Invalid "city": {DOCUMENT["city"]!r}'
    ]

    rows = fetch_all('SELECT id FROM accident_reports WHERE id = %s',
                     (DOCUMENT['_id'], ))
    assert not rows


def test_accident_reports_transformer_rejects_missing_fields(sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL']
    from src.accident_reports_transformer import (
        handler as accident_reports_transformer,
    )

    document = dict(VALID_DOCUMENT)
    del document['row_number']
    event = {
        'Records': [{
            'body': json.dumps(document)
        }]
    }

    # ACT
    accident_reports_transformer.handler(event, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == ['Missing field(s): row_number']


@pytest.mark.parametrize('overrides, expected_error', INVALID_FIELD_CASES)
def test_accident_reports_transformer_rejects_invalid_field(
        sqs_client, overrides, expected_error):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL']
    from src.accident_reports_transformer import (
        handler as accident_reports_transformer,
    )

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
    accident_reports_transformer.handler(event, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == [expected_error]


def test_accident_reports_transformer_rolls_back_on_database_error(
        mocker, sqs_client):
    # ARRANGE
    os.environ['TRANSFORMER_DLQ_URL'] = os.environ[
        'ACCIDENT_REPORTS_TRANSFORMER_DLQ_URL']
    from src.accident_reports_transformer import (
        handler as accident_reports_transformer,
    )

    mock_connection = mocker.MagicMock()
    mocker.patch.object(accident_reports_transformer.postgres,
                        'get_connection',
                        return_value=mock_connection)
    mocker.patch.object(accident_reports_transformer,
                        '_upsert',
                        side_effect=psycopg2.Error('boom'))
    event = {
        'Records': [{
            'body': json.dumps(VALID_DOCUMENT)
        }]
    }

    # ACT / ASSERT
    with pytest.raises(psycopg2.Error):
        accident_reports_transformer.handler(event, None)
    mock_connection.rollback.assert_called_once()
    mock_connection.commit.assert_not_called()
