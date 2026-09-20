# Data Governance

This document maps every field, table, and responsibility across the traffic monitoring pipeline described in `README.md`.

- [Data dictionary](#data-dictionary)
- [Data catalog](#data-catalog)
- [Lineage](#lineage)
- [RACI matrix](#raci-matrix)
- [Data quality rules already implemented](#data-quality-rules-already-implemented)

## Data dictionary

### Accident reports (MongoDB, `accidentReports`)

| Field | Type | Meaning | Source |
| --- | --- | --- | --- |
| `occurred_at` | ISO 8601 datetime string | Date and time of the accident | Excel columns `fecha` + `hora`, combined |
| `city` | string, one of Bogotá, Medellín, Cali, Barranquilla | City where the accident happened | Excel column `ciudad` |
| `road` | string | Road where the accident happened | Excel column `via` |
| `severity` | string, one of minor, moderate, severe, fatal | Severity of the accident | Excel column `severidad` (leve/moderado/grave/fatal), translated |
| `vehicles_involved` | integer, 1-20 | Number of vehicles involved | Excel column `vehiculos_involucrados` |
| `involved_person_name` | string, encrypted (Fernet) | Name of the person involved. PII | Excel column `nombre_persona_involucrada` |
| `involved_person_id` | string of 6-10 digits, encrypted (Fernet) | National ID of the person involved. PII | Excel column `cedula_persona_involucrada` |
| `source_s3_key` | string | S3 key of the uploaded Excel file this row came from | Added automatically when the file is split into individual rows (see [Lineage](#lineage)) |
| `row_number` | integer | Position of this row within that Excel file | Added automatically when the file is split into individual rows (see [Lineage](#lineage)) |
| `created_at`, `updated_at` | ISO 8601 datetime string | When the document was written to MongoDB | Set automatically when the row is saved |

### Sensor readings (MongoDB, `trafficSensorReadings`)

| Field | Type | Meaning | Source |
| --- | --- | --- | --- |
| `sensor_id` | string | Identifier of the reporting sensor | Derived from the MQTT certificate's thing name, never from the device's own payload |
| `city` | string, one of Bogotá, Medellín, Cali, Barranquilla | City where the sensor sits | Sensor payload |
| `road` | string | Road where the sensor sits | Sensor payload |
| `speed_avg` | number, 0-200 | Average speed measured, km/h | Sensor payload |
| `vehicle_count` | integer, >= 0 | Number of vehicles counted in the interval | Sensor payload |
| `recorded_at` | ISO 8601 datetime string | When the reading was taken | Sensor payload |
| `created_at`, `updated_at` | ISO 8601 datetime string | When the document was written to MongoDB | Set automatically when the reading is saved |

No PII field exists in this collection.

### RDS PostgreSQL (`traffic_monitoring`, schema `public`)

Dimension tables:

| Table | Columns | Notes |
| --- | --- | --- |
| `cities` | `id`, `name` | Fixed list of the 4 cities, already in the database before any data arrives |
| `severities` | `id`, `code` | Fixed list of the 4 severity levels, already in the database before any data arrives |
| `roads` | `id`, `city_id` (FK), `name` | Added automatically the first time that road shows up in a report or reading |
| `sensors` | `id` | Added automatically the first time that sensor reports a reading |

Fact tables:

| Table | Columns | Notes |
| --- | --- | --- |
| `accident_reports` | `id`, `occurred_at`, `city_id` (FK), `road_id` (FK), `severity_id` (FK), `vehicles_involved`, `source_s3_key`, `row_number`, `created_at`, `updated_at` | `id` is the MongoDB `_id` as text. No PII columns. |
| `sensor_readings` | `id`, `sensor_id` (FK), `city_id` (FK), `road_id` (FK), `speed_avg`, `vehicle_count`, `recorded_at`, `created_at`, `updated_at` | `id` is the MongoDB `_id` as text. Partitioned by day on `recorded_at`. |

The ETL pipeline never copies `involved_person_name` or `involved_person_id` to RDS, encrypted or otherwise. The RDS schema has no PII at all.

## Data catalog

| Dataset | Lives in | Fed by | Contains PII |
| --- | --- | --- | --- |
| `accidentReports` | MongoDB Atlas, database `trafficMonitoring` | Excel uploads through the batch API | Yes, encrypted |
| `trafficSensorReadings` | MongoDB Atlas, database `trafficMonitoring` | IoT sensors over MQTT | No |
| `migrationLogs` | MongoDB Atlas, database `trafficMonitoring` | `mongodb-migrations` bookkeeping | No |
| `cities`, `severities`, `roads`, `sensors` | RDS PostgreSQL, database `traffic_monitoring` | The ETL pipeline | No |
| `accident_reports` | RDS PostgreSQL, database `traffic_monitoring` | The ETL pipeline, from `accidentReports` | No, excluded by design |
| `sensor_readings` | RDS PostgreSQL, database `traffic_monitoring` | The ETL pipeline, from `trafficSensorReadings` | No |

Access credentials are also part of the catalog, since they gate who can read what: `MongoCredentials`, `PiiEncryptionKey`, RDS `MasterCredentials`, and RDS `ReadOnlyCredentials`, all in Secrets Manager. The Bedrock agent and the `RunSqlQuery` Lambda only ever hold `ReadOnlyCredentials`.

## Lineage

Accident reports:

1. An auxiliary at a city's Secretaría de Tránsito uploads an Excel file through the batch API.
2. `ValidateAndStore` checks the file and stores it raw in S3.
3. `SplitAndEnqueue` re-validates the file, splits it into one message per row, and moves it to `processed/` or `failed/`.
4. `ValidateAndPersist` re-validates each row, encrypts the PII fields, and writes the document to `accidentReports` in MongoDB.
5. From MongoDB, the document reaches RDS through the ETL Transformer, either right away (the live path) or later through a manual backfill. The Transformer resolves `city`/`severity`/`road` into their RDS ids and writes a row to `accident_reports`, without the PII fields.
6. From RDS, the Bedrock agent reads the data through `RunSqlQuery`, using the read-only role, when a user asks it a question through the chat frontend.

Sensor readings follow the same shape: a sensor at a city's Secretaría de Tránsito publishes over MQTT, IoT Core stamps the trusted sensor id and routes it to SQS, `PersistSensorReading` writes it to `trafficSensorReadings`, the ETL Transformer copies it into `sensor_readings`, and the Bedrock agent reads it from there.

The diagrams in `docs/` draw this visually: `architecture_batch.png` and `architecture_streaming.png` for the two ingestion paths, `architecture_etl.png` for the copy into RDS, `architecture_chat.png` for how the agent reads it back.

## RACI matrix

Roles:

- Secretaría de Tránsito: the city transit authority. Uploads the Excel files and owns the IoT sensors on its roads.
- Data Engineering: builds and operates the pipeline, from the Lambdas to the ETL to the agent.
- Security and Compliance: owns the rules around PII and read-only access.
- Data Consumer: asks the chat agent questions about the data.

| Activity | Secretaría de Tránsito | Data Engineering | Security and Compliance | Data Consumer |
| --- | --- | --- | --- | --- |
| Upload the accident reports Excel file | R, A | I | | |
| Operate and maintain the IoT sensors | R, A | C | | |
| Design and maintain the Lambda validations | I | R, A | C | |
| Encrypt and protect PII fields | I | R | A | |
| Decide which fields are excluded from RDS as PII | | R | A | |
| Design and operate the pipeline (Lambdas, queues, ETL) | I | R, A | | I |
| Approve the agent's read-only access to RDS | | R | A | I |
| Query the data through the chat agent | | A | | R |
| Respond to a security incident or data leak | C | R | A | I |
| Review and approve changes to the data schema | C | R | A | I |

R: Responsible. A: Accountable. C: Consulted. I: Informed.

## Data quality rules already implemented

The rules below live in code, not in this document. This section is a readable summary; the source of truth is `backend/src/common/accident_reports.py`, `backend/src/common/sensor_readings.py`, and `backend/src/validate_and_persist/pii.py`.

Accident reports, checked at three separate points (upload, split, persist), so a row that slips past one still gets caught by the next:

- The file must have all 8 required columns, or it is rejected whole.
- The file cannot exceed 300 rows.
- `fecha` and `hora` must combine into a valid date and time.
- `ciudad` must be Bogotá, Medellín, Cali, or Barranquilla.
- `via` cannot be empty.
- `severidad` must be leve, moderado, grave, or fatal.
- `vehiculos_involucrados` must be a whole number from 1 to 20.
- `nombre_persona_involucrada` cannot be empty.
- `cedula_persona_involucrada` must be a string of 6 to 10 digits.

A row that fails validation at the persist step does not block the rest of the file. It goes into a separate holding queue instead, with the validation errors attached, so someone can fix and resubmit it later.

Sensor readings, checked at the persist step:

- `sensor_id` cannot be empty, and is never taken from the device's own payload. It comes from the MQTT certificate's thing name, which the device cannot forge.
- `city` must be Bogotá, Medellín, Cali, or Barranquilla.
- `road` cannot be empty.
- `speed_avg` must be a number from 0 to 200.
- `vehicle_count` must be a whole number of 0 or more.
- `recorded_at` must be a valid date and time.

PII handling:

- `involved_person_name` and `involved_person_id` are encrypted with Fernet before they reach MongoDB. The key lives in Secrets Manager, separate from the Mongo credentials.
- Neither PII field is ever copied to RDS. The ETL Transformer drops them rather than masking or encrypting them there.
- The Bedrock agent and its `RunSqlQuery` Lambda only connect to RDS with the read-only role, and RDS has no PII to expose in the first place.
- `RunSqlQuery` also rejects any SQL statement that does not start with `SELECT` or `WITH`, regardless of what the model generates.
