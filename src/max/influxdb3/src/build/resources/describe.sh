#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: ${0} [-v|--verbose] [-h|--help] [database]"
  echo "       influxdb3 describe, print the live schema of a database as line protocol"
  exit 2
}

SCHEMA_VERBOSE=${SCHEMA_VERBOSE:-false}
DATABASE=""
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    SCHEMA_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    usage
    ;;
  *)
    DATABASE="$1"
    shift
    ;;
  esac
done

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODULE_DIR="${ROOT_DIR}"
while [ "${MODULE_DIR}" != "/" ] && [ ! -f "${MODULE_DIR}/.env" ]; do
  MODULE_DIR="$(dirname "${MODULE_DIR}")"
done

if [ ! -f "${MODULE_DIR}/.env" ]; then
  echo "Schema script [influxdb3] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE="${DATABASE:-${INFLUXDB3_DATABASE_HOME}}"
TARGET="${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}"

# noinspection HttpUrlsUsage
query() {
  local response status
  response="$(curl -sS -w '\n%{http_code}' -X POST \
    "http://${TARGET}/api/v3/query_sql" \
    -H "Authorization: Bearer ${INFLUXDB3_TOKEN_ADMIN}" \
    -H "Content-Type: application/json" \
    --data-binary "$(jq -n --arg db "${DATABASE}" --arg q "$1" '{db: $db, q: $q, format: "json"}')")"
  status="${response##*$'\n'}"
  if [ "${status}" != "200" ]; then
    echo "Schema script [influxdb3] query failed [${1}] status [${status}] response [${response%$'\n'*}]" >&2
    return 1
  fi
  printf '%s' "${response%$'\n'*}"
}

values() {
  local table="$1" column="$2" summary cardinality value
  summary="$(query "SELECT count(DISTINCT \"${column}\") AS cardinality, min(\"${column}\") AS value
    FROM \"${table}\" WHERE \"${column}\" IS NOT NULL" |
    jq -r '.[0] | [(.cardinality // 0), (.value // "")] | @tsv')"
  IFS=$'\t' read -r cardinality value <<<"${summary}"
  if [ "${cardinality}" = "1" ]; then
    printf '%s\t%s' "${cardinality}" "${value}"
    return 0
  fi
  printf '%s\t<%s-strings>' "${cardinality}" "${cardinality}"
}

placeholder() {
  case "$1" in
  *Dictionary* | *Utf8*) echo "<text>" ;;
  *Int*) echo "<number>i" ;;
  *Float* | *Decimal*) echo "<number>" ;;
  *Boolean*) echo "<true|false>" ;;
  *) echo "<value>" ;;
  esac
}

printf '\nSchema describe [influxdb3] database [%s] against [%s]\n\n' "${DATABASE}" "${TARGET}"

TABLES="$(query "SELECT table_name FROM information_schema.tables WHERE table_schema = 'iox' ORDER BY table_name" |
  jq -r '.[].table_name')"

if [ -z "${TABLES}" ]; then
  echo "Schema script [influxdb3] database [${DATABASE}] carries no tables" >&2
  exit 1
fi

while IFS= read -r TABLE; do
  COLUMNS="$(query "SELECT column_name, data_type FROM information_schema.columns
    WHERE table_schema = 'iox' AND table_name = '${TABLE}' ORDER BY column_name" |
    jq -r '.[] | [.column_name, .data_type] | @tsv')"
  TAGS=""
  RANKED=()
  FIELDS=()
  while IFS=$'\t' read -r COLUMN TYPE; do
    [ -z "${COLUMN}" ] && continue
    [ "${COLUMN}" = "time" ] && continue
    if [[ "${TYPE}" == *Dictionary* ]]; then
      IFS=$'\t' read -r CARDINALITY RENDERED <<<"$(values "${TABLE}" "${COLUMN}")"
      RANKED+=("$([ "${COLUMN}" = "module" ] && echo 0 || echo 1)"$'\t'"${CARDINALITY}"$'\t'"${COLUMN}"$'\t'"${RENDERED}")
    else
      FIELDS+=("    ${COLUMN}=$(placeholder "${TYPE}")")
    fi
  done <<<"${COLUMNS}"
  if [ "${#RANKED[@]}" -gt 0 ]; then
    while IFS=$'\t' read -r _ _ COLUMN RENDERED; do
      TAGS="${TAGS},${COLUMN}=${RENDERED}"
    done < <(printf '%s\n' "${RANKED[@]}" | sort -t$'\t' -k1,1n -k2,2n -k3,3)
  fi
  echo "${TABLE}${TAGS}"
  for INDEX in "${!FIELDS[@]}"; do
    if [ "${INDEX}" -lt "$((${#FIELDS[@]} - 1))" ]; then
      echo "${FIELDS[${INDEX}]},"
    else
      echo "${FIELDS[${INDEX}]}"
    fi
  done
  echo "    <timestamp>"
  echo ""
done <<<"${TABLES}"
