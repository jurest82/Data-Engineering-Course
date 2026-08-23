#!/bin/bash
# Demo script: provisions a test IoT Core "Thing" + X.509 certificate for a
# traffic sensor, and attaches it to the SensorReadingsPolicy already
# deployed by infrastructure/serverless/iot -- so it can only connect/publish
# on its own topic (sensors/traffic/<sensor-id>/data). Safe to re-run: skips
# certificate creation if one already exists locally for this sensor-id.
#
# Run inside the backend devcontainer (needs the AWS CLI + credentials):
#   cd backend/tests/sensor_readings && ./provision_sensor.sh sensor-001
set -e

SENSOR_ID=$1
if [ -z "$SENSOR_ID" ]; then
  echo "Usage: ./provision_sensor.sh <sensor-id>" >&2
  exit 1
fi

CERTS_DIR="$(dirname "$0")/certs/$SENSOR_ID"
mkdir -p "$CERTS_DIR"

if [ -f "$CERTS_DIR/certificate.pem.crt" ]; then
  echo "Certificate for $SENSOR_ID already exists at $CERTS_DIR, skipping creation."
else
  aws iot create-thing --thing-name "$SENSOR_ID" >/dev/null

  CERT_RESPONSE=$(aws iot create-keys-and-certificate --set-as-active)
  echo "$CERT_RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin)['certificatePem'])" \
    > "$CERTS_DIR/certificate.pem.crt.tmp"
  echo "$CERT_RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin)['keyPair']['PrivateKey'])" \
    > "$CERTS_DIR/private.pem.key.tmp"
  CERT_ARN=$(echo "$CERT_RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin)['certificateArn'])")

  POLICY_NAME=$(aws ssm get-parameter \
    --name "/${DEPLOY_APP}-iot/SensorReadingsPolicyName" \
    --query 'Parameter.Value' \
    --output text)

  aws iot attach-policy --policy-name "$POLICY_NAME" --target "$CERT_ARN"
  aws iot attach-thing-principal --thing-name "$SENSOR_ID" --principal "$CERT_ARN"

  # Only rename to the final names (the ones the idempotency check above and
  # send_sensor_reading.sh look for) once the policy/thing attachments have
  # actually succeeded, so a partial failure never looks like "already done".
  mv "$CERTS_DIR/certificate.pem.crt.tmp" "$CERTS_DIR/certificate.pem.crt"
  mv "$CERTS_DIR/private.pem.key.tmp" "$CERTS_DIR/private.pem.key"

  echo "Provisioned $SENSOR_ID, certificate saved to $CERTS_DIR"
fi

ROOT_CA="$(dirname "$0")/certs/AmazonRootCA1.pem"
if [ ! -f "$ROOT_CA" ]; then
  curl -s "https://www.amazontrust.com/repository/AmazonRootCA1.pem" -o "$ROOT_CA"
  echo "Downloaded Amazon Root CA 1 to $ROOT_CA"
fi
