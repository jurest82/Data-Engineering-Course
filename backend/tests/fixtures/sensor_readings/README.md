# Sensor reading fixtures

Example MQTT payloads to publish manually from the AWS IoT Core console (**AWS IoT Core → MQTT test client → Publish to a topic**), to demo the streaming pipeline without needing a real sensor/certificate.

- **Topic**: `sensors/traffic/sensor-001/data` (any `sensors/traffic/<anything>/data` matches the deployed topic rule)
- **Message payload**: paste the contents of one of these files

| File                 | Expected outcome                                                                  |
| -------------------- | --------------------------------------------------------------------------------- |
| `valid_reading.json` | Persisted to the `trafficSensorReadings` collection in MongoDB Atlas              |
| `invalid_city.json`  | Forwarded to the `SensorReadingsDLQ` dead-letter queue (invalid `city`)           |
| `invalid_speed.json` | Forwarded to the `SensorReadingsDLQ` dead-letter queue (`speed_avg` out of range) |

After publishing an invalid one, check `PersistSensorReading`'s CloudWatch Logs or the DLQ's message count to see it land there.
