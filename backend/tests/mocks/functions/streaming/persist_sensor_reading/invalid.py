from pathlib import Path

from tests.mocks.functions.streaming.persist_sensor_reading import (
    event_builder, )

FIXTURE_PATH = (Path(__file__).resolve().parents[4] / 'fixtures' /
                'sensor_readings' / 'invalid_city.json')

THING_NAME = 'sensor-001'
READING = event_builder.build_reading(FIXTURE_PATH, THING_NAME)
EVENT = event_builder.build_sqs_event(READING)
