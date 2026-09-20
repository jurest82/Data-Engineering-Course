import json
import os

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(scope='session')
def aws_credentials():
    """Mocked AWS credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'mock_value'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'mock_value'
    os.environ['AWS_SECURITY_TOKEN'] = 'mock_value'
    os.environ['AWS_SESSION_TOKEN'] = 'mock_value'


@pytest.fixture(scope='session')
def secrets_manager_client(aws_credentials):
    """Mocked Secrets Manager client for moto."""
    with mock_aws():
        connection = boto3.client('secretsmanager')
        connection.create_secret(
            Name=os.environ['MONGO_CREDENTIALS_SECRET_NAME'],
            SecretString=json.dumps({
                'host': os.environ['MONGO_LOCAL_HOST'],
                'port': int(os.environ['MONGO_LOCAL_PORT']),
                'dbname': os.environ['MONGO_LOCAL_DBNAME'],
                'username': os.environ['MONGO_LOCAL_USERNAME'],
                'password': os.environ['MONGO_LOCAL_PASSWORD'],
            }),
        )
        yield connection
