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
def secrets_manager_client(aws_credentials):  # pylint: disable=unused-argument
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
        connection.create_secret(
            Name=os.environ['PII_ENCRYPTION_KEY_SECRET_NAME'],
            SecretString=json.dumps({
                'key': os.environ['PII_ENCRYPTION_KEY'],
            }),
        )
        yield connection


@pytest.fixture(scope='session')
def s3_client(aws_credentials):  # pylint: disable=unused-argument
    """Mocked S3 client for moto."""
    with mock_aws():
        connection = boto3.client('s3')
        connection.create_bucket(Bucket=os.environ['RAW_REPORTS_BUCKET_NAME'])
        yield connection


@pytest.fixture(scope='session')
def sqs_client(aws_credentials):  # pylint: disable=unused-argument
    """Mocked SQS client for moto."""
    with mock_aws():
        connection = boto3.client('sqs')
        queue = connection.create_queue(QueueName='AccidentReportsQueue')
        dlq = connection.create_queue(QueueName='AccidentReportsDLQ')
        os.environ['ACCIDENT_REPORTS_QUEUE_URL'] = queue['QueueUrl']
        os.environ['ACCIDENT_REPORTS_DLQ_URL'] = dlq['QueueUrl']

        sensor_readings_dlq = connection.create_queue(
            QueueName='SensorReadingsDLQ')
        os.environ['SENSOR_READINGS_DLQ_URL'] = sensor_readings_dlq['QueueUrl']

        # Domain-prefixed: both domains share the same env var names.
        etl_domains = {
            'AccidentReports': 'ACCIDENT_REPORTS',
            'SensorReadings': 'SENSOR_READINGS',
        }
        for domain, prefix in etl_domains.items():
            extractor_queue = connection.create_queue(
                QueueName=f'{domain}ExtractorQueue')
            dispatcher_queue = connection.create_queue(
                QueueName=f'{domain}DispatcherQueue')
            transformer_dlq = connection.create_queue(
                QueueName=f'{domain}TransformerDLQ')
            os.environ[f'{prefix}_EXTRACTOR_QUEUE_URL'] = extractor_queue[
                'QueueUrl']
            os.environ[f'{prefix}_DISPATCHER_QUEUE_URL'] = dispatcher_queue[
                'QueueUrl']
            os.environ[f'{prefix}_TRANSFORMER_DLQ_URL'] = transformer_dlq[
                'QueueUrl']

        yield connection


@pytest.fixture(scope='session')
def sns_client(aws_credentials):  # pylint: disable=unused-argument
    """Mocked SNS client for moto."""
    with mock_aws():
        connection = boto3.client('sns')
        topic = connection.create_topic(Name='AccidentReportsEtlTopic')
        os.environ['ACCIDENT_REPORTS_ETL_TOPIC_ARN'] = topic['TopicArn']

        sensor_readings_topic = connection.create_topic(
            Name='SensorReadingsEtlTopic')
        os.environ['SENSOR_READINGS_ETL_TOPIC_ARN'] = sensor_readings_topic[
            'TopicArn']

        yield connection
