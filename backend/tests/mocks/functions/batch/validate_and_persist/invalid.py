import json

ROW = {
    'occurred_at': '2026-08-01T08:30:00',
    'city': 'Not A Real City',
    'road': 'Carrera 7',
    'severity': 'minor',
    'vehicles_involved': 2,
    'involved_person_name': 'Juan Perez',
    'involved_person_id': '123456789',
    'source_s3_key': 'processed/invalid_row.xlsx',
    'row_number': 1,
}

EVENT = {
    'Records': [{
        'body': json.dumps(ROW)
    }]
}
