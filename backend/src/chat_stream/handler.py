import json
import os

import boto3

HARNESS_ARN = os.environ['HARNESS_ARN']

AGENTCORE_CLIENT = boto3.client('bedrock-agentcore')

NO_OP_ROUTES = ('$connect', '$disconnect')


def handler(event, context):
    request_context = event['requestContext']
    if request_context['routeKey'] in NO_OP_ROUTES:
        return {
            'statusCode': 200
        }

    body = json.loads(event['body'])
    session_id = body['sessionId']
    response = AGENTCORE_CLIENT.invoke_harness(
        harnessArn=HARNESS_ARN,
        runtimeSessionId=session_id,
        messages=[{
            'role': 'user',
            'content': [{
                'text': body['prompt']
            }]
        }],
    )

    management_client = _management_client(request_context)
    connection_id = request_context['connectionId']
    for chunk in response['stream']:
        message = _translate(chunk)
        if message is not None:
            message['sessionId'] = session_id
            management_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message).encode('utf-8'),
            )

    return {
        'statusCode': 200
    }


def _management_client(request_context):
    domain_name = request_context['domainName']
    stage = request_context['stage']
    endpoint = f'https://{domain_name}/{stage}'
    return boto3.client('apigatewaymanagementapi', endpoint_url=endpoint)


def _translate(chunk):
    if 'contentBlockStart' in chunk:
        if 'toolUse' in chunk['contentBlockStart']['start']:
            return {
                'type': 'tool_start'
            }
        return None
    if 'contentBlockDelta' in chunk:
        delta = chunk['contentBlockDelta']['delta']
        if 'text' in delta:
            return {
                'type': 'delta',
                'text': delta['text']
            }
        return None
    if 'messageStop' in chunk and chunk['messageStop'][
            'stopReason'] != 'tool_use':
        return {
            'type': 'done'
        }
    return None
