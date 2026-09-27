import base64
import json
from pathlib import Path

FIXTURE_PATH = (Path(__file__).resolve().parents[4] / 'fixtures' / 'batch' /
                'missing_column.xlsx')

EVENT = {
    'body':
        json.dumps({
            'file': base64.b64encode(FIXTURE_PATH.read_bytes()).decode()
        })
}
