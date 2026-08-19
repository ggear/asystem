#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

set -euo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")/database"

PSQL=(psql -h "${DATABASE_HOST}" -p "${DATABASE_PORT}" -U "${DATABASE_USER}" -d "${DATABASE_NAME}")
export PGPASSWORD="${DATABASE_PASSWORD}"

printf '\nSchema apply [%s] against [%s]\n' "wrangle" "${DATABASE_HOST}"
for SQL_FILE in "${ROOT_DIR}"/*.sql; do
  printf -- '\n-- %s\n\n' "$(basename "${SQL_FILE}")"
  "${PSQL[@]}" -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
done
