import base64
import json
import os


def test_validate_and_store_valid_file_is_stored(s3_client):
    # ARRANGE
    from src.validate_and_store.handler import handler
    from tests.mocks.functions.batch.validate_and_store.valid import EVENT

    expected_bytes = base64.b64decode(json.loads(EVENT['body'])['file'])

    # ACT
    response = handler(EVENT, None)

    # ASSERT
    assert response['statusCode'] == 202
    body = json.loads(response['body'])
    assert body['rows_accepted'] == 3
    assert body['s3_key'].startswith('uploads/')

    objects = s3_client.list_objects_v2(
        Bucket=os.environ['RAW_REPORTS_BUCKET_NAME'])['Contents']
    assert any(obj['Key'] == body['s3_key'] for obj in objects)

    stored_object = s3_client.get_object(
        Bucket=os.environ['RAW_REPORTS_BUCKET_NAME'], Key=body['s3_key'])
    assert stored_object['Body'].read() == expected_bytes


def test_validate_and_store_invalid_file_is_rejected(s3_client):
    # ARRANGE
    from src.validate_and_store.handler import handler
    from tests.mocks.functions.batch.validate_and_store.invalid import EVENT

    # ACT
    response = handler(EVENT, None)

    # ASSERT
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert 'Missing required column(s)' in body['errors'][0]

    objects = s3_client.list_objects_v2(
        Bucket=os.environ['RAW_REPORTS_BUCKET_NAME']).get('Contents', [])
    assert not objects
