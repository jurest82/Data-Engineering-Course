import json
import os

import boto3
import psycopg2

secrets_client = boto3.client('secretsmanager')

_CACHE = {}


def get_connection(secret_name):
    if secret_name not in _CACHE:
        secret = _resolve_secret(secret_name)
        _CACHE[secret_name] = psycopg2.connect(
            host=secret['host'],
            port=secret['port'],
            dbname=secret['dbname'],
            user=secret['username'],
            password=secret['password'],
        )
    return _CACHE[secret_name]


def _resolve_secret(secret_name):
    # POSTGRES_LOCAL_HOST bypasses Secrets Manager for the local test Postgres.
    local_host = os.environ.get('POSTGRES_LOCAL_HOST')
    if local_host:
        return {
            'host':
                local_host,
            'port':
                int(os.environ.get('POSTGRES_LOCAL_PORT', 5432)),
            'dbname':
                os.environ.get('POSTGRES_LOCAL_DBNAME', 'traffic_monitoring'),
            'username':
                os.environ['POSTGRES_LOCAL_USERNAME'],
            'password':
                os.environ['POSTGRES_LOCAL_PASSWORD'],
        }
    return json.loads(
        secrets_client.get_secret_value(SecretId=secret_name)['SecretString'])
