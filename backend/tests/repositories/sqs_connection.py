def drain_queue(sqs_client, queue_url):
    messages = []
    while True:
        response = sqs_client.receive_message(QueueUrl=queue_url,
                                              MaxNumberOfMessages=10)
        if 'Messages' not in response:
            return messages
        messages.extend(response['Messages'])
