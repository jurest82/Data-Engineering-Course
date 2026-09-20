import json
import os

import boto3
from pymongo import MongoClient

secrets_client = boto3.client('secretsmanager')

_CACHE = {}


def get_collection(secret_name, collection_name):
    if secret_name not in _CACHE:
        secret = _resolve_secret(secret_name)
        uri = _build_uri(secret)
        _CACHE[secret_name] = {
            'client': MongoClient(uri),
            'dbname': secret['dbname'],
        }
    cached = _CACHE[secret_name]
    return cached['client'][cached['dbname']][collection_name]


def _resolve_secret(secret_name):
    # MONGO_LOCAL_HOST bypasses Secrets Manager for the local test Mongo.
    local_host = os.environ.get('MONGO_LOCAL_HOST')
    if local_host:
        return {
            'host': local_host,
            'port': int(os.environ.get('MONGO_LOCAL_PORT', 27017)),
            'dbname': os.environ.get('MONGO_LOCAL_DBNAME', 'trafficMonitoring'),
            'username': os.environ['MONGO_LOCAL_USERNAME'],
            'password': os.environ['MONGO_LOCAL_PASSWORD'],
        }
    return json.loads(
        secrets_client.get_secret_value(SecretId=secret_name)['SecretString'])


def _build_uri(secret):
    # Only the local secret has a `port`; Atlas connects via DNS SRV.
    if 'port' in secret:
        return (f"mongodb://{secret['username']}:{secret['password']}"
                f"@{secret['host']}:{secret['port']}/?authSource=admin")
    return (f"mongodb+srv://{secret['username']}:{secret['password']}"
            f"@{secret['host']}/?retryWrites=true&w=majority")
