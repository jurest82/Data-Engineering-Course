import datetime as dt
import decimal
import os
import re

import psycopg2

from src.common import postgres

READONLY_CREDENTIALS_SECRET_NAME = os.environ[
    'READONLY_CREDENTIALS_SECRET_NAME']
STATEMENT_TIMEOUT_MS = os.environ['STATEMENT_TIMEOUT_MS']
MAX_ROWS = int(os.environ['MAX_ROWS'])

ALLOWED_STATEMENT_RE = re.compile(r'^\s*(SELECT|WITH)\b', re.IGNORECASE)
LIMIT_RE = re.compile(r'\blimit\s+(\d+)', re.IGNORECASE)


def handler(event, context):
    sql = event.get('sql')
    if sql is None:
        return {
            'error': 'Missing required "sql" parameter'
        }
    if not ALLOWED_STATEMENT_RE.match(sql):
        return {
            'error': 'Only SELECT/WITH statements are allowed'
        }

    sql = _enforce_limit(sql)

    try:
        columns, rows = _execute(sql)
    except psycopg2.Error as error:
        return {
            'error': f'Query failed: {error}'
        }

    return {
        'columns': columns,
        'rows': _json_safe(rows)
    }


def _enforce_limit(sql):
    match = LIMIT_RE.search(sql)
    if match is None:
        return f'{sql.rstrip().rstrip(";")} LIMIT {MAX_ROWS}'
    if int(match.group(1)) > MAX_ROWS:
        return LIMIT_RE.sub(f'LIMIT {MAX_ROWS}', sql, count=1)
    return sql


def _execute(sql):
    connection = postgres.get_connection(READONLY_CREDENTIALS_SECRET_NAME)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f'SET statement_timeout = {STATEMENT_TIMEOUT_MS}')
            cursor.execute(sql)
            columns = [description.name for description in cursor.description]
            rows = cursor.fetchall()
    except psycopg2.Error:
        connection.rollback()
        raise
    connection.rollback()
    return columns, rows


def _json_safe(rows):
    return [[_json_safe_value(value) for value in row] for row in rows]


def _json_safe_value(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    return value
