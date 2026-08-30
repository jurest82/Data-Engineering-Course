# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [x.x.x] - dd/mm/yyyy

### Added

- `infrastructure` subproject:
  - Single-instance, publicly accessible PostgreSQL RDS instance for a future ETL out of MongoDB Atlas (`rds`), using the account's default VPC instead of a dedicated one and auto-generated master credentials in Secrets Manager
- `backend` subproject:
  - Realistic synthetic data seeder for `accidentReports`/`trafficSensorReadings` (`backend/database/seeders/`), guarded to only run against `dev`/`test`
  - Index migrations for both collections, tracked via the `mongodb-migrations` package in an auditable `migrationLogs` collection (`backend/database/migrations/`)
  - A classroom demo (`backend/database/demo_indexes.py`) showing the `explain()` plan before/after an index, with the speedup made explicit

## [0.0.1] - 29/08/2026

### Added

- Dockerized development environment, with a devcontainer setup for both the backend and infrastructure subprojects
- `infrastructure` subproject:
  - Serverless Framework stacks for shared base resources:
    - S3 bucket for raw files (`storage`)
    - SQS queues with dead-letter queues, for the batch pipeline and for streaming sensor readings (`queue`)
    - Secrets Manager secrets for MongoDB Atlas credentials and the PII encryption key (`secrets`)
    - IoT Core policy and topic rule that route sensor readings to the streaming queue, stamping each message with the sensor identity derived from its MQTT topic rather than trusting the payload's own claim (`iot`)
    - SNS topic with an email subscription, CloudWatch alarms on both pipelines' dead-letter queues and on `SplitAndEnqueue` Lambda errors, and an account-wide AWS Budget on cost (`alerts`)
- `backend` subproject:
  - Batch accident reports pipeline:
    - `ValidateAndStore` Lambda: validates an uploaded accident reports Excel file (structure and business rules) and stores it raw in S3, behind a REST API with an API Key
    - `SplitAndEnqueue` Lambda: re-validates the file from S3, splits it into one SQS message per row (`send_message_batch`), and moves it to `processed/` or `failed/` depending on the outcome
    - `ValidateAndPersist` Lambda: re-validates each row from SQS and saves the document to MongoDB Atlas, or forwards invalid rows to the dead-letter queue itself; encrypts PII fields (`involved_person_name`, `involved_person_id`) before saving
  - Streaming sensor readings pipeline:
    - `PersistSensorReading` Lambda: re-validates each sensor reading from SQS (deriving `sensor_id` entirely from the trusted, topic-derived identity, since the reading's own payload never carries one) and saves it to MongoDB Atlas, or forwards invalid readings to the dead-letter queue itself
  - Shared Python Lambda Layers, in their own stack: `Commons` (`openpyxl`), `Mongo` (`pymongo`), `Security` (`cryptography`)
  - Lambda deploy architecture (`x86_64`/`arm64`) resolved automatically to match the machine running the deploy
  - Test fixtures for both pipelines (`backend/tests/fixtures/batch/`, `backend/tests/fixtures/sensor_readings/`)
  - Demo scripts (`backend/tests/batch/`, `backend/tests/sensor_readings/`): send an invalid row/reading straight to a queue to demo the dead-letter queue path, and provision a test IoT Core sensor certificate and publish a reading via MQTT with it
- Architecture diagrams for both pipelines (`docs/`), generated with the Python `diagrams` library
