# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Decide whether to mask, tokenize, or field-level encrypt PII accident report fields (`nombre_persona_involucrada`, `cedula_persona_involucrada`) before storing in MongoDB Atlas (Ley 1581 de 2012 compliance).
- CloudWatch alarm on the batch processing dead-letter queue and on Lambda 2 errors.

## [x.x.x] - dd/10/2026

### Added

- Dockerized development environment, with a devcontainer setup for both the backend and infrastructure subprojects
- `infrastructure` subproject:
  - Serverless Framework stacks for the batch accident reports pipeline:
    - S3 bucket for raw files (`storage`)
    - SQS queue with a dead-letter queue (`queue`)
    - Secrets Manager secret for MongoDB Atlas credentials (`secrets`)
- `backend` subproject:
  - `ValidateAndStore` Lambda: validates an uploaded accident reports Excel file (structure and business rules) and stores it raw in S3, behind a REST API with an API Key
  - `SplitAndEnqueue` Lambda: re-validates the file from S3, splits it into one SQS message per row (`send_message_batch`), and moves it to `processed/` or `failed/` depending on the outcome
  - Shared Python Lambda Layer (`Commons`) for cross-Lambda dependencies (`openpyxl` for now)
  - Test fixtures (`backend/tests/fixtures/`) covering the valid, missing-column, invalid-rows and exceeds-max-rows cases
