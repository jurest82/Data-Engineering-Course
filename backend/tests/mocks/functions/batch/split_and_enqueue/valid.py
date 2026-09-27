from pathlib import Path

from tests.mocks.functions.batch.split_and_enqueue.event_builder import (
    build_s3_event, )

FIXTURE_PATH = (Path(__file__).resolve().parents[4] / 'fixtures' / 'batch' /
                'valid_report.xlsx')

OBJECT_KEY = 'uploads/valid_report.xlsx'
EVENT = build_s3_event(OBJECT_KEY)
