import json
import os


def test_validate_and_persist_valid_row_is_encrypted_and_stored(
        mocker, sqs_client, sns_client, secrets_manager_client):
    # ARRANGE
    from src.validate_and_persist import handler as validate_and_persist
    from src.validate_and_persist import pii
    from tests.mocks.functions.batch.validate_and_persist.valid import (
        EVENT,
        PLAINTEXT_ID,
        PLAINTEXT_NAME,
        ROW,
    )
    from tests.repositories.connection import get_database

    publish_spy = mocker.spy(validate_and_persist.sns_client, 'publish')

    # ACT
    validate_and_persist.handler(EVENT, None)

    # ASSERT
    document = get_database()['accidentReports'].find_one({
        'source_s3_key': 'processed/valid_report.xlsx'
    })
    assert document is not None
    assert document['occurred_at'] == ROW['occurred_at']
    assert document['city'] == ROW['city']
    assert document['road'] == ROW['road']
    assert document['severity'] == ROW['severity']
    assert document['vehicles_involved'] == ROW['vehicles_involved']
    assert document['row_number'] == ROW['row_number']
    assert pii.decrypt(document['involved_person_name']) == PLAINTEXT_NAME
    assert pii.decrypt(document['involved_person_id']) == PLAINTEXT_ID

    publish_spy.assert_called_once()
    call_kwargs = publish_spy.call_args.kwargs
    assert call_kwargs['TopicArn'] == os.environ[
        'ACCIDENT_REPORTS_ETL_TOPIC_ARN']
    assert call_kwargs['MessageAttributes']['action'][
        'StringValue'] == 'created'
    etl_document = json.loads(call_kwargs['Message'])
    assert etl_document['_id'] == str(document['_id'])
    assert etl_document['occurred_at'] == ROW['occurred_at']
    assert etl_document['city'] == ROW['city']
    assert etl_document['road'] == ROW['road']
    assert etl_document['severity'] == ROW['severity']
    assert etl_document['vehicles_involved'] == ROW['vehicles_involved']
    assert etl_document['source_s3_key'] == ROW['source_s3_key']
    assert etl_document['row_number'] == ROW['row_number']
    assert 'involved_person_name' not in etl_document
    assert 'involved_person_id' not in etl_document


def test_validate_and_persist_invalid_row_is_sent_to_dlq(
        sqs_client, sns_client, secrets_manager_client):
    # ARRANGE
    from src.validate_and_persist.handler import handler
    from tests.mocks.functions.batch.validate_and_persist.invalid import (
        EVENT,
        ROW,
    )
    from tests.repositories.connection import get_database

    # ACT
    handler(EVENT, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['ACCIDENT_REPORTS_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    assert len(messages) == 1
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == [f'Invalid "city": {ROW["city"]!r}']

    document = get_database()['accidentReports'].find_one({
        'source_s3_key': 'processed/invalid_row.xlsx'
    })
    assert document is None
