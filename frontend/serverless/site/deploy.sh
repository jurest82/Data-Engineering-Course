#!/bin/bash
# Builds the static site (injecting the chat WebSocket URL resolved from SSM
# into dist/config.js) and deploys it in one step: serverless deploy (creates/
# updates SiteBucket and the CloudFront distribution), an aws s3 sync of
# dist/ to SiteBucket, and a CloudFront cache invalidation.
#
# Run inside the frontend devcontainer:
#   cd /app/frontend/serverless/site && ./deploy.sh [stage]
set -e

EXEC_PATH=$(dirname "$(readlink -f "$0")")
SRC_PATH="$EXEC_PATH/../../src"
STACK_NAME="${DEPLOY_APP}-frontend-site"
STAGE="${1:-dev}"

WEBSOCKET_URL=$(aws ssm get-parameter \
  --name "/${DEPLOY_APP}-backend-bedrock/ChatWebSocketUrl" \
  --query Parameter.Value --output text)

rm -rf "$EXEC_PATH/dist"
mkdir -p "$EXEC_PATH/dist"
cp "$SRC_PATH/index.html" "$SRC_PATH/style.css" "$SRC_PATH/app.js" "$EXEC_PATH/dist/"
cat >"$EXEC_PATH/dist/config.js" <<EOF
window.CHAT_CONFIG = { websocketUrl: '${WEBSOCKET_URL}' };
EOF

serverless deploy --stage "$STAGE"

BUCKET_NAME=$(aws cloudformation describe-stack-resource \
  --stack-name "$STACK_NAME" \
  --logical-resource-id SiteBucket \
  --query StackResourceDetail.PhysicalResourceId --output text)

aws s3 sync "$EXEC_PATH/dist" "s3://${BUCKET_NAME}" --delete

DISTRIBUTION_ID=$(aws cloudformation describe-stack-resource \
  --stack-name "$STACK_NAME" \
  --logical-resource-id SiteDistribution \
  --query StackResourceDetail.PhysicalResourceId --output text)

aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" \
  --paths '/*'
