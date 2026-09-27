import json

from tests.mocks.functions.etl.accident_reports_transformer.valid import (
    DOCUMENT as VALID_DOCUMENT, )

DOCUMENT = {
    **VALID_DOCUMENT,
    '_id': 'accident-report-invalid',
    'city': 'Not A Real City',
    'source_s3_key': 'processed/invalid_report.xlsx',
}

EVENT = {
    'Records': [{
        'body': json.dumps(DOCUMENT)
    }]
}
