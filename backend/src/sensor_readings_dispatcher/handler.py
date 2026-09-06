import os

import boto3

sns_client = boto3.client('sns')

ETL_TOPIC_ARN = os.environ['ETL_TOPIC_ARN']


def handler(event, context):
    for record in event['Records']:
        sns_client.publish(
            TopicArn=ETL_TOPIC_ARN,
            Message=record['body'],
            MessageAttributes={
                'action': {
                    'DataType': 'String',
                    'StringValue': 'generated',
                },
            },
        )
