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
    echo "       influxdb3 describe print what the instance actually holds"
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

DATABASE_NAME="${DATABASE_NAME:-${INFLUXDB3_DATABASE_NAME:-${INFLUXDB3_DATABASE_HOME:-}}}"
DATABASE_TOKEN="${DATABASE_TOKEN:-${INFLUXDB3_DATABASE_TOKEN:-${INFLUXDB3_TOKEN_ADMIN:-}}}"

for VARIABLE in DATABASE_NAME DATABASE_TOKEN; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [influxdb3] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

query() {
  local response status
  response="$(curl -sS -w '\n%{http_code}' -X POST \
    "http://${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}/api/v3/query_sql" \
    -H "Authorization: Bearer ${DATABASE_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "$(jq -n --arg db "${DATABASE_NAME}" --arg q "$1" --arg format "${2:-json}" \
      '{db: $db, q: $q, format: $format}')")"
  status="${response##*$'\n'}"
  printf '%s' "${response%$'\n'*}"
  [ "${status}" = "200" ]
}

write_lp() {
  local response status
  response="$(curl -sS -w '\n%{http_code}' -X POST \
    "http://${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}/api/v3/write_lp?db=${DATABASE_NAME}&precision=nanosecond" \
    -H "Authorization: Bearer ${DATABASE_TOKEN}" \
    -H "Content-Type: text/plain" \
    --data-binary @-)"
  status="${response##*$'\n'}"
  if [ "${status}" != "204" ] && [ "${status}" != "200" ]; then
    printf 'write failed with status [%s] body [%s]\n' "${status}" "${response%$'\n'*}" >&2
    return 1
  fi
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

printf '\nSchema describe [%s] against [%s]\n' "influxdb3" "${INFLUXDB3_SERVICE_PROD}"

databases() {
  local response
  response="$(curl -sS "http://${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}/api/v3/configure/database?format=json"     -H "Authorization: Bearer ${DATABASE_TOKEN}")" || return 1
  printf '%s' "${response}" | jq -r '.[]["iox::database"]' | sort
}

catalogued() {
  query "SELECT table_name, count(*) AS columns, sum(CASE WHEN column_name = 'module' THEN 1 ELSE 0 END) AS tagged
    FROM information_schema.columns WHERE table_schema = 'iox' GROUP BY table_name ORDER BY table_name"
}

section "databases"
for DATABASE_NAME in $(databases); do
  CATALOGUE="$(catalogued)" || { fail "${DATABASE_NAME}" "${CATALOGUE}"; exit 1; }
  jq -nc --arg database "${DATABASE_NAME}" --argjson tables "$(printf '%s' "${CATALOGUE}" | rows)"     '{database: $database, tables: $tables}'
done | table
printf '
'

for DATABASE_NAME in $(databases); do
  section "tables ${DATABASE_NAME}"
  CATALOGUE="$(catalogued)" || { fail "${DATABASE_NAME}" "${CATALOGUE}"; exit 1; }
  STATEMENT=""
  while IFS=$'	' read -r TABLE COLUMNS TAGGED; do
    [ -z "${TABLE}" ] && continue
    if [ "${TAGGED}" = 0 ]; then
      MODULES="CAST(NULL AS VARCHAR)"
    else
      MODULES="string_agg(DISTINCT module, ', ')"
    fi
    [ -n "${STATEMENT}" ] && STATEMENT="${STATEMENT} UNION ALL "
    STATEMENT="${STATEMENT}SELECT '${TABLE}' AS \"table\", ${MODULES} AS \"modules\", ${COLUMNS} AS \"columns\","
    STATEMENT="${STATEMENT} count(*) AS \"rows\", CAST(min(time) + INTERVAL '480 minute' AS VARCHAR) AS \"oldest\","
    STATEMENT="${STATEMENT} CAST(max(time) + INTERVAL '480 minute' AS VARCHAR) AS \"newest\" FROM \"${TABLE}\""
  done < <(printf '%s' "${CATALOGUE}" | jq -r '.[] | [.table_name, .columns, .tagged] | @tsv')
  if [ -z "${STATEMENT}" ]; then
    printf 'no rows

'
    continue
  fi
  query_one "${STATEMENT} ORDER BY \"rows\" DESC" || exit 1
  printf '
'
done
