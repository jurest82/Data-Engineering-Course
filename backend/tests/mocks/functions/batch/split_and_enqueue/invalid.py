from pathlib import Path

from tests.mocks.functions.batch.split_and_enqueue.event_builder import (
    build_s3_event,
)

FIXTURE_PATH = (Path(__file__).resolve().parents[4] / 'fixtures' / 'batch' /
                'missing_column.xlsx')

OBJECT_KEY = 'uploads/missing_column.xlsx'
EVENT = build_s3_event(OBJECT_KEY)
