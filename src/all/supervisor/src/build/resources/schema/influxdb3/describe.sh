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
    echo "       influxdb3 describe print what production actually carries"
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

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

table() {
  jq -sr '
    def title: split("_") | map(if length > 0 then (.[0:1] | ascii_upcase) + .[1:] else . end) | join(" ");
    def numeric: type == "number" or (type == "string" and test("^-?[0-9]+([.][0-9]+)?$"));
    def placeholder: . == "-" or . == "";
    def clip: if length > 50 then .[0:47] + "..." else . end;
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
SCHEMA_ACTION=${SCHEMA_ACTION:-Describe}
SCHEMA_TARGET=${SCHEMA_TARGET:-}
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
  if [ -n "${SCHEMA_LABEL}" ]; then
    printf -- '-- %s\n' "${SCHEMA_LABEL}"
  fi
  if [ "${SCHEMA_ECHO}" = true ]; then
    printf '%s\n\n' "${block}"
  else
    label="$(printf '%s\n' "${block}" | sed -n -e 's/^-- //p' | head -1)"
    printf '%s [%s] against [%s]:\n\n' "${SCHEMA_ACTION}" "${label}" "${SCHEMA_TARGET}"
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

describe_sql() {
  cat <<'SCHEMA_SQL'
--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'supervisor/host'          AS relation,
    'host*'                    AS dimension,
    37                         AS measures,
    '6s'                       AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/service'       AS relation,
    'host/service*'            AS dimension,
    22                         AS measures,
    '6s'                       AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
ORDER BY rows DESC;

-- measures
SELECT
    'supervisor/host'                                            AS relation,
    'status'                                                     AS measure,
    'bool'                                                       AS kind,
    '-'                                                          AS unit,
    '6s'                                                         AS period,
    count(status)                                                AS rows,
    CAST(min(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                  AS relation,
    'status_trend'                                                     AS measure,
    'bool'                                                             AS kind,
    '-'                                                                AS unit,
    '6s'                                                               AS period,
    count(status_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                    AS relation,
    'used_processor'                                                     AS measure,
    'int'                                                                AS kind,
    '%'                                                                  AS unit,
    '6s'                                                                 AS period,
    count(used_processor)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                          AS relation,
    'used_processor_trend'                                                     AS measure,
    'int'                                                                      AS kind,
    '%'                                                                        AS unit,
    '6s'                                                                       AS period,
    count(used_processor_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                 AS relation,
    'used_memory'                                                     AS measure,
    'int'                                                             AS kind,
    '%'                                                               AS unit,
    '6s'                                                              AS period,
    count(used_memory)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'used_memory_trend'                                                     AS measure,
    'int'                                                                   AS kind,
    '%'                                                                     AS unit,
    '6s'                                                                    AS period,
    count(used_memory_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                      AS relation,
    'allocated_memory'                                                     AS measure,
    'int'                                                                  AS kind,
    '%'                                                                    AS unit,
    '6s'                                                                   AS period,
    count(allocated_memory)                                                AS rows,
    CAST(min(time) FILTER (WHERE allocated_memory IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE allocated_memory IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                            AS relation,
    'allocated_memory_trend'                                                     AS measure,
    'int'                                                                        AS kind,
    '%'                                                                          AS unit,
    '6s'                                                                         AS period,
    count(allocated_memory_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE allocated_memory_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE allocated_memory_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                         AS relation,
    'failed_log_messages'                                                     AS measure,
    'int'                                                                     AS kind,
    '-'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(failed_log_messages)                                                AS rows,
    CAST(min(time) FILTER (WHERE failed_log_messages IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_log_messages IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                               AS relation,
    'failed_log_messages_trend'                                                     AS measure,
    'int'                                                                           AS kind,
    '-'                                                                             AS unit,
    '6s'                                                                            AS period,
    count(failed_log_messages_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE failed_log_messages_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_log_messages_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                   AS relation,
    'failed_shares'                                                     AS measure,
    'int'                                                               AS kind,
    '-'                                                                 AS unit,
    '6s'                                                                AS period,
    count(failed_shares)                                                AS rows,
    CAST(min(time) FILTER (WHERE failed_shares IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_shares IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                         AS relation,
    'failed_shares_trend'                                                     AS measure,
    'int'                                                                     AS kind,
    '-'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(failed_shares_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE failed_shares_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_shares_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                    AS relation,
    'failed_backups'                                                     AS measure,
    'int'                                                                AS kind,
    '-'                                                                  AS unit,
    '6s'                                                                 AS period,
    count(failed_backups)                                                AS rows,
    CAST(min(time) FILTER (WHERE failed_backups IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_backups IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                          AS relation,
    'failed_backups_trend'                                                     AS measure,
    'int'                                                                      AS kind,
    '-'                                                                        AS unit,
    '6s'                                                                       AS period,
    count(failed_backups_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE failed_backups_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_backups_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                             AS relation,
    'warn_temperature_of_max'                                                     AS measure,
    'int'                                                                         AS kind,
    '%'                                                                           AS unit,
    '6s'                                                                          AS period,
    count(warn_temperature_of_max)                                                AS rows,
    CAST(min(time) FILTER (WHERE warn_temperature_of_max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warn_temperature_of_max IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                                   AS relation,
    'warn_temperature_of_max_trend'                                                     AS measure,
    'int'                                                                               AS kind,
    '%'                                                                                 AS unit,
    '6s'                                                                                AS period,
    count(warn_temperature_of_max_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE warn_temperature_of_max_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warn_temperature_of_max_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                           AS relation,
    'spin_fan_speed_of_max'                                                     AS measure,
    'int'                                                                       AS kind,
    '%'                                                                         AS unit,
    '6s'                                                                        AS period,
    count(spin_fan_speed_of_max)                                                AS rows,
    CAST(min(time) FILTER (WHERE spin_fan_speed_of_max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE spin_fan_speed_of_max IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                                 AS relation,
    'spin_fan_speed_of_max_trend'                                                     AS measure,
    'int'                                                                             AS kind,
    '%'                                                                               AS unit,
    '6s'                                                                              AS period,
    count(spin_fan_speed_of_max_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE spin_fan_speed_of_max_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE spin_fan_speed_of_max_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                      AS relation,
    'life_used_drives'                                                     AS measure,
    'int'                                                                  AS kind,
    '%'                                                                    AS unit,
    '6s'                                                                   AS period,
    count(life_used_drives)                                                AS rows,
    CAST(min(time) FILTER (WHERE life_used_drives IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE life_used_drives IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                            AS relation,
    'life_used_drives_trend'                                                     AS measure,
    'int'                                                                        AS kind,
    '%'                                                                          AS unit,
    '6s'                                                                         AS period,
    count(life_used_drives_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE life_used_drives_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE life_used_drives_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'used_system_space'                                                     AS measure,
    'int'                                                                   AS kind,
    '%'                                                                     AS unit,
    '6s'                                                                    AS period,
    count(used_system_space)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_system_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_system_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                             AS relation,
    'used_system_space_trend'                                                     AS measure,
    'int'                                                                         AS kind,
    '%'                                                                           AS unit,
    '6s'                                                                          AS period,
    count(used_system_space_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_system_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_system_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                      AS relation,
    'used_share_space'                                                     AS measure,
    'int'                                                                  AS kind,
    '%'                                                                    AS unit,
    '6s'                                                                   AS period,
    count(used_share_space)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_share_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_share_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                            AS relation,
    'used_share_space_trend'                                                     AS measure,
    'int'                                                                        AS kind,
    '%'                                                                          AS unit,
    '6s'                                                                         AS period,
    count(used_share_space_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_share_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_share_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'used_backup_space'                                                     AS measure,
    'int'                                                                   AS kind,
    '%'                                                                     AS unit,
    '6s'                                                                    AS period,
    count(used_backup_space)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_backup_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_backup_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                             AS relation,
    'used_backup_space_trend'                                                     AS measure,
    'int'                                                                         AS kind,
    '%'                                                                           AS unit,
    '6s'                                                                          AS period,
    count(used_backup_space_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_backup_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_backup_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                     AS relation,
    'used_swap_space'                                                     AS measure,
    'int'                                                                 AS kind,
    '%'                                                                   AS unit,
    '6s'                                                                  AS period,
    count(used_swap_space)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_swap_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_swap_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                           AS relation,
    'used_swap_space_trend'                                                     AS measure,
    'int'                                                                       AS kind,
    '%'                                                                         AS unit,
    '6s'                                                                        AS period,
    count(used_swap_space_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_swap_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_swap_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                   AS relation,
    'used_disk_ops'                                                     AS measure,
    'int'                                                               AS kind,
    '%'                                                                 AS unit,
    '6s'                                                                AS period,
    count(used_disk_ops)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                         AS relation,
    'used_disk_ops_trend'                                                     AS measure,
    'int'                                                                     AS kind,
    '%'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(used_disk_ops_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                  AS relation,
    'used_network'                                                     AS measure,
    'int'                                                              AS kind,
    '%'                                                                AS unit,
    '6s'                                                               AS period,
    count(used_network)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                        AS relation,
    'used_network_trend'                                                     AS measure,
    'int'                                                                    AS kind,
    '%'                                                                      AS unit,
    '6s'                                                                     AS period,
    count(used_network_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                 AS relation,
    'temperature'                                                     AS measure,
    'float'                                                           AS kind,
    '°C'                                                              AS unit,
    '6s'                                                              AS period,
    count(temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'temperature_trend'                                                     AS measure,
    'float'                                                                 AS kind,
    '°C'                                                                    AS unit,
    '6s'                                                                    AS period,
    count(temperature_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE temperature_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/service'                                         AS relation,
    'status'                                                     AS measure,
    'bool'                                                       AS kind,
    '-'                                                          AS unit,
    '6s'                                                         AS period,
    count(status)                                                AS rows,
    CAST(min(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                               AS relation,
    'status_trend'                                                     AS measure,
    'bool'                                                             AS kind,
    '-'                                                                AS unit,
    '6s'                                                               AS period,
    count(status_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'backup_status'                                                     AS measure,
    'bool'                                                              AS kind,
    '-'                                                                 AS unit,
    '6s'                                                                AS period,
    count(backup_status)                                                AS rows,
    CAST(min(time) FILTER (WHERE backup_status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE backup_status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'backup_status_trend'                                                     AS measure,
    'bool'                                                                    AS kind,
    '-'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(backup_status_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE backup_status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE backup_status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'health_status'                                                     AS measure,
    'bool'                                                              AS kind,
    '-'                                                                 AS unit,
    '6s'                                                                AS period,
    count(health_status)                                                AS rows,
    CAST(min(time) FILTER (WHERE health_status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE health_status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'health_status_trend'                                                     AS measure,
    'bool'                                                                    AS kind,
    '-'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(health_status_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE health_status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE health_status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                    AS relation,
    'configured_status'                                                     AS measure,
    'bool'                                                                  AS kind,
    '-'                                                                     AS unit,
    '6s'                                                                    AS period,
    count(configured_status)                                                AS rows,
    CAST(min(time) FILTER (WHERE configured_status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE configured_status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                          AS relation,
    'configured_status_trend'                                                     AS measure,
    'bool'                                                                        AS kind,
    '-'                                                                           AS unit,
    '6s'                                                                          AS period,
    count(configured_status_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE configured_status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE configured_status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                 AS relation,
    'used_processor'                                                     AS measure,
    'int'                                                                AS kind,
    '%'                                                                  AS unit,
    '6s'                                                                 AS period,
    count(used_processor)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                       AS relation,
    'used_processor_trend'                                                     AS measure,
    'int'                                                                      AS kind,
    '%'                                                                        AS unit,
    '6s'                                                                       AS period,
    count(used_processor_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                              AS relation,
    'used_memory'                                                     AS measure,
    'int'                                                             AS kind,
    '%'                                                               AS unit,
    '6s'                                                              AS period,
    count(used_memory)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                    AS relation,
    'used_memory_trend'                                                     AS measure,
    'int'                                                                   AS kind,
    '%'                                                                     AS unit,
    '6s'                                                                    AS period,
    count(used_memory_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'used_disk_ops'                                                     AS measure,
    'int'                                                               AS kind,
    '%'                                                                 AS unit,
    '6s'                                                                AS period,
    count(used_disk_ops)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'used_disk_ops_trend'                                                     AS measure,
    'int'                                                                     AS kind,
    '%'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(used_disk_ops_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                               AS relation,
    'used_network'                                                     AS measure,
    'int'                                                              AS kind,
    '%'                                                                AS unit,
    '6s'                                                               AS period,
    count(used_network)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                     AS relation,
    'used_network_trend'                                                     AS measure,
    'int'                                                                    AS kind,
    '%'                                                                      AS unit,
    '6s'                                                                     AS period,
    count(used_network_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'restart_count'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '6s'                                                                AS period,
    count(restart_count)                                                AS rows,
    CAST(min(time) FILTER (WHERE restart_count IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE restart_count IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'restart_count_trend'                                                     AS measure,
    'float'                                                                   AS kind,
    '-'                                                                       AS unit,
    '6s'                                                                      AS period,
    count(restart_count_trend)                                                AS rows,
    CAST(min(time) FILTER (WHERE restart_count_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE restart_count_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
    AND column_name NOT IN (
        'allocated_memory', 'allocated_memory_trend', 'backup_status',
        'backup_status_trend', 'configured_status', 'configured_status_trend',
        'failed_backups', 'failed_backups_trend', 'failed_log_messages',
        'failed_log_messages_trend', 'failed_shares', 'failed_shares_trend',
        'health_status', 'health_status_trend', 'host', 'life_used_drives',
        'life_used_drives_trend', 'max_memory', 'module', 'name', 'restart_count',
        'restart_count_trend', 'running_time', 'service', 'services', 'services_max_memory',
        'spin_fan_speed_of_max', 'spin_fan_speed_of_max_trend', 'status', 'status_trend',
        'temperature', 'temperature_trend', 'time', 'up_time', 'used_backup_space',
        'used_backup_space_trend', 'used_disk_ops', 'used_disk_ops_trend', 'used_memory',
        'used_memory_trend', 'used_network', 'used_network_trend', 'used_processor',
        'used_processor_trend', 'used_share_space', 'used_share_space_trend',
        'used_swap_space', 'used_swap_space_trend', 'used_system_space',
        'used_system_space_trend', 'version', 'warn_temperature_of_max',
        'warn_temperature_of_max_trend'
    )
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'supervisor/host'          AS relation,
    'host*'                    AS dimension,
    host                       AS entity,
    CASE WHEN host IN (
        'macmini-mad', 'macmini-max', 'macmini-may', 'macmini-meg', 'raspbpi-jen',
        'raspbpi-jil'
    ) THEN 'yes' ELSE 'no' END AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
GROUP BY host, CASE WHEN host IN (
    'macmini-mad', 'macmini-max', 'macmini-may', 'macmini-meg', 'raspbpi-jen',
    'raspbpi-jil'
) THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'supervisor/service'       AS relation,
    'host/service*'            AS dimension,
    concat(host, '/', service) AS entity,
    CASE WHEN service IN (
        'cloudflare', 'grafana', 'homeassistant', 'influxdb', 'influxdb3', 'letsencrypt',
        'mariadb', 'mlflow', 'mlserver', 'network', 'nginx', 'openra', 'plex', 'postgres',
        'sabnzbd', 'sonarr', 'supervisor', 'tempstat', 'vernemq', 'weewx', 'wrangle',
        'zigbee2mqtt'
    ) THEN 'yes' ELSE 'no' END AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
GROUP BY concat(host, '/', service), CASE WHEN service IN (
    'cloudflare', 'grafana', 'homeassistant', 'influxdb', 'influxdb3', 'letsencrypt',
    'mariadb', 'mlflow', 'mlserver', 'network', 'nginx', 'openra', 'plex', 'postgres',
    'sabnzbd', 'sonarr', 'supervisor', 'tempstat', 'vernemq', 'weewx', 'wrangle',
    'zigbee2mqtt'
) THEN 'yes' ELSE 'no' END
ORDER BY rows DESC;
SCHEMA_SQL
}

printf '\nSchema describe [%s] against [%s]\n' "supervisor" "${INFLUXDB3_SERVICE_PROD}"
printf -- '\n-- %s\n\n' "describe"
describe_sql | SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${INFLUXDB3_SERVICE_PROD}" \
  query_sql
