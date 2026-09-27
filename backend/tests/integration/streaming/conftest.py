import os

import pytest


@pytest.fixture(autouse=True)
def streaming_cleanup(sqs_client):
    yield
    sqs_client.purge_queue(QueueUrl=os.environ['SENSOR_READINGS_DLQ_URL'])
