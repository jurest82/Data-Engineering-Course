import json

import boto3
import psycopg2

secrets_client = boto3.client('secretsmanager')

_CACHE = {}


def get_connection(secret_name):
    if secret_name not in _CACHE:
        secret = json.loads(
            secrets_client.get_secret_value(
                SecretId=secret_name)['SecretString'])
        _CACHE[secret_name] = psycopg2.connect(
            host=secret['host'],
            port=secret['port'],
            dbname=secret['dbname'],
            user=secret['username'],
            password=secret['password'],
        )
    return _CACHE[secret_name]
