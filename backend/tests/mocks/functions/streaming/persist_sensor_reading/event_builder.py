import json


def build_reading(fixture_path, thing_name):
    reading = json.loads(fixture_path.read_text())
    reading['thing_name'] = thing_name
    return reading


def build_sqs_event(reading):
    return {
        'Records': [{
            'body': json.dumps(reading)
        }]
    }
