import json

from tests.mocks.functions.etl.sensor_readings_transformer.valid import (
    DOCUMENT as VALID_DOCUMENT, )

DOCUMENT = {
    **VALID_DOCUMENT,
    '_id': 'sensor-reading-invalid',
    'city': 'Not A Real City',
}

EVENT = {
    'Records': [{
        'body': json.dumps(DOCUMENT)
    }]
}
