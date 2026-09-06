import json
import math
import os

import boto3

from src.common import mongo

sqs_client = boto3.client('sqs')

MONGO_CREDENTIALS_SECRET_NAME = os.environ['MONGO_CREDENTIALS_SECRET_NAME']
EXTRACTOR_QUEUE_URL = os.environ['EXTRACTOR_QUEUE_URL']
GENERATOR_BATCH_SIZE = int(os.environ.get('GENERATOR_BATCH_SIZE', '500'))

MONGO_COLLECTION_NAME = 'trafficSensorReadings'


def handler(event, context):
    collection = mongo.get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                      MONGO_COLLECTION_NAME)
    total = collection.count_documents({})
    if total == 0:
        print('No documents found, nothing to generate.')
        return

    batches = math.ceil(total / GENERATOR_BATCH_SIZE)
    messages = [{
        'skip': index * GENERATOR_BATCH_SIZE,
        'limit': GENERATOR_BATCH_SIZE,
    } for index in range(batches)]
    _send_in_batches(messages)
    print(f'Queued {len(messages)} batch(es) covering {total} documents.')


def _send_in_batches(messages):
    for start in range(0, len(messages), 10):
        chunk = messages[start:start + 10]
        entries = [{
            'Id': str(start + index),
            'MessageBody': json.dumps(message),
        } for index, message in enumerate(chunk)]
        sqs_client.send_message_batch(QueueUrl=EXTRACTOR_QUEUE_URL,
                                      Entries=entries)
