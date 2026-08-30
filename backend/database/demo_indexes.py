"""Live classroom demo: shows students how an index changes a query's plan.

For each collection, captures the query plan BEFORE the index exists
(COLLSCAN), applies the real, tracked migration (database/migrations/), then
captures it again AFTER (IXSCAN) -- printing a before/after comparison with
the speedup made explicit, not just raw numbers.

Run database/seeders/seed.sh first: the COLLSCAN-vs-IXSCAN difference needs
enough documents in each collection to actually be visible.

Always reverts every index before starting, so the before/after is real and
repeatable every time this runs (e.g. once per class section), not just the
first time.

Run inside the backend devcontainer:
    cd /app/backend && python3 -m database.demo_indexes
"""
import datetime as dt
import os
import subprocess

from src.common.mongo import get_collection

DEPLOY_APP = os.environ['DEPLOY_APP']
MONGO_CREDENTIALS_SECRET_NAME = f'/{DEPLOY_APP}-secrets/MongoCredentials'
MIGRATE_SH = os.path.join(os.path.dirname(__file__), 'migrations', 'migrate.sh')

# 'timestamp' is each demo's own migration filename prefix -- passed to
# migrate.sh as --to_datetime so applying/reverting one demo's index can
# never touch the other's (mongodb-migrate applies/reverts *everything* up
# to that point otherwise, not just the single migration in question).
DEMOS = [
    {
        'collection':
            'accidentReports',
        'timestamp':
            '20260829000000',
        'index_fields': ('city', 'occurred_at'),
        'query': {
            'city': 'Medellín',
            'occurred_at': {
                '$gte': (dt.datetime.now() - dt.timedelta(days=30)).isoformat(),
            },
        },
        'description':
            'accidentReports: city="Medellín" AND occurred_at >= last 30 days',
    },
    {
        'collection': 'trafficSensorReadings',
        'timestamp': '20260829000001',
        'index_fields': ('sensor_id', 'recorded_at'),
        'query': {
            'sensor_id': 'sensor-001',
        },
        'description': 'trafficSensorReadings: sensor_id="sensor-001"',
    },
]


def _run_migrate(*extra_args):
    subprocess.run([MIGRATE_SH, *extra_args], check=True)


def _upgrade_to(timestamp):
    _run_migrate('--upgrade', timestamp)


def _has_index(collection, index_fields):
    for index in collection.index_information().values():
        if tuple(field for field, _ in index['key']) == index_fields:
            return True
    return False


def _scan_stage(plan_node):
    """MongoDB's winningPlan often wraps the actual IXSCAN/COLLSCAN in an
    outer stage (e.g. FETCH, to pull the full document once the index has
    found it) -- walk down to the stage that actually says which one it is,
    since that's the one students need to see."""
    stage = plan_node['stage']
    if stage in ('IXSCAN', 'COLLSCAN'):
        return stage
    if 'inputStage' in plan_node:
        return _scan_stage(plan_node['inputStage'])
    return stage


def _explain(collection, query):
    plan = collection.find(query).explain()
    stats = plan['executionStats']
    return {
        'stage': _scan_stage(plan['queryPlanner']['winningPlan']),
        'docs_examined': stats['totalDocsExamined'],
        'n_returned': stats['nReturned'],
        'millis': stats['executionTimeMillis'],
    }


def _print_stats(label, stats):
    print(f'  {label}')
    print(f'    Execution plan:       {stats["stage"]}')
    print(f'    Documents examined:   {stats["docs_examined"]}')
    print(f'    Documents returned:   {stats["n_returned"]}')
    print(f'    Execution time:       {stats["millis"]} ms')


def _print_comparison(before, after):
    docs_saved = before['docs_examined'] - after['docs_examined']
    if after['millis'] > 0:
        speedup = f'{before["millis"] / after["millis"]:.1f}x faster'
    else:
        speedup = 'so fast it no longer registers in ms'
    print(f'  >>> {speedup}, {docs_saved} fewer documents examined <<<')


def run_demo(demo):
    collection = get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                demo['collection'])
    print(f'\n=== {demo["description"]} ===')

    if _has_index(collection, demo['index_fields']):
        print('  Index already exists -- no "before" to measure, '
              'this is the current plan:')
        _print_stats('CURRENT (with index)', _explain(collection,
                                                      demo['query']))
        return

    before = _explain(collection, demo['query'])
    _print_stats('BEFORE (no index)', before)

    _upgrade_to(demo['timestamp'])

    after = _explain(collection, demo['query'])
    _print_stats('AFTER (with index)', after)
    _print_comparison(before, after)


def main():
    # Unconditional, not a flag: this script's only job is to show a real
    # before/after, so reverting first (both collections at once --
    # mongodb-migrate has no per-migration downgrade) is just what it does,
    # every time, not an opt-in extra.
    _run_migrate('--downgrade')

    for demo in DEMOS:
        run_demo(demo)


if __name__ == '__main__':
    main()
