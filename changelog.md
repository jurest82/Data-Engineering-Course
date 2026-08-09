# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Deferred

- PII handling for accident report fields (`nombre_persona_involucrada`, `cedula_persona_involucrada`): decide whether to mask, tokenize, or field-level encrypt before storing in MongoDB Atlas (Ley 1581 de 2012 compliance).
- CloudWatch alarm on the batch processing dead-letter queue: no alerting is configured yet when messages land there.

## [x.x.x] - dd/10/2026

### Added

- Dockerized development environment, with a devcontainer setup for both the backend and infrastructure subprojects
