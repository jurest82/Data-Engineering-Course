# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [x.x.x] - dd/10/2026

### Added

- Dockerized development environment, with a devcontainer setup for both the backend and infrastructure subprojects
- `infrastructure` subproject:
  - Serverless Framework stacks for the batch accident reports pipeline:
    - S3 bucket for raw files (`storage`)
    - SQS queues with dead-letter queues, for the batch pipeline and for streaming sensor readings (`queue`)
    - Secrets Manager secrets for MongoDB Atlas credentials and the PII encryption key (`secrets`)
    - SNS topic with an email subscription, CloudWatch alarms on the accident reports dead-letter queue and on `SplitAndEnqueue` Lambda errors, and an account-wide AWS Budget on cost (`alerts`)
- `backend` subproject:
  - `ValidateAndStore` Lambda: validates an uploaded accident reports Excel file (structure and business rules) and stores it raw in S3, behind a REST API with an API Key
  - `SplitAndEnqueue` Lambda: re-validates the file from S3, splits it into one SQS message per row (`send_message_batch`), and moves it to `processed/` or `failed/` depending on the outcome
  - `ValidateAndPersist` Lambda: re-validates each row from SQS, encrypts PII fields (`involved_person_name`, `involved_person_id`) and saves the document to MongoDB Atlas, or forwards invalid rows to the dead-letter queue itself
  - Shared Python Lambda Layers: `Commons` (`openpyxl`), `Mongo` (`pymongo`), `Security` (`cryptography`)
  - Lambda deploy architecture (`x86_64`/`arm64`) resolved automatically to match the machine running the deploy
  - Test fixtures (`backend/tests/fixtures/`) covering the valid, missing-column, invalid-rows and exceeds-max-rows cases
