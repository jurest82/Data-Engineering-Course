#!/bin/bash
# Generates a "<name>.json" (ready to paste as the Postman body) next to each
# "<name>.xlsx" fixture in this folder: {"file": "<base64 of that .xlsx>"}
set -e
cd "$(dirname "$0")"

for FILE in *.xlsx; do
  NAME="${FILE%.xlsx}"
  ENCODED=$(base64 -i "$FILE" | tr -d '\n')
  printf '{"file": "%s"}\n' "$ENCODED" > "${NAME}.json"
  echo "Generated ${NAME}.json"
done
