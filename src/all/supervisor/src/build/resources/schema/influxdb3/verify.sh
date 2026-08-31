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
    echo "       influxdb3 verify assert production matches the declaration"
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
  echo "Schema script [supervisor] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE_NAME="${DATABASE_NAME:-${SUPERVISOR_DATABASE_NAME:-${INFLUXDB3_DATABASE_HOME:-}}}"
DATABASE_TOKEN="${DATABASE_TOKEN:-${SUPERVISOR_DATABASE_TOKEN:-${INFLUXDB3_TOKEN_ADMIN:-}}}"

for VARIABLE in DATABASE_NAME DATABASE_TOKEN; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [supervisor] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
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

verify_sql() {
  cat <<'SCHEMA_SQL'
--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    'supervisor/host' AS relation,
    'status'          AS measure,
    '6s'              AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'status_trend'    AS measure,
    '6s'              AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_processor'  AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor') = 0
UNION ALL
SELECT
    'supervisor/host'      AS relation,
    'used_processor_trend' AS measure,
    '6s'                   AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_memory'     AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'used_memory_trend' AS measure,
    '6s'                AS period,
    '%'                 AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'allocated_memory' AS measure,
    '6s'               AS period,
    '%'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'allocated_memory') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'allocated_memory_trend' AS measure,
    '6s'                     AS period,
    '%'                      AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'allocated_memory_trend') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'failed_log_messages' AS measure,
    '6s'                  AS period,
    '%'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_log_messages') = 0
UNION ALL
SELECT
    'supervisor/host'           AS relation,
    'failed_log_messages_trend' AS measure,
    '6s'                        AS period,
    '%'                         AS unit,
    'missing'                   AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_log_messages_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'failed_shares'   AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_shares') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'failed_shares_trend' AS measure,
    '6s'                  AS period,
    '%'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_shares_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'failed_backups'  AS measure,
    '6s'              AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_backups') = 0
UNION ALL
SELECT
    'supervisor/host'      AS relation,
    'failed_backups_trend' AS measure,
    '6s'                   AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_backups_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'warn_temperature' AS measure,
    '6s'               AS period,
    '%'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'warn_temperature') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'warn_temperature_trend' AS measure,
    '6s'                     AS period,
    '%'                      AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'warn_temperature_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'spin_fan_speed'  AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'spin_fan_speed') = 0
UNION ALL
SELECT
    'supervisor/host'      AS relation,
    'spin_fan_speed_trend' AS measure,
    '6s'                   AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'spin_fan_speed_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'life_used_drives' AS measure,
    '6s'               AS period,
    '%'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'life_used_drives') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'life_used_drives_trend' AS measure,
    '6s'                     AS period,
    '%'                      AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'life_used_drives_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_home_space' AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_home_space') = 0
UNION ALL
SELECT
    'supervisor/host'       AS relation,
    'used_home_space_trend' AS measure,
    '6s'                    AS period,
    '%'                     AS unit,
    'missing'               AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_home_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'used_share_space' AS measure,
    '6s'               AS period,
    '%'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_share_space') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'used_share_space_trend' AS measure,
    '6s'                     AS period,
    '%'                      AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_share_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'used_backup_space' AS measure,
    '6s'                AS period,
    '%'                 AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_backup_space') = 0
UNION ALL
SELECT
    'supervisor/host'         AS relation,
    'used_backup_space_trend' AS measure,
    '6s'                      AS period,
    '%'                       AS unit,
    'missing'                 AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_backup_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_swap_space' AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_swap_space') = 0
UNION ALL
SELECT
    'supervisor/host'       AS relation,
    'used_swap_space_trend' AS measure,
    '6s'                    AS period,
    '%'                     AS unit,
    'missing'               AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_swap_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_disk_ops'   AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'used_disk_ops_trend' AS measure,
    '6s'                  AS period,
    '%'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_network'    AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network') = 0
