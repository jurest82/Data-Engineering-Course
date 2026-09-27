import os

import psycopg2

_CACHE = {}


def get_connection():
    if 'connection' not in _CACHE:
        _CACHE['connection'] = psycopg2.connect(
            host=os.environ['POSTGRES_LOCAL_HOST'],
            port=os.environ['POSTGRES_LOCAL_PORT'],
            dbname=os.environ['POSTGRES_LOCAL_DBNAME'],
            user=os.environ['POSTGRES_LOCAL_USERNAME'],
            password=os.environ['POSTGRES_LOCAL_PASSWORD'],
        )
    return _CACHE['connection']


def fetch_all(query, params=None):
    connection = get_connection()
    connection.rollback()
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def truncate(*table_names):
    connection = get_connection()
    connection.rollback()
    with connection.cursor() as cursor:
        cursor.execute(f'TRUNCATE {", ".join(table_names)} CASCADE')
    connection.commit()
