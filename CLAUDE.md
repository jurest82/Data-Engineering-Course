# CLAUDE.md: Data Engineering Course

## What this project is

Batch data pipeline that ingests traffic accident reports, uploaded as an Excel file, for the traffic monitoring service described in `README.md`. This document covers the **batch** flow and the traffic sensor **streaming** flow (both complete, see their own sections).

## How to work in this repository

Nothing from this project is installed directly on the host. All work on `backend` and `infrastructure` (installing dependencies, running the `aws` CLI, the `serverless` CLI, formatting/linting Python, deploying) happens by spinning up that subproject's Docker container (`docker compose`, using that subproject's `.docker/docker-compose.yml`) and running it there, replicating what its `entrypoint.sh` does (git configuration, `npm install`, AWS credentials from `.envs/`).

**Claude never runs deploys, `git push`, or other destructive/state-changing commands.** Give the command (or a read-only diagnosis, e.g. `serverless print`/`package`) and let Juan Pablo run it himself.

## Monorepo structure

- **Root**: devcontainer for monorepo-level work (e.g. generating the architecture diagrams). `.docker/Dockerfile` is multi-stage: `img-base` (Python 3.13 + Node 24 + common tools, includes `~/.cfnlintrc` so `cfn-lint` ignores the W3005 false positive that Serverless Framework adds) → `img-backend` (adds `boto3`, only so the local linter/autocomplete resolves the imports; the Lambda runtime already includes it, it's never packaged) / `img-infrastructure` (no additional differences for now) / `img-root` (adds `graphviz` + the Python `diagrams` library, used to generate the architecture diagrams in `docs/` — one per pipeline, see `docs/architecture.py` — not specific to `backend` or `infrastructure`, that's why it lives in the root image).
- **`backend/`**: contains **several Serverless Framework stacks, each in its own folder under `backend/serverless/<stack>/`** (same pattern as `infrastructure/serverless/<stack>/`), not a single stack for the whole backend:
  - `backend/serverless/layers` (`service: backend-layers`): only the shared Lambda Layers, no functions of its own. **Must be deployed first**, since the other `backend` stacks consume its ARNs via SSM.
  - `backend/serverless/batch` (`service: backend-batch`): API Gateway + the batch flow's 3 Lambdas + their IAM roles.
  - Lambda code in `backend/src/<function_name>/`, in **Python**, formatted with `yapf` + `isort` (see `pyproject.toml`); logic shared between Lambdas in `backend/src/common/`. Since each `serverless.yml` lives two levels below `backend/` (`backend/serverless/<stack>/`), each function's `package.patterns` references its code with `../../src/...`.
  - **Python dependencies go through Lambda Layers, not through a `requirements.txt` packaged in each function.** Each layer lives in `backend/src/layers/<name>/` (with its own `requirements.txt` and a `.gitignore` that ignores the generated `python/` folder) and is defined in `backend/serverless/layers/layers.yml` with `path: ../../src/layers/<name>` + `package.patterns: ['!./**', 'python/**']`. Since the layers live in a separate stack, functions in the other `backend` stacks reference them by ARN via SSM (`layers: [${ssm:/${env:DEPLOY_APP}-backend-layers/<Name>LayerArn}]`), not with a direct `!Ref`. `backend`'s `entrypoint.sh` installs those dependencies into `src/layers/<name>/python/` and generates a `.pth` file in the container so they also work for local testing.
  - **Why not `module:`**: the Python-requirements integration's `module` option (for a per-function `requirements.txt`) changes the zip's effective root to the function's folder, which clashes with `package.patterns` (which keeps resolving paths relative to where `serverless.yml` lives) and with having shared code (`common/`) outside that folder; with that combination the packaging ends up inconsistent and includes no files at all. Lambda Layers avoid the problem entirely (they have their own `path:` mechanism for the root).
  - **Current layers**: `Commons` (`openpyxl`), `Mongo` (`pymongo`), `Security` (`cryptography`). Each Lambda only references the layers it actually needs (e.g. Lambda 1/2 don't load `Mongo` or `Security`).
  - **Secrets referenced by name, not by ARN**: `custom.secretsManager.<name>` builds the secret's name directly (e.g. `/${env:DEPLOY_APP}-secrets/MongoCredentials`, matching how `infrastructure` names it), without looking up the ARN via SSM. IAM does need an ARN, though, so it's built with a wildcard: `arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:<name>-*` (the `-*` covers the random suffix Secrets Manager adds).
  - **Deploy architecture (`x86_64`/`arm64`) is resolved dynamically**, not by hand: `provider.architecture: ${file(../architecture.js):get}` (a single `architecture.js` shared in `backend/serverless/`, referenced by all 3 stacks), a script that returns Node's `process.arch`. Needed because `pymongo`/`cryptography` ship compiled extensions, which must match the architecture of whoever deploys (relevant because students may be on Apple Silicon Macs or Intel/Windows x86).
  - **Test cases**: `backend/tests/fixtures/batch/` has example Excel files (`valid_report.xlsx`, `missing_column.xlsx`, `invalid_rows.xlsx`, `exceeds_max_rows.xlsx`) and `generate_base64.sh`, which generates a `.json` for each `.xlsx` with the body ready to paste into Postman (`{"file": "<base64>"}`). `backend/tests/fixtures/sensor_readings/` has example MQTT payloads to paste into the IoT Core console's MQTT test client (see its own `README.md`).
- **`infrastructure/`**: shared base resources (Serverless Framework): S3, SQS+DLQ, Secrets Manager, and CloudWatch alarms. Doesn't deploy the Lambdas' IAM roles, that's `backend`'s responsibility. Each resource lives in its own sub-stack (`serverless/storage`, `serverless/queue`, `serverless/secrets`, `serverless/alerts`), deployed independently. `serverless/queue` is deliberately general-purpose, not exclusive to batch: it hosts both `AccidentReports`/its DLQ (batch) and `SensorReadings`/its DLQ (streaming), instead of having a separate queue sub-stack per flow. All of them are independent from each other **except `alerts`**, which must be deployed **after** `backend/serverless/batch` (its alarms reference, via SSM, the name of the `SplitAndEnqueue` Lambda that stack exports) — it's the only reversal of the usual infra-before-backend order.
- **`docs/`**: architecture diagrams, one per pipeline (`architecture_batch.png`, `architecture_streaming.png`), generated with the Python `diagrams` library from `docs/architecture.py` (run it with `python3 architecture.py` inside the root devcontainer, which brings `graphviz` via `img-root`). Deliberately two separate diagrams rather than one: a single diagram would have to draw both pipelines' cross-cutting edges toward Mongo/Secrets Manager and toward the shared alarms, and those edges force long curves in Graphviz's auto-layout; split apart, each pipeline is a straight chain.
- **`frontend/`** and **`etl/`**: don't exist yet, not part of the current scope (see "Open items"); they're no longer mentioned in `README.md` as if they were part of the monorepo. Until there's a frontend, the batch flow is tested directly against the API (e.g. with Postman).
- Each subproject (`backend`, `infrastructure`) has its own devcontainer, `docker-compose.yml`, `entrypoint.sh`, `.envs/config.env` (with `DEVELOPER`, used so deployed resource names don't collide between developers) and `ws.code-workspace` (a multi-root workspace that also exposes the other subproject's `.envs` and the root's shared ones).

## Infrastructure as code

Serverless Framework, CLI only, no Serverless Dashboard: no `org:`/`app:` keys are set at the top of any `serverless.yml`. `SERVERLESS_ACCESS_KEY` (in `.envs/sls.env`) is only for CLI licensing.

- `@serverless/safeguards-plugin` plugin: rules defined **locally** in each `serverless.yml`'s `custom.safeguards` section (e.g. `allowed-regions`, `allowed-function-names`, `no-wild-iam-role-statements`, `allowed-stages`), not remote Dashboard rules.
- `serverless-deployment-bucket` plugin: its own deployment bucket per stack, with naming that includes `DEVELOPER` in `dev` to avoid collisions between developers.
- Linting of the generated CloudFormation templates: `cfn-lint` + `cfn-lint-serverless`.

## Batch flow architecture

Client sends a `POST` to API Gateway with the accident Excel file encoded in **base64**, max **300 rows** per file.

**Status: all 3 steps (Lambda 1, 2 and 3) are built, deployed and tested.**

1. **Lambda 1** (`ValidateAndStore`, invoked by API Gateway, synchronous) — ✅ built: validates the Excel's structure **and** the business rules; if any row is invalid, rejects the whole file (saves nothing, responds 400 with the detail). If everything is valid, saves the raw file to S3 and responds quickly, without waiting for the rest of the processing (avoids API Gateway's 29s limit). Excel schema (columns in Spanish, mapped to English for the code/Mongo):

   | Excel column | Field in code/Mongo | Validation |
   |---|---|---|
   | `fecha` + `hora` | `occurred_at` | Combined into a single ISO 8601 timestamp |
   | `ciudad` | `city` | Bogotá, Medellín, Cali or Barranquilla |
   | `via` | `road` | Non-empty text |
   | `severidad` | `severity` | leve/moderado/grave/fatal in the Excel, translated to minor/moderate/severe/fatal on save |
   | `vehiculos_involucrados` | `vehicles_involved` | Integer 1-20 |
   | `nombre_persona_involucrada` | `involved_person_name` | Non-empty text (PII) |
   | `cedula_persona_involucrada` | `involved_person_id` | Numeric, 6-10 digits (PII) |

   API exposed as a REST API (not an HTTP API) in order to use API Gateway's native API Key (`private: true` on the event + `provider.apiGateway.apiKeys`): without the correct `x-api-key` header, API Gateway rejects the request before invoking the Lambda. Schema and validations shared in `backend/src/common/accident_reports.py`, reused by Lambdas 2 and 3. `severity` is also translated (leve→minor, moderado→moderate, grave→severe, fatal→fatal) before saving; `city`/`road` are not translated (proper nouns).
2. The `ObjectCreated` event from that S3 bucket triggers **Lambda 2** (`SplitAndEnqueue`) — ✅ built: reuses `backend/src/common/accident_reports.py` to re-parse/re-validate the Excel (Lambda 1 doesn't pass it the already-parsed data, only the file in S3) and, if it's still fully valid, splits the Excel into one JSON per row (with `source_s3_key` and `row_number` for traceability) and sends them to SQS with `send_message_batch` (batches of up to 10). When done, it moves the file (copy + delete, S3 has no native "move") to `processed/` if it succeeded or to `failed/` if something failed (before re-raising the error). The S3 trigger is scoped to the `uploads/` prefix (`rules: - prefix: uploads/`), essential to avoid triggering a loop when moving files to `processed/`/`failed/` within the same bucket. Lambda 2 failing while re-validating a file that Lambda 1 already accepted is a symptom of a bug in the code itself (not of the user's data — that case was already resolved synchronously by Lambda 1); that's why alerting on those failures is an operational concern (see the CloudWatch alarm further below), not something the user needs to see.
3. **SQS**, with a **Dead Letter Queue (DLQ)** configured, triggers **Lambda 3** (`ValidateAndPersist`) — ✅ built, with a batch size of 1 (processes one row per invocation):
   - Validates the row (defense in depth; doesn't blindly trust what Lambda 1/2 already validated).
   - If valid: encrypts `involved_person_name` and `involved_person_id` (Fernet, key from Secrets Manager) before saving; fetches the Mongo credentials from **Secrets Manager** (cached in a module-level variable across "warm" invocations) and uses a **Mongo client that's also cached/reused** across invocations, to save the document (with `created_at`/`updated_at` in UTC) to MongoDB Atlas.
   - If validation fails: the Lambda **explicitly sends the message to the DLQ itself** (original row + `validation_errors`), instead of letting the exception propagate and having SQS retry it until it exhausts its `maxReceiveCount` (a row with invalid data doesn't get fixed by retrying; the DLQ should conceptually be reserved for processing failures, not just "SQS gave up"). The PII in that DLQ message is left in plain text on purpose, so someone can fix the data before a redrive.
   - Reserved concurrency: **not applied, permanently while this project is built on an AWS free-tier account** (a total limit of only 10 concurrent executions, with AWS requiring at least 10 unreserved); there's no room to reserve anything.
4. IAM roles: one per Lambda, with minimal permissions (Lambda 1: `s3:PutObject`; Lambda 2: `s3:GetObject`/`DeleteObject` on `uploads/*`, `s3:PutObject` on `processed/*` and `failed/*`, `sqs:SendMessage`; Lambda 3: `sqs:ReceiveMessage`/`DeleteMessage` on the queue, `sqs:SendMessage` to the DLQ, `secretsmanager:GetSecretValue` scoped to the Mongo and PII-key secrets' ARNs).

**Database**: MongoDB Atlas, free tier **M0** (not AWS DocumentDB: it has no real free tier and would require putting the Lambdas inside a VPC).

`backend` exposes the API at API Gateway's default URL, with no custom domain.

## Streaming flow architecture

Fixed traffic sensors report average speed and vehicle count per road, every few seconds, via MQTT against **AWS IoT Core**. Same pattern already proven in the batch flow: **IoT Core → SQS → Lambda → MongoDB**, with the Lambda validating again for defense in depth and forwarding invalid rows itself to its own DLQ (same approach as batch's Lambda 3).

**Why not Kinesis Data Streams**: it's AWS's "classic" streaming service, but it has no real free tier (it bills per shard-hour from minute one, regardless of traffic) — that would break this project's premise of living within the free tier. IoT Core does have a message free tier, and it also fits the "sensors" theme.

**Status**: built, deployed and tested end to end, both with `aws iot-data publish` and with a real certificate via `mosquitto_pub` (see below).

- The 3 shared Lambda Layers live in their own stack (`backend/serverless/layers`, see "Monorepo structure"), also consumed by this flow.
- `SensorReadings`/`SensorReadingsDLQ` queues in `infrastructure/serverless/queue` (the same stack that already hosted the batch queues) — ✅ deployed.
- Stack `infrastructure/serverless/iot` — ✅ deployed: a **generic, reusable IoT Policy** (not tied to a specific device) that uses IoT policy variables (`${iot:Connection.Thing.ThingName}`) so each certificate can only connect/publish on its own topic (`sensors/traffic/<its-thing-name>/data`), and an `AWS::IoT::TopicRule` (`SELECT *, topic(3) AS thing_name FROM 'sensors/traffic/+/data'`) that routes each message to `SensorReadingsQueue`, with its own IAM role (`sqs:SendMessage` scoped to that queue). The `topic(3) AS thing_name` adds the topic segment corresponding to the Thing's name to the message (the name `sensor_id` isn't reused because AWS IoT SQL's documentation doesn't specify how it would resolve a name collision with `SELECT *`): since the Policy already guarantees that segment matches the `ThingName` of the certificate that published (`iot:Publish` scoped to `sensors/traffic/${iot:Connection.Thing.ThingName}/data`), it's a trustworthy identity source — the sensor's own JSON payload has no `sensor_id` field at all, precisely so there's no client-controlled value to trust instead. `PersistSensorReading` uses `thing_name` to set `sensor_id` before validating/persisting (see below). Deliberately does **not** include the Thing/certificate for a specific device — that's per-sensor provisioning, not a fixed resource of the stack (see `provision_sensor.sh` below).
- Stack `backend/serverless/streaming` — ✅ deployed: `PersistSensorReading` Lambda (batchSize 1, same defense-in-depth + self-forward-to-its-DLQ pattern as batch's Lambda 3) + its IAM role. The sensor's own JSON payload is just `city`, `road`, `speed_avg`, `vehicle_count`, `recorded_at` — no PII (there's no person involved), so it uses neither encryption nor the `Security` layer. It deliberately has no `sensor_id` field: the device already identified itself by the topic it's authorized to publish to, so asking it to repeat that in the payload would just be one more client-controlled value to distrust. `sensor_id` is set entirely server-side from the trusted `thing_name` (see above) before validating. Persists to MongoDB Atlas, same `trafficMonitoring` database, new `trafficSensorReadings` collection.
- `backend/src/common/mongo.py`: shared Mongo connection/cache helper (`get_collection(secret_name, collection_name)`), extracted so both `PersistSensorReading` and batch's Lambda 3 reuse it without duplicating the "warm" client-caching pattern.
- CloudWatch alarm on the sensor readings DLQ, in the same `alerts` stack as batch (see "Observability").
- Tested end to end with `aws iot-data publish` (publishes directly with IAM credentials, no device certificate — valid for testing the IoT Core → queue → Lambda mechanism, but not a sensor's real authentication).
- Simulating sensors with a real certificate: `backend/tests/sensor_readings/provision_sensor.sh <sensor-id>` (creates the Thing + X.509 certificate, attaches the already-deployed `SensorReadingsPolicy` and the Thing to it; idempotent per sensor) and `send_sensor_reading.sh <sensor-id> [file] [topic]` (publishes via `mosquitto_pub` with mTLS, the same authentication path a real sensor would use). Successfully tested: valid and invalid publishes (to a sensor's own DLQ), plus the negative test — one sensor's certificate publishing on another's topic — confirmed blocked by the Policy (verified by subscribing to that topic from the IoT Core console: the message never arrived). `mosquitto_pub`'s `-i` must match the certificate's Thing name, since the Policy uses `${iot:Connection.Thing.ThingName}` for `iot:Connect`; a mismatched client ID drops the connection immediately ("connection was lost"). Requires the `mosquitto-clients` package (already in `img-backend`).

## Observability

Stack `infrastructure/serverless/alerts` — ✅ built: an SNS topic with an email subscription (`ALERTS_EMAIL`, needs the subscription confirmed the first time the stack is deployed) receives three CloudWatch alarms:

- Visible messages in the accident reports DLQ (`ApproximateNumberOfMessagesVisible >= 1`): indicates rows Lambda 3 couldn't validate/process.
- Errors in Lambda 2 (`SplitAndEnqueue`, `Errors` metric >= 1): indicates it failed re-validating a file Lambda 1 had already accepted, a symptom of a bug in the code itself (see point 2 of the batch flow architecture).
- Visible messages in the sensor readings DLQ (`ApproximateNumberOfMessagesVisible >= 1`, same criterion as accidents'): indicates readings `PersistSensorReading` couldn't validate/process.

There's no alarm on Lambda 1 or Lambda 3 errors: Lambda 1 responds its errors directly to the client via API Gateway (synchronous), and Lambda 3's invalid rows go to the DLQ (already covered by the alarm above) instead of raising an exception. Streaming has no step equivalent to Lambda 2 (IoT Core routes straight to the queue with no intermediate re-validation), so it doesn't have that second "bug in the code" alarm either.

The same stack also defines an **AWS Budget on cost** (`AWS::Budgets::Budget`, USD 1/month, notifies by email on both actual and forecasted spend): unlike the CloudWatch alarms (scoped to this pipeline), the Budget covers spend for **the whole AWS account**, meant to catch anything that fell outside the free tier. "Free Tier Alerts" (a Billing account preference, not an IaC resource, that would warn before any real charge) was deliberately not also turned on: it was considered and dropped as redundant next to the Budget, for this project's scope.

## Database seeding and index migrations

`backend/database/` (not IaC — MongoDB Atlas itself isn't managed by any IaC tool in this project, its M0 cluster is created manually) — mirrors a pattern Juan Pablo already uses in another of his projects:

- `backend/database/seeders/seed_mongo.py` + `seed.sh`: fills `accidentReports`/`trafficSensorReadings` with realistic synthetic data (`Faker`, plus a small curated list of real road names per city), reusing the real validation (`accident_reports.validate_row`, `sensor_readings.validate_reading`) and PII encryption (`validate_and_persist.pii.encrypt`) so seeded documents are indistinguishable from ones a real device/upload would produce. Meant to feed a later (not yet built) ETL to RDS PostgreSQL and a Bedrock agent. `seed.sh` refuses to run unless the `MongoCredentials` secret's `STAGE` tag is `dev` or `test`, so synthetic data can never land in a real environment by accident.
- `backend/database/migrations/`: index management via the `mongodb-migrations` PyPI package (CLI `mongodb-migrate`). Migration files (`migrations/migrations/<timestamp>_*.py`) implement `mongodb_migrations.base.BaseMigration`'s `upgrade`/`downgrade`, each just calling `create_index`/`drop_index` via the same `mongo.get_collection` helper the Lambdas use. `migrate.sh` resolves the Mongo secret itself (bash + `aws secretsmanager` + `jq`, URL-encoding the password) since it drives the `mongodb-migrate` CLI directly, not Python code. Applied migrations are tracked in an automatically-created `migrationLogs` collection — the audit trail this pattern is meant to give.
- Current indexes: `accidentReports` on `(city, occurred_at)`, `trafficSensorReadings` on `(sensor_id, recorded_at)` — chosen to match the two most natural query patterns ("accidents in city X, most recent first" / "readings for sensor X, ordered by time").
- `backend/database/demo_indexes.py`: the classroom demo. Always reverts every index first (via `migrate.sh`, unconditionally — not an opt-in flag, since a real before/after is the script's only job), runs `explain()` before the index exists (`COLLSCAN`), re-applies the real migration, runs `explain()` again (`IXSCAN`), and prints the before/after with the speedup made explicit (not just raw numbers) so the improvement is obvious in class and the demo is repeatable across class sections without remembering any flag.
- `Faker` and `mongodb-migrations` are devcontainer-only dependencies, added to `img-backend` in `.docker/Dockerfile` the same way `boto3` was (a plain `pip3 install`, not a Lambda Layer — nothing here is ever deployed as a Lambda).

## Commit convention

Base: Conventional Commits (see [reference article](https://medium.com/@iambonitheuri/the-art-of-writing-meaningful-git-commit-messages-a56887a4cb49)): types like `feat`/`fix`/`refactor`/`chore`/`docs`/`test`/etc., imperative mood, no trailing period.

**The actual style Juan Pablo uses in this repo**: each line of the message is a bullet `* <type>: <description>` (with a literal `*` at the start), one line per distinct change, even if several land in the same commit. No separate body, no additional explanation below the bullets. Real example:

```
* feat: add ValidateAndStore Lambda behind a REST API with an API key
* feat: add shared Commons Lambda layer for Python dependencies
* chore: ignore Lambda layer python/ folders in prettier, yapf and isort
* docs: update backend README deployment section for the single-stack layout
```

When a commit touches several things (code + docs, for example), reflect each one in its own bullet, don't just summarize the main one. If the changes are very different in nature, prefer several separate commits over a single commit with many unrelated bullets.

**Never add Claude co-authorship to commits in this repository.**

## Changelog convention

While the project has no release yet, `changelog.md`'s `[Unreleased]`/`[x.x.x]` entry only lists final state (`Added`/`Changed`), not internal fixes made along the way (e.g. a bug fixed before it ever shipped isn't its own `Fixed` bullet — the final, correct behavior is just what `Added` describes).

## Open items

- Frontend for uploading the Excel file: not part of the current scope.