UNION ALL
SELECT
    'supervisor/host'    AS relation,
    'used_network_trend' AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'temperature'     AS measure,
    '6s'              AS period,
    '°C'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'temperature') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'temperature_trend' AS measure,
    '6s'                AS period,
    '°C'                AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'temperature_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'failed_drives'   AS measure,
    '6s'              AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_drives') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'failed_drives_trend' AS measure,
    '6s'                  AS period,
    '%'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_drives_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'status'             AS measure,
    '6s'                 AS period,
    '-'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'status_trend'       AS measure,
    '6s'                 AS period,
    '-'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'backup_status'      AS measure,
    '6s'                 AS period,
    '-'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'backup_status') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'backup_status_trend' AS measure,
    '6s'                  AS period,
    '-'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'backup_status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'health_status'      AS measure,
    '6s'                 AS period,
    '-'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'health_status') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'health_status_trend' AS measure,
    '6s'                  AS period,
    '-'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'health_status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'configured_status'  AS measure,
    '6s'                 AS period,
    '-'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'configured_status') = 0
UNION ALL
SELECT
    'supervisor/service'      AS relation,
    'configured_status_trend' AS measure,
    '6s'                      AS period,
    '-'                       AS unit,
    'missing'                 AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'configured_status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_processor'     AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor') = 0
UNION ALL
SELECT
    'supervisor/service'   AS relation,
    'used_processor_trend' AS measure,
    '6s'                   AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_memory'        AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_memory_trend'  AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_disk_ops'      AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'used_disk_ops_trend' AS measure,
    '6s'                  AS period,
    '%'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_network'       AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_network_trend' AS measure,
    '6s'                 AS period,
    '%'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'restart_count'      AS measure,
    '6s'                 AS period,
    '-'                  AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'restart_count') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'restart_count_trend' AS measure,
    '6s'                  AS period,
    '-'                   AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'restart_count_trend') = 0
UNION ALL
SELECT
    'supervisor' AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
    AND column_name NOT IN (
        'allocated_memory', 'allocated_memory_trend', 'backup_status',
        'backup_status_trend', 'configured_status', 'configured_status_trend',
        'failed_backups', 'failed_backups_trend', 'failed_drives', 'failed_drives_trend',
        'failed_log_messages', 'failed_log_messages_trend', 'failed_shares',
        'failed_shares_trend', 'health_status', 'health_status_trend', 'host',
        'life_used_drives', 'life_used_drives_trend', 'module', 'restart_count',
        'restart_count_trend', 'service', 'spin_fan_speed', 'spin_fan_speed_of_max',
        'spin_fan_speed_of_max_trend', 'spin_fan_speed_trend', 'status', 'status_trend',
        'temperature', 'temperature_trend', 'time', 'used_backup_space',
        'used_backup_space_trend', 'used_disk_ops', 'used_disk_ops_trend',
        'used_home_space', 'used_home_space_trend', 'used_memory', 'used_memory_trend',
        'used_network', 'used_network_trend', 'used_processor', 'used_processor_trend',
        'used_share_space', 'used_share_space_trend', 'used_swap_space',
        'used_swap_space_trend', 'used_system_space', 'used_system_space_trend',
        'warn_temperature', 'warn_temperature_of_max', 'warn_temperature_of_max_trend',
        'warn_temperature_trend'
    )
ORDER BY fault, measure;
SCHEMA_SQL
}

printf '\nSchema verify [%s] against [%s]\n' "supervisor" "${INFLUXDB3_SERVICE_PROD}"
printf -- '\n-- %s\n\n' "verify"

pending() {
  jq -s '(if length == 1 and (.[0] | type) == "array" then .[0] else . end)
    | map(select(.fault == "pending")) | length'
}

FAULTS=0
PENDING=0
while IFS= read -r STATEMENT; do
  [ -z "${STATEMENT}" ] && continue
  if ! RESULT="$(query "${STATEMENT}")"; then
    fail "${STATEMENT}" "${RESULT}"
    exit 1
  fi
  COUNT="$(printf '%s' "${RESULT}" | rows)"
  if [ "${COUNT}" != "0" ]; then
    WAITING="$(printf '%s' "${RESULT}" | pending)"
    PENDING=$((PENDING + WAITING))
    FAULTS=$((FAULTS + COUNT - WAITING))
    printf '%s\n' "${RESULT}" | table
    printf '\n'
  fi
done < <(verify_sql | statements)

if [ "${PENDING}" != "0" ]; then
  printf '\nSchema verify [%s] found [%s] retired measure(s) still carried, see mutate.sh\n' "supervisor" "${PENDING}" >&2
fi
if [ "${FAULTS}" != "0" ]; then
  printf '\nSchema verify [%s] found [%s] fault row(s)\n' "supervisor" "${FAULTS}" >&2
  exit 1
fi
printf '\nSchema verify [%s] found no drift\n' "supervisor"
