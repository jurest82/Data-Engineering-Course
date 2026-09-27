import json

DOCUMENT = {
    '_id': 'sensor-reading-1',
    'sensor_id': 'sensor-001',
    'city': 'Bogotá',
    'road': 'Autopista Norte',
    'speed_avg': 42.5,
    'vehicle_count': 8,
    'recorded_at': '2026-08-29T12:00:00+00:00',
    'created_at': '2026-08-29T12:00:00+00:00',
    'updated_at': '2026-08-29T12:00:00+00:00',
}

EVENT = {
    'Records': [{
        'body': json.dumps(DOCUMENT)
    }]
}
