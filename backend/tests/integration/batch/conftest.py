import os

import pytest


@pytest.fixture(autouse=True)
def batch_cleanup(s3_client, sqs_client):
    yield
    bucket = os.environ['RAW_REPORTS_BUCKET_NAME']
    objects = s3_client.list_objects_v2(Bucket=bucket).get('Contents', [])
    if objects:
        s3_client.delete_objects(
            Bucket=bucket,
            Delete={
                'Objects': [{
                    'Key': obj['Key']
                } for obj in objects]
            },
        )
    sqs_client.purge_queue(QueueUrl=os.environ['ACCIDENT_REPORTS_QUEUE_URL'])
    sqs_client.purge_queue(QueueUrl=os.environ['ACCIDENT_REPORTS_DLQ_URL'])
