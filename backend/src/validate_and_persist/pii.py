import json
import os

import boto3
from cryptography.fernet import Fernet

secrets_client = boto3.client('secretsmanager')

PII_ENCRYPTION_KEY_SECRET_NAME = os.environ['PII_ENCRYPTION_KEY_SECRET_NAME']

_FERNET = None


def encrypt(value):
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value):
    return _get_fernet().decrypt(value.encode()).decode()


def _get_fernet():
    global _FERNET
    if _FERNET is None:
        secret = json.loads(
            secrets_client.get_secret_value(
                SecretId=PII_ENCRYPTION_KEY_SECRET_NAME)['SecretString'])
        _FERNET = Fernet(secret['key'].encode())
    return _FERNET
