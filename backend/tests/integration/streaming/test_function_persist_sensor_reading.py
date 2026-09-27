import json
import os


def test_persist_sensor_reading_valid_reading_is_stored(
    mocker,
    sqs_client,  # pylint: disable=unused-argument
    sns_client,  # pylint: disable=unused-argument
    secrets_manager_client):  # pylint: disable=unused-argument
    # ARRANGE
    from src.persist_sensor_reading import handler as persist_sensor_reading
    from tests.mocks.functions.streaming.persist_sensor_reading.valid import (
        EVENT,
        READING,
        THING_NAME,
    )
    from tests.repositories.connection import get_database

    publish_spy = mocker.spy(persist_sensor_reading.sns_client, 'publish')

    # ACT
    persist_sensor_reading.handler(EVENT, None)

    # ASSERT
    document = get_database()['trafficSensorReadings'].find_one({
        'sensor_id': THING_NAME
    })
    assert document is not None
    assert document['city'] == READING['city']
    assert document['road'] == READING['road']
    assert document['speed_avg'] == READING['speed_avg']
    assert document['vehicle_count'] == READING['vehicle_count']
    assert document['recorded_at'] == READING['recorded_at']

    publish_spy.assert_called_once()
    call_kwargs = publish_spy.call_args.kwargs
    assert call_kwargs['TopicArn'] == os.environ[
        'SENSOR_READINGS_ETL_TOPIC_ARN']
    assert call_kwargs['MessageAttributes']['action'][
        'StringValue'] == 'created'
    etl_document = json.loads(call_kwargs['Message'])
    assert etl_document['_id'] == str(document['_id'])
    assert etl_document['sensor_id'] == THING_NAME
    assert etl_document['city'] == READING['city']
    assert etl_document['road'] == READING['road']
    assert etl_document['speed_avg'] == READING['speed_avg']
    assert etl_document['vehicle_count'] == READING['vehicle_count']
    assert etl_document['recorded_at'] == READING['recorded_at']


def test_persist_sensor_reading_invalid_reading_is_sent_to_dlq(
        sqs_client, sns_client, secrets_manager_client):  # pylint: disable=unused-argument
    # ARRANGE
    from src.persist_sensor_reading.handler import handler
    from tests.mocks.functions.streaming.persist_sensor_reading.invalid import (
        EVENT,
        READING,
        THING_NAME,
    )
    from tests.repositories.connection import get_database

    # ACT
    handler(EVENT, None)

    # ASSERT
    messages = sqs_client.receive_message(
        QueueUrl=os.environ['SENSOR_READINGS_DLQ_URL'],
        MaxNumberOfMessages=10)['Messages']
    assert len(messages) == 1
    body = json.loads(messages[0]['Body'])
    assert body['validation_errors'] == [f'Invalid "city": {READING["city"]!r}']

    document = get_database()['trafficSensorReadings'].find_one({
        'sensor_id': THING_NAME
    })
    assert document is None
