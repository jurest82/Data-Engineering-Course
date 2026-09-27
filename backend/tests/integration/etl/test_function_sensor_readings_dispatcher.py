import json
import os

import pytest


def test_sensor_readings_dispatcher_publishes_generated_action(
        mocker, sns_client):  # pylint: disable=unused-argument
    # ARRANGE
    os.environ['ETL_TOPIC_ARN'] = os.environ['SENSOR_READINGS_ETL_TOPIC_ARN']
    from src.sensor_readings_dispatcher import (
        handler as sensor_readings_dispatcher, )

    body = json.dumps({
        '_id': 'sensor-reading-1',
        'sensor_id': 'sensor-001'
    })
    event = {
        'Records': [{
            'body': body
        }]
    }
    publish_spy = mocker.spy(sensor_readings_dispatcher.sns_client, 'publish')

    # ACT
    sensor_readings_dispatcher.handler(event, None)

    # ASSERT
    publish_spy.assert_called_once()
    call_kwargs = publish_spy.call_args.kwargs
    assert call_kwargs['TopicArn'] == os.environ[
        'SENSOR_READINGS_ETL_TOPIC_ARN']
    assert call_kwargs['Message'] == body
    assert call_kwargs['MessageAttributes']['action'][
        'StringValue'] == 'generated'


def test_sensor_readings_dispatcher_raises_on_malformed_record(
        mocker, sns_client):  # pylint: disable=unused-argument
    # ARRANGE
    os.environ['ETL_TOPIC_ARN'] = os.environ['SENSOR_READINGS_ETL_TOPIC_ARN']
    from src.sensor_readings_dispatcher import (
        handler as sensor_readings_dispatcher, )

    event = {
        'Records': [{}]
    }
    publish_spy = mocker.spy(sensor_readings_dispatcher.sns_client, 'publish')

    # ACT / ASSERT
    with pytest.raises(KeyError):
        sensor_readings_dispatcher.handler(event, None)
    publish_spy.assert_not_called()
