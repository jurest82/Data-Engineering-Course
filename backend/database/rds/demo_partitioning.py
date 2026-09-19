"""Live classroom demo: shows students how partitioning sensor_readings by
recorded_at lets Postgres skip partitions that can't match the query
("partition pruning"), instead of scanning the whole table.

Unlike demo_indexes.py, this doesn't toggle the migration on/off (undoing the
partitioning would mean dropping and recreating the table, losing its data
and needing a full ETL backfill to get it back -- too heavy for a repeatable
in-class demo). Instead it runs the same query twice in the same session,
toggling Postgres' own enable_partition_pruning setting: OFF is the
"before" (every partition considered, as if the table weren't partitioned
at all), ON is the real, default behavior.

Requires the ETL backfill to have already populated sensor_readings (see
"ETL backfill" in backend/README.md) -- the pruning difference needs data
spread across more than one partition to actually be visible.

Run inside the backend devcontainer:
    cd /app/backend && python3 -m database.rds.demo_partitioning
"""
import datetime as dt
import os

from src.common import postgres

DEPLOY_APP = os.environ['DEPLOY_APP']
RDS_CREDENTIALS_SECRET_NAME = f'/{DEPLOY_APP}-rds/MasterCredentials'

QUERY = ('SELECT * FROM sensor_readings '
         'WHERE recorded_at >= %s AND recorded_at < %s')


def _busiest_day(cursor):
    """Picks whichever day actually has the most rows, instead of assuming
    the data reaches all the way up to "today" -- the ETL backfill only ever
    has whatever was last seeded into Mongo (see seed_mongo.py), which can
    be well behind the current date by the time this demo gets run."""
    cursor.execute('''
        SELECT date_trunc('day', recorded_at)::date AS day, count(*)
        FROM sensor_readings
        GROUP BY 1
        ORDER BY count(*) DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            'sensor_readings is empty -- run the ETL backfill first '
            '(see "ETL backfill" in backend/README.md)')
    return row[0]


def _scan_relations(plan_node, relations):
    """Partition pruning shows up as fewer child scans under the Append node
    that combines each partition's own scan -- walk the whole plan tree and
    collect every relation actually scanned, not just the top node."""
    if 'Relation Name' in plan_node:
        relations.add(plan_node['Relation Name'])
    for child in plan_node.get('Plans', []):
        _scan_relations(child, relations)


def _explain(cursor, query_params, enable_pruning):
    cursor.execute(
        f"SET enable_partition_pruning = {'on' if enable_pruning else 'off'}")
    cursor.execute(f'EXPLAIN (ANALYZE, FORMAT JSON) {QUERY}', query_params)
    plan = cursor.fetchone()[0][0]

    relations = set()
    _scan_relations(plan['Plan'], relations)
    return {
        'partitions_scanned': len(relations),
        'millis': plan['Execution Time'],
    }


def _print_stats(label, stats):
    print(f'  {label}')
    print(f'    Partitions scanned:   {stats["partitions_scanned"]}')
    print(f'    Execution time:       {stats["millis"]:.2f} ms')


def _print_comparison(before, after):
    partitions_saved = (before['partitions_scanned'] -
                        after['partitions_scanned'])
    if after['millis'] > 0:
        speedup = f'{before["millis"] / after["millis"]:.1f}x faster'
    else:
        speedup = 'so fast it no longer registers in ms'
    print(f'  >>> {speedup}, {partitions_saved} fewer partitions scanned <<<')


def main():
    connection = postgres.get_connection(RDS_CREDENTIALS_SECRET_NAME)
    with connection.cursor() as cursor:
        day = _busiest_day(cursor)
        range_start = day.isoformat()
        range_end = (day + dt.timedelta(days=1)).isoformat()
        query_params = (range_start, range_end)

        print(f'\n=== sensor_readings: recorded_at in '
              f'[{range_start}, {range_end}) ===')

        before = _explain(cursor, query_params, enable_pruning=False)
        _print_stats('BEFORE (pruning disabled -- every partition considered)',
                     before)

        after = _explain(cursor, query_params, enable_pruning=True)
        _print_stats('AFTER (pruning enabled -- the real, default behavior)',
                     after)

        _print_comparison(before, after)
    connection.rollback()


if __name__ == '__main__':
    main()
