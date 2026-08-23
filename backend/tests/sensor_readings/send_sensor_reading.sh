#!/bin/bash
# Demo script: publishes a sensor reading via MQTT using a provisioned
# sensor's real certificate (mTLS) -- the same way a real device would
# connect, unlike `aws iot-data publish`, which authenticates with IAM
# credentials instead of a device certificate.
#
# Run ./provision_sensor.sh <sensor-id> first. Requires mosquitto-clients.
#
# Usage: ./send_sensor_reading.sh <sensor-id> [payload-file] [topic]
#
# Examples:
#   ./send_sensor_reading.sh sensor-001
#   ./send_sensor_reading.sh sensor-001 ../fixtures/sensor_readings/invalid_city.json
#
#   # Negative test: sensor-002's certificate is only authorized for its own
#   # topic, so publishing to sensor-001's topic gets denied by the Policy:
#   ./send_sensor_reading.sh sensor-002 ../fixtures/sensor_readings/valid_reading.json sensors/traffic/sensor-001/data
set -e

SENSOR_ID=$1
if [ -z "$SENSOR_ID" ]; then
  echo "Usage: ./send_sensor_reading.sh <sensor-id> [payload-file] [topic]" >&2
  exit 1
fi

PAYLOAD_FILE=${2:-"$(dirname "$0")/../fixtures/sensor_readings/valid_reading.json"}
TOPIC=${3:-"sensors/traffic/$SENSOR_ID/data"}

CERTS_DIR="$(dirname "$0")/certs/$SENSOR_ID"
if [ ! -f "$CERTS_DIR/certificate.pem.crt" ]; then
  echo "No certificate found for $SENSOR_ID. Run ./provision_sensor.sh $SENSOR_ID first." >&2
  exit 1
fi

ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --query 'endpointAddress' --output text)

# -i must equal the connecting certificate's Thing name: the Policy scopes
# iot:Connect to client/${iot:Connection.Thing.ThingName}, so a mismatched
# (or default random) client ID gets the connection denied right away.
mosquitto_pub \
  --cafile "$(dirname "$0")/certs/AmazonRootCA1.pem" \
  --cert "$CERTS_DIR/certificate.pem.crt" \
  --key "$CERTS_DIR/private.pem.key" \
  -h "$ENDPOINT" -p 8883 \
  -i "$SENSOR_ID" \
  -t "$TOPIC" \
  -f "$PAYLOAD_FILE"

echo "Sent $PAYLOAD_FILE to $TOPIC using $SENSOR_ID's certificate."
echo "Note: this only confirms the client sent it -- MQTT QoS 0 gives no broker ack, so a Policy denial fails silently here. Check the queue/Lambda logs (or a console subscription) to confirm it actually arrived."
