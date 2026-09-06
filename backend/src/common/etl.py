import json


def publish_to_etl(sns_client, topic_arn, document, inserted_id, fields):
    # Never propagate: that would re-deliver the SQS message and duplicate
    # the Mongo insert.
    try:
        etl_document = {
            field: document[field]
            for field in fields
        }
        etl_document['_id'] = str(inserted_id)
        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(etl_document),
            MessageAttributes={
                'action': {
                    'DataType': 'String',
                    'StringValue': 'created',
                },
            },
        )
    except Exception as error:
        print(f'Failed to publish to the ETL topic: {error}')
