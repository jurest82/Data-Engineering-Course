import io
import json
import os
from urllib.parse import unquote_plus

import boto3
from openpyxl import load_workbook

from src.common.accident_reports import (
    WorkbookValidationError,
    validate_workbook,
)

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

ACCIDENT_REPORTS_QUEUE_URL = os.environ['ACCIDENT_REPORTS_QUEUE_URL']

PROCESSED_PREFIX = 'processed/'
FAILED_PREFIX = 'failed/'
SQS_BATCH_SIZE = 10


def handler(event, context):
    for record in event['Records']:
        bucket_name = record['s3']['bucket']['name']
        object_key = unquote_plus(record['s3']['object']['key'])
        _process_object(bucket_name, object_key)


def _process_object(bucket_name, object_key):
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    file_bytes = response['Body'].read()

    try:
        workbook = load_workbook(io.BytesIO(file_bytes),
                                 read_only=True,
                                 data_only=True)
        rows = validate_workbook(workbook.active)
    except WorkbookValidationError:
        _move_object(bucket_name, object_key, FAILED_PREFIX)
        raise

    _enqueue_rows(rows, object_key)
    _move_object(bucket_name, object_key, PROCESSED_PREFIX)


def _enqueue_rows(rows, source_s3_key):
    entries = []
    for row_number, row in enumerate(rows, start=1):
        message = dict(row)
        message['source_s3_key'] = source_s3_key
        message['row_number'] = row_number
        entries.append({
            'Id': str(row_number),
            'MessageBody': json.dumps(message),
        })
        if len(entries) == SQS_BATCH_SIZE:
            _send_batch(entries)
            entries = []
    if entries:
        _send_batch(entries)


def _send_batch(entries):
    sqs_client.send_message_batch(QueueUrl=ACCIDENT_REPORTS_QUEUE_URL,
                                  Entries=entries)


def _move_object(bucket_name, object_key, destination_prefix):
    file_name = object_key.rsplit('/', 1)[-1]
    destination_key = f'{destination_prefix}{file_name}'
    s3_client.copy_object(
        Bucket=bucket_name,
        CopySource={
            'Bucket': bucket_name,
            'Key': object_key
        },
        Key=destination_key,
    )
    s3_client.delete_object(Bucket=bucket_name, Key=object_key)
