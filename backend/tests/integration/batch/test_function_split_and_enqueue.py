import os

import pytest


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

    keys = [
        obj['Key']
        for obj in s3_client.list_objects_v2(Bucket=bucket)['Contents']
    ]
    assert 'failed/missing_column.xlsx' in keys
    assert OBJECT_KEY not in keys
