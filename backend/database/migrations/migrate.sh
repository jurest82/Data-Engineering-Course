#!/bin/bash
# Applies (or reverts) the MongoDB index migrations in ./migrations, tracked
# in the migrationLogs collection so re-running this is always safe --
# already-applied migrations are skipped automatically.
#
# Run inside the backend devcontainer:
#   cd /app/backend && ./database/migrations/migrate.sh                        # upgrade all pending
#   cd /app/backend && ./database/migrations/migrate.sh --downgrade            # revert ALL applied migrations
#   cd /app/backend && ./database/migrations/migrate.sh --downgrade 20260829000000  # revert down to (not including) that timestamp
#   cd /app/backend && ./database/migrations/migrate.sh --upgrade 20260829000000    # upgrade only up to that timestamp
set -e

EXEC_PATH=$(dirname "$(readlink -f "$0")")
# mongodb-migrate has no "--upgrade" flag -- upgrading is just what it does
# when "--downgrade" is absent, so this array only gains an element when
# downgrading (passing an empty string as an argument would confuse its
# argument parser). Without --to_datetime, mongodb-migrate applies/reverts
# *every* migration, not just the ones up to a given point -- pass a
# timestamp as the second argument to limit it, same as the CLI itself.
ACTION_FLAGS=()
if [ "$1" == '-d' ] || [ "$1" == '--downgrade' ]; then
  ACTION_FLAGS=('--downgrade')
fi
if [ -n "$2" ]; then
  ACTION_FLAGS+=('--to_datetime' "$2")
fi

SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id "/${DEPLOY_APP}-secrets/MongoCredentials" \
  --query SecretString --output text)

DB_HOST=$(echo "$SECRET_JSON" | jq -r '.host')
DB_DBNAME=$(echo "$SECRET_JSON" | jq -r '.dbname')
DB_USERNAME=$(echo "$SECRET_JSON" | jq -r '.username')
# command substitution already strips the trailing newline jq's -r adds, so
# this URL-encodes the password as-is (no xargs word-splitting pitfalls for
# passwords containing spaces).
DB_PASSWORD_RAW=$(echo "$SECRET_JSON" | jq -r '.password')
DB_PASSWORD=$(printf '%s' "$DB_PASSWORD_RAW" | jq -sRr @uri)

# mongodb-migrate loads each migration file with a raw __import__(), which
# needs /app/backend on sys.path for "from src.common.mongo import ..." to
# resolve -- it isn't there by default since this runs as an installed
# console script, not via `python3 -m`.
BACKEND_ROOT=$(cd "$EXEC_PATH/../.." && pwd)
export PYTHONPATH="$BACKEND_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mongodb-migrate \
  --url "mongodb+srv://${DB_USERNAME}:${DB_PASSWORD}@${DB_HOST}/${DB_DBNAME}" \
  --migrations "$EXEC_PATH/migrations" \
  --metastore migrationLogs \
  "${ACTION_FLAGS[@]}"
