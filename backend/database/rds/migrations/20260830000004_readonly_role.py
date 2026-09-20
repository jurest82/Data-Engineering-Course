# pylint: disable=invalid-name
import json
import os

import boto3
from yoyo import step

DEPLOY_APP = os.environ['DEPLOY_APP']
READONLY_CREDENTIALS_SECRET_NAME = f'/{DEPLOY_APP}-rds/ReadOnlyCredentials'

secrets_client = boto3.client('secretsmanager')


def apply_step(conn):
    secret = json.loads(
        secrets_client.get_secret_value(
            SecretId=READONLY_CREDENTIALS_SECRET_NAME)['SecretString'])

    cursor = conn.cursor()
    cursor.execute('CREATE ROLE readonly WITH LOGIN PASSWORD %s',
                   (secret['password'], ))
    cursor.execute('GRANT CONNECT ON DATABASE traffic_monitoring TO readonly')
    cursor.execute('GRANT USAGE ON SCHEMA public TO readonly')
    cursor.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly')
    cursor.execute('''
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT ON TABLES TO readonly
    ''')


def rollback_step(conn):
    cursor = conn.cursor()
    cursor.execute('DROP OWNED BY readonly')
    cursor.execute('DROP ROLE readonly')


steps = [step(apply_step, rollback_step)]
