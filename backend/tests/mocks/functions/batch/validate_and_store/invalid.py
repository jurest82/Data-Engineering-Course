from pathlib import Path

FIXTURE_PATH = (Path(__file__).resolve().parents[4] / 'fixtures' / 'batch' /
                'missing_column.json')

EVENT = {
    'body': FIXTURE_PATH.read_text()
}
