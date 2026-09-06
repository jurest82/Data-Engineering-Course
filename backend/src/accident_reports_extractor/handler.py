import json
import os

import boto3

from src.common import mongo

sqs_client = boto3.client('sqs')

MONGO_CREDENTIALS_SECRET_NAME = os.environ['MONGO_CREDENTIALS_SECRET_NAME']
DISPATCHER_QUEUE_URL = os.environ['DISPATCHER_QUEUE_URL']

MONGO_COLLECTION_NAME = 'accidentReports'


def handler(event, context):
    collection = mongo.get_collection(MONGO_CREDENTIALS_SECRET_NAME,
                                      MONGO_COLLECTION_NAME)
    for record in event['Records']:
        _process_record(collection, record)


def _process_record(collection, record):
    page = json.loads(record['body'])
    documents = collection.find({}).skip(page['skip']).limit(page['limit'])
    _send_in_batches([_serialize(document) for document in documents])


def _serialize(document):
    document['_id'] = str(document['_id'])
    return document


def _send_in_batches(documents):
    for start in range(0, len(documents), 10):
        chunk = documents[start:start + 10]
        entries = [{
            'Id': str(start + index),
            'MessageBody': json.dumps(document),
        } for index, document in enumerate(chunk)]
        sqs_client.send_message_batch(QueueUrl=DISPATCHER_QUEUE_URL,
                                      Entries=entries)
