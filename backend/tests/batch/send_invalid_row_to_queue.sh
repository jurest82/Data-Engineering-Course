#!/bin/bash
# Demo script: sends a row with an invalid "severity" directly to the
# accidentReports SQS queue, bypassing ValidateAndStore/SplitAndEnqueue.
# ValidateAndPersist (Lambda 3) re-validates it, fails, and forwards it to the
# dead-letter queue itself -- this is how you can show that path without
# needing an actual malformed file to make it through Lambda 1 and 2.
#
# Run inside the backend devcontainer (needs the AWS CLI + credentials):
#   cd tests/batch && ./send_invalid_row_to_queue.sh
set -e

QUEUE_URL=$(aws ssm get-parameter \
  --name "/${DEPLOY_APP}-queue/AccidentReportsQueueUrl" \
  --query 'Parameter.Value' \
  --output text)

MESSAGE_BODY='{"occurred_at":"2026-08-22T10:00:00","city":"Bogotá","road":"Autopista Norte","severity":"critica","vehicles_involved":2,"involved_person_name":"Prueba DLQ","involved_person_id":"1234567"}'

aws sqs send-message \
  --queue-url "$QUEUE_URL" \
  --message-body "$MESSAGE_BODY"

echo "Message sent. \"severity\": \"critica\" is not a valid value, so ValidateAndPersist should reject it and forward it to the dead-letter queue -- check the DLQ alarm and its messages in the AWS console."
