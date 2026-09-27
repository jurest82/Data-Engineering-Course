import io
import json
import os

import pytest
from openpyxl import Workbook

CITIES = ['Bogotá', 'Medellín', 'Cali', 'Barranquilla']


def _build_workbook_bytes(row_count):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append([
        'fecha',
        'hora',
        'ciudad',
        'via',
        'severidad',
        'vehiculos_involucrados',
        'nombre_persona_involucrada',
        'cedula_persona_involucrada',
    ])
    for index in range(row_count):
        worksheet.append([
            '2026-08-01',
            '08:30',
            CITIES[index % len(CITIES)],
            'Carrera 7',
            'leve',
            2,
            'Juan Perez',
            str(100000000 + index),
        ])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_split_and_enqueue_valid_file_is_split_and_moved(s3_client, sqs_client):
    # ARRANGE
    from src.split_and_enqueue.handler import handler
    from tests.mocks.functions.batch.split_and_enqueue.valid import (
        EVENT,
        FIXTURE_PATH,
        OBJECT_KEY,
    )

    bucket = os.environ['RAW_REPORTS_BUCKET_NAME']
    s3_client.put_object(Bucket=bucket,
                         Key=OBJECT_KEY,
                         Body=FIXTURE_PATH.read_bytes())

    # ACT
    handler(EVENT, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['ACCIDENT_REPORTS_QUEUE_URL'],
        MaxNumberOfMessages=10)['Messages']
    assert len(messages) == 3
    rows = sorted((json.loads(message['Body']) for message in messages),
                  key=lambda row: row['row_number'])
    assert [row['row_number'] for row in rows] == [1, 2, 3]
    assert [row['city'] for row in rows] == ['Bogotá', 'Medellín', 'Cali']
    assert [row['severity'] for row in rows] == ['minor', 'moderate', 'severe']
    assert all(row['source_s3_key'] == OBJECT_KEY for row in rows)

    keys = [
        obj['Key']
        for obj in s3_client.list_objects_v2(Bucket=bucket)['Contents']
    ]
    assert 'processed/valid_report.xlsx' in keys
    assert OBJECT_KEY not in keys


def test_split_and_enqueue_invalid_file_is_moved_to_failed(
        s3_client, sqs_client):
    # ARRANGE
    from src.common.accident_reports import WorkbookValidationError
    from src.split_and_enqueue.handler import handler
    from tests.mocks.functions.batch.split_and_enqueue.invalid import (
        EVENT,
        FIXTURE_PATH,
        OBJECT_KEY,
    )

    bucket = os.environ['RAW_REPORTS_BUCKET_NAME']
    s3_client.put_object(Bucket=bucket,
                         Key=OBJECT_KEY,
                         Body=FIXTURE_PATH.read_bytes())

    # ACT / ASSERT
    with pytest.raises(WorkbookValidationError):
        handler(EVENT, None)

    messages = sqs_client.receive_message(
        QueueUrl=os.environ['ACCIDENT_REPORTS_QUEUE_URL'],
        MaxNumberOfMessages=10).get('Messages', [])
    assert not messages

    keys = [
        obj['Key']
        for obj in s3_client.list_objects_v2(Bucket=bucket)['Contents']
    ]
    assert 'failed/missing_column.xlsx' in keys
    assert OBJECT_KEY not in keys


def test_split_and_enqueue_flushes_sqs_in_batches_of_ten(
        mocker, s3_client, sqs_client):
    # ARRANGE
    from src.split_and_enqueue import handler as split_and_enqueue

    bucket = os.environ['RAW_REPORTS_BUCKET_NAME']
    object_key = 'uploads/twelve_rows.xlsx'
    s3_client.put_object(Bucket=bucket,
                         Key=object_key,
                         Body=_build_workbook_bytes(12))
    event = {
        'Records': [{
            's3': {
                'bucket': {
                    'name': bucket
                },
                'object': {
                    'key': object_key
                },
            }
        }]
    }
    batch_spy = mocker.spy(split_and_enqueue.sqs_client, 'send_message_batch')

    # ACT
    split_and_enqueue.handler(event, None)

    # ASSERT
    assert batch_spy.call_count == 2
    entry_counts = sorted(
        len(call.kwargs['Entries']) for call in batch_spy.call_args_list)
    assert entry_counts == [2, 10]
