#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

set -uo pipefail

SCHEMA_VERBOSE=${SCHEMA_VERBOSE:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    SCHEMA_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${0} [-v|--verbose] [-h|--help]"
    echo "       postgres describe print what the instance actually holds"
    exit 2
    ;;
  *)
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
  echo "Schema script [postgres] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE_USER="${DATABASE_USER:-${POSTGRES_DATABASE_USER:-${POSTGRES_USER:-}}}"
DATABASE_NAME="${DATABASE_NAME:-${POSTGRES_DATABASE_NAME:-${POSTGRES_DATABASE_MAINTENANCE:-}}}"
DATABASE_PASSWORD="${DATABASE_PASSWORD:-${POSTGRES_DATABASE_PASSWORD:-${POSTGRES_KEY:-}}}"

for VARIABLE in DATABASE_USER DATABASE_NAME DATABASE_PASSWORD; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [postgres] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

export PGPASSWORD="${DATABASE_PASSWORD}"
export PGTZ="${TZ:-UTC}"

query() {
  psql -h "${POSTGRES_SERVICE_PROD}" -p "${POSTGRES_API_PORT}" -U "${DATABASE_USER}" -d "${DATABASE_NAME}" \
    -q -t -A -v ON_ERROR_STOP=1 -c "SELECT row_to_json(result) FROM ($1) AS result" 2>&1
}

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

table() {
  jq -sr --argjson clip 50 '
    def title: split("_") | map(if length > 0 then (.[0:1] | ascii_upcase) + .[1:] else . end) | join(" ");
    def numeric: type == "number" or (type == "string" and test("^-?[0-9]+([.][0-9]+)?$"));
    def placeholder: . == "-" or . == "";
    def clip: if $clip > 0 and length > $clip then .[0:($clip - 3)] + "..." else . end;
    (if length == 1 and (.[0] | type) == "array" then .[0] else . end)
    | if length == 0 then "no rows" else
      (.[0] | keys_unsorted) as $columns
      | [range(0; $columns | length)] as $indexes
      | (map(. as $row | $columns
        | map(if $row[.] == null then "" else ($row[.] | tostring | clip) end))) as $body
      | ([$columns | map(title)] + $body) as $matrix
      | ($indexes | map(. as $index | $matrix | map(.[$index] | length) | max)) as $widths
      | ($indexes | map(. as $index | $body | map(.[$index])
        | (any(numeric) and all(numeric or placeholder)))) as $rights
      | (def row($cells): "|" + ($cells | to_entries | map(
           ((" " * ($widths[.key] - (.value | length))) // "") as $fill
           | if $rights[.key] then " " + $fill + .value + " " else " " + .value + $fill + " " end)
           | join("|")) + "|";
         def rule: "+" + ($indexes | map("-" * ($widths[.] + 2)) | join("+")) + "+";
         [rule, row($matrix[0]), rule] + ($body | map(row(.))) + [rule] | join("\n"))
    end
  '
}

rows() {
  jq -s '(if length == 1 and (.[0] | type) == "array" then .[0] else . end) | length'
}

SCHEMA_ECHO=${SCHEMA_ECHO:-true}
SCHEMA_LABEL=${SCHEMA_LABEL:-}

statements() {
  sed -e 's/--.*$//' | tr '\n' ' ' | tr ';' '\n' |
    sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

query_block() {
  local block="$1" statement label result
  statement="$(printf '%s\n' "${block}" | sed -e 's/--.*$//' | tr '\n' ' ' |
    sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*;*[[:space:]]*$//')"
  [ -z "${statement}" ] && return 0
  label="${SCHEMA_LABEL}"
  if [ -z "${label}" ]; then
    label="$(printf '%s\n' "${block}" | sed -n -e 's/^-- //p' | head -1)"
  fi
  printf -- '\n-- %s\n\n' "${label}"
  if [ "${SCHEMA_ECHO}" = true ]; then
    printf '%s\n\n' "${block}"
  fi
  if ! result="$(query "${statement}")"; then
    fail "${statement}" "${result}"
    return 1
  fi
  printf '%s\n' "${result}" | table
  printf '\n'
}

query_one() {
  local result
  if ! result="$(query "$1")"; then
    fail "$1" "${result}"
    return 1
  fi
  printf '%s\n' "${result}" | table
}

query_sql() {
  local line block="" faults=0
  while IFS= read -r line || [ -n "${line}" ]; do
    case "${line}" in
    ---*) continue ;;
    "-- WARNING:"*) continue ;;
    esac
    [ -z "${block}" ] && [ -z "${line}" ] && continue
    block="${block}${line}"$'\n'
    case "${line}" in
    *\;)
      query_block "${block%$'\n'}" || faults=$((faults + 1))
      block=""
      ;;
    esac
  done
  if [ -n "${block}" ]; then
    query_block "${block%$'\n'}" || faults=$((faults + 1))
  fi
  [ "${faults}" = 0 ]
}

section() {
  printf -- '\n-- %s\n\n' "$1"
}

slurp() {
  jq -rs '(if length == 1 and (.[0] | type) == "array" then .[0] else . end) | '"$1"
}

printf '\nSchema describe [%s] against [%s]\n' "postgres" "${POSTGRES_SERVICE_PROD}"

DATABASES="SELECT
    d.datname                                         AS database,
    pg_get_userbyid(d.datdba)                         AS owner,
    pg_encoding_to_char(d.encoding)                   AS encoding,
    pg_size_pretty(pg_database_size(d.datname))       AS size,
    count(s.pid)                                      AS sessions
  FROM pg_database d LEFT JOIN pg_stat_activity s ON s.datname = d.datname
  WHERE d.datallowconn AND NOT d.datistemplate
  GROUP BY d.datname, d.datdba, d.encoding
  ORDER BY pg_database_size(d.datname) DESC"

EXTENSIONS="SELECT extname AS extension, extversion AS version FROM pg_extension ORDER BY extname"

TABLES="SELECT
    n.nspname                                         AS schema,
    c.relname                                         AS table,
    pg_size_pretty(pg_total_relation_size(c.oid))     AS size,
    CASE WHEN c.reltuples < 0 THEN '-'
         ELSE c.reltuples::bigint::text END           AS estimate
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'r'
    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    AND n.nspname NOT LIKE '\\_timescaledb%'
  ORDER BY pg_total_relation_size(c.oid) DESC"

HYPERTABLES="SELECT
    hypertable_schema                                 AS schema,
    hypertable_name                                   AS table,
    num_chunks                                        AS chunks,
    compression_enabled                               AS compressed,
    pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS size
  FROM timescaledb_information.hypertables
  ORDER BY hypertable_schema, hypertable_name"

databases() {
  query "${DATABASES}" | slurp '.[].database' | sort
}

MAINTENANCE="${DATABASE_NAME}"

section "databases"
query_one "${DATABASES}" || exit 1
printf '\n'

for DATABASE_NAME in $(databases); do
  section "extensions ${DATABASE_NAME}"
  query_one "${EXTENSIONS}" || exit 1
  printf '\n'
  section "tables ${DATABASE_NAME}"
  query_one "${TABLES}" || exit 1
  printf '\n'
  if [ "$(query "${EXTENSIONS}" | slurp 'any(.extension == "timescaledb")')" = true ]; then
    section "hypertables ${DATABASE_NAME}"
    query_one "${HYPERTABLES}" || exit 1
    printf '\n'
  fi
done

DATABASE_NAME="${MAINTENANCE}"
