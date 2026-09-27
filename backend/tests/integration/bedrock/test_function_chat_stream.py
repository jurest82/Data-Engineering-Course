import json
import os

import pytest

from src.chat_stream import handler as chat_stream

STREAM_CHUNKS = [
    {
        'contentBlockStart': {
            'start': {
                'toolUse': {
                    'name': 'run_sql_query'
                }
            }
        }
    },
    {
        'contentBlockStart': {
            'start': {}
        }
    },
    {
        'contentBlockDelta': {
            'delta': {
                'text': 'Hello'
            }
        }
    },
    {
        'contentBlockDelta': {
            'delta': {}
        }
    },
    {
        'messageStop': {
            'stopReason': 'tool_use'
        }
    },
    {
        'messageStop': {
            'stopReason': 'end_turn'
        }
    },
]


def test_chat_stream_management_client_builds_the_right_endpoint():
    # ARRANGE / ACT
    client = chat_stream._management_client({  # pylint: disable=protected-access
        'domainName': 'abc123.execute-api.us-east-1.amazonaws.com',
        'stage': 'dev',
    })

    # ASSERT
    assert client.meta.endpoint_url == (
        'https://abc123.execute-api.us-east-1.amazonaws.com/dev')


def test_chat_stream_connect_and_disconnect_are_no_ops(mocker):
    # ARRANGE
    invoke_spy = mocker.spy(chat_stream.AGENTCORE_CLIENT, 'invoke_harness')

    # ACT / ASSERT
    for route in ('$connect', '$disconnect'):
        response = chat_stream.handler({
            'requestContext': {
                'routeKey': route
            }
        }, None)
        assert response == {
            'statusCode': 200
        }
    invoke_spy.assert_not_called()


def test_chat_stream_send_message_relays_translated_chunks(mocker):
    # ARRANGE
    invoke_spy = mocker.patch.object(chat_stream.AGENTCORE_CLIENT,
                                     'invoke_harness',
                                     return_value={
                                         'stream': STREAM_CHUNKS
                                     })
    mock_management_client = mocker.MagicMock()
    mocker.patch.object(chat_stream,
                        '_management_client',
                        return_value=mock_management_client)

    event = {
        'requestContext': {
            'routeKey': 'sendMessage',
            'connectionId': 'conn-1',
            'domainName': 'example.execute-api.us-east-1.amazonaws.com',
            'stage': 'dev',
        },
        'body': json.dumps({
            'sessionId': 'session-1',
            'prompt': 'hola',
        }),
    }

    # ACT
    response = chat_stream.handler(event, None)

    # ASSERT
    assert response == {
        'statusCode': 200
    }
    invoke_spy.assert_called_once_with(
        harnessArn=os.environ['HARNESS_ARN'],
        runtimeSessionId='session-1',
        messages=[{
            'role': 'user',
            'content': [{
                'text': 'hola'
            }]
        }],
    )

    posted_calls = mock_management_client.post_to_connection.call_args_list
    posted_messages = [json.loads(call.kwargs['Data']) for call in posted_calls]
    assert posted_messages == [
        {
            'type': 'tool_start',
            'sessionId': 'session-1'
        },
        {
            'type': 'delta',
            'text': 'Hello',
            'sessionId': 'session-1'
        },
        {
            'type': 'done',
            'sessionId': 'session-1'
        },
    ]
    assert all(call.kwargs['ConnectionId'] == 'conn-1' for call in posted_calls)


def test_chat_stream_raises_on_malformed_body(mocker):
    # ARRANGE
    invoke_spy = mocker.spy(chat_stream.AGENTCORE_CLIENT, 'invoke_harness')
    event = {
        'requestContext': {
            'routeKey': 'sendMessage',
            'connectionId': 'conn-1',
            'domainName': 'example.execute-api.us-east-1.amazonaws.com',
            'stage': 'dev',
        },
        'body': json.dumps({}),
    }

    # ACT / ASSERT
    with pytest.raises(KeyError):
        chat_stream.handler(event, None)
    invoke_spy.assert_not_called()
