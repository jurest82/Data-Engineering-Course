# Sensor reading fixtures

Example MQTT payloads for the streaming pipeline. Two ways to publish them, depending on what you want to demo:

1. **AWS IoT Core console** (no certificate needed, authenticates with your IAM credentials): **AWS IoT Core → MQTT test client → Publish to a topic**.
   - **Topic**: `sensors/traffic/sensor-001/data` (any `sensors/traffic/<anything>/data` matches the deployed topic rule)
   - **Message payload**: paste the contents of one of these files
2. **`../../sensor_readings/send_sensor_reading.sh`** (real device certificate, mTLS -- the same authentication path a real sensor would use): `./send_sensor_reading.sh sensor-001 ../fixtures/sensor_readings/invalid_city.json`. Run `provision_sensor.sh <sensor-id>` first. See that script for the negative-test demo (a sensor publishing on _another_ sensor's topic, denied by the Policy).

| File                 | Expected outcome                                                                  |
| -------------------- | --------------------------------------------------------------------------------- |
| `valid_reading.json` | Persisted to the `trafficSensorReadings` collection in MongoDB Atlas              |
| `invalid_city.json`  | Forwarded to the `SensorReadingsDLQ` dead-letter queue (invalid `city`)           |
| `invalid_speed.json` | Forwarded to the `SensorReadingsDLQ` dead-letter queue (`speed_avg` out of range) |

After publishing an invalid one, check `PersistSensorReading`'s CloudWatch Logs or the DLQ's message count to see it land there.
