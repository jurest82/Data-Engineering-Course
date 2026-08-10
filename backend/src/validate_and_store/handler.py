import base64
import binascii
import io
import json
import os
import uuid

import boto3
from openpyxl import load_workbook

from src.common.accident_reports import (
    WorkbookValidationError,
    validate_workbook,
)

s3_client = boto3.client('s3')

RAW_REPORTS_BUCKET_NAME = os.environ['RAW_REPORTS_BUCKET_NAME']

XLSX_CONTENT_TYPE = ('application/vnd.openxmlformats-officedocument'
                     '.spreadsheetml.sheet')


def handler(event, context):
    try:
        payload = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return _response(400, {
            'message': 'Request body must be valid JSON'
        })

    encoded_file = payload.get('file')
    if not encoded_file:
        return _response(400, {
            'message': '"file" is required'
        })

    try:
        file_bytes = base64.b64decode(encoded_file, validate=True)
    except binascii.Error:
        return _response(400, {
            'message': '"file" is not valid base64'
        })

    try:
        workbook = load_workbook(io.BytesIO(file_bytes),
                                 read_only=True,
                                 data_only=True)
    except Exception:
        return _response(400, {
            'message': 'File is not a valid .xlsx workbook'
        })

    try:
        rows = validate_workbook(workbook.active)
    except WorkbookValidationError as error:
        return _response(400, {
            'message': 'Validation failed',
            'errors': error.errors,
        })

    report_key = f'uploads/{uuid.uuid4()}.xlsx'
    s3_client.put_object(
        Bucket=RAW_REPORTS_BUCKET_NAME,
        Key=report_key,
        Body=file_bytes,
        ContentType=XLSX_CONTENT_TYPE,
    )

    return _response(
        202, {
            'message': 'Accident reports file accepted',
            's3_key': report_key,
            'rows_accepted': len(rows),
        })


def _response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body),
    }
