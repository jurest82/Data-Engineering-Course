import json
import os

import pytest


def test_accident_reports_dispatcher_publishes_generated_action(
        mocker, sns_client):  # pylint: disable=unused-argument
    # ARRANGE
    os.environ['ETL_TOPIC_ARN'] = os.environ['ACCIDENT_REPORTS_ETL_TOPIC_ARN']
    from src.accident_reports_dispatcher import (
        handler as accident_reports_dispatcher, )

    body = json.dumps({
        '_id': 'accident-report-1',
        'city': 'Bogotá'
    })
    event = {
        'Records': [{
            'body': body
        }]
    }
    publish_spy = mocker.spy(accident_reports_dispatcher.sns_client, 'publish')

    # ACT
    accident_reports_dispatcher.handler(event, None)

    # ASSERT
    publish_spy.assert_called_once()
    call_kwargs = publish_spy.call_args.kwargs
    assert call_kwargs['TopicArn'] == os.environ[
        'ACCIDENT_REPORTS_ETL_TOPIC_ARN']
    assert call_kwargs['Message'] == body
    assert call_kwargs['MessageAttributes']['action'][
        'StringValue'] == 'generated'


def test_accident_reports_dispatcher_raises_on_malformed_record(
        mocker, sns_client):  # pylint: disable=unused-argument
    # ARRANGE
    os.environ['ETL_TOPIC_ARN'] = os.environ['ACCIDENT_REPORTS_ETL_TOPIC_ARN']
    from src.accident_reports_dispatcher import (
        handler as accident_reports_dispatcher, )

    event = {
        'Records': [{}]
    }
    publish_spy = mocker.spy(accident_reports_dispatcher.sns_client, 'publish')

    # ACT / ASSERT
    with pytest.raises(KeyError):
        accident_reports_dispatcher.handler(event, None)
    publish_spy.assert_not_called()
