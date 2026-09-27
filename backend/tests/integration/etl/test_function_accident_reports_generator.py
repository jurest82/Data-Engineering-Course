import json
import os

from tests.repositories.sqs_connection import drain_queue


def test_accident_reports_generator_with_no_documents_enqueues_nothing(
        sqs_client):
    # ARRANGE
    os.environ['EXTRACTOR_QUEUE_URL'] = os.environ[
        'ACCIDENT_REPORTS_EXTRACTOR_QUEUE_URL']
    from src.accident_reports_generator import (
        handler as accident_reports_generator, )

    # ACT
    accident_reports_generator.handler({}, None)

    # ASSERT
    messages = drain_queue(sqs_client,
                           os.environ['ACCIDENT_REPORTS_EXTRACTOR_QUEUE_URL'])
    assert not messages


def test_accident_reports_generator_pages_documents_across_sqs_batches(
        sqs_client):
    # ARRANGE
    os.environ['EXTRACTOR_QUEUE_URL'] = os.environ[
        'ACCIDENT_REPORTS_EXTRACTOR_QUEUE_URL']
    from src.accident_reports_generator import (
        handler as accident_reports_generator, )
    from src.common import mongo

    collection = mongo.get_collection(
        os.environ['MONGO_CREDENTIALS_SECRET_NAME'], 'accidentReports')
    collection.insert_many([{
        'seed_index': index
    } for index in range(55)])

    # ACT
    accident_reports_generator.handler({}, None)

    # ASSERT
    messages = drain_queue(sqs_client,
                           os.environ['ACCIDENT_REPORTS_EXTRACTOR_QUEUE_URL'])
    pages = sorted((json.loads(message['Body']) for message in messages),
                   key=lambda page: page['skip'])
    assert len(pages) == 11
    assert pages[0] == {
        'skip': 0,
        'limit': 5
    }
    assert pages[-1] == {
        'skip': 50,
        'limit': 5
    }
