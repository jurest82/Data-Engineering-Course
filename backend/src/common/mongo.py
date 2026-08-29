import json

import boto3
from pymongo import MongoClient

secrets_client = boto3.client('secretsmanager')

_CACHE = {}


def get_collection(secret_name, collection_name):
    if secret_name not in _CACHE:
        secret = json.loads(
            secrets_client.get_secret_value(
                SecretId=secret_name)['SecretString'])
        uri = (f"mongodb+srv://{secret['username']}:{secret['password']}"
               f"@{secret['host']}/?retryWrites=true&w=majority")
        _CACHE[secret_name] = {
            'client': MongoClient(uri),
            'dbname': secret['dbname'],
        }
    cached = _CACHE[secret_name]
    return cached['client'][cached['dbname']][collection_name]
