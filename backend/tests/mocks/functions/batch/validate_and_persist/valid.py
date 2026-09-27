import json

PLAINTEXT_NAME = 'Juan Perez'
PLAINTEXT_ID = '123456789'

ROW = {
    'occurred_at': '2026-08-01T08:30:00',
    'city': 'Bogotá',
    'road': 'Carrera 7',
    'severity': 'minor',
    'vehicles_involved': 2,
    'involved_person_name': PLAINTEXT_NAME,
    'involved_person_id': PLAINTEXT_ID,
    'source_s3_key': 'processed/valid_report.xlsx',
    'row_number': 1,
}

EVENT = {
    'Records': [{
        'body': json.dumps(ROW)
    }]
}
