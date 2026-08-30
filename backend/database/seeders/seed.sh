#!/bin/bash
# Seeds accidentReports/trafficSensorReadings with realistic synthetic data.
# Refuses to run unless the MongoCredentials secret is tagged STAGE=dev or
# STAGE=test, so synthetic data can never land in a real environment by
# accident (same guard pattern used in other projects' seeders).
#
# Run inside the backend devcontainer:
#   cd /app/backend && ./database/seeders/seed.sh [--accident-reports N] [--sensor-readings N] [--sensors N] [--reset]
#   e.g. cd /app/backend && ./database/seeders/seed.sh --accident-reports 10000 --sensor-readings 20000 --sensors 200 --reset
set -e

STAGE=$(aws secretsmanager describe-secret \
  --secret-id "/${DEPLOY_APP}-secrets/MongoCredentials" \
  --query "Tags[?Key=='STAGE'].Value" --output text)

if [ "$STAGE" != "dev" ] && [ "$STAGE" != "test" ]; then
  echo "Seeding skipped for '$STAGE' stage (only dev/test allowed)." >&2
  exit 1
fi

# seed_mongo.py imports src.validate_and_persist.pii, which reads this env var
# at import time (not lazily); a Lambda gets it from its `environment:` block,
# so we export it ourselves here for this plain script.
export PII_ENCRYPTION_KEY_SECRET_NAME="/${DEPLOY_APP}-secrets/PiiEncryptionKey"
python3 -m database.seeders.seed_mongo "$@"
