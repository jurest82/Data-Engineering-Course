import json

DOCUMENT = {
    '_id': 'accident-report-1',
    'occurred_at': '2026-08-01T08:30:00+00:00',
    'city': 'Bogotá',
    'road': 'Carrera 7',
    'severity': 'minor',
    'vehicles_involved': 2,
    'source_s3_key': 'processed/valid_report.xlsx',
    'row_number': 1,
    'created_at': '2026-08-01T08:30:00+00:00',
    'updated_at': '2026-08-01T08:30:00+00:00',
}

EVENT = {
    'Records': [{
        'body': json.dumps(DOCUMENT)
    }]
}
