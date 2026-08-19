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
  echo "Schema script [homeassistant] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE_NAME="${DATABASE_NAME:-${HOMEASSISTANT_DATABASE_NAME:-${INFLUXDB3_DATABASE_HOME:-}}}"
DATABASE_TOKEN="${DATABASE_TOKEN:-${HOMEASSISTANT_DATABASE_TOKEN:-${INFLUXDB3_TOKEN_ADMIN:-}}}"

for VARIABLE in DATABASE_NAME DATABASE_TOKEN; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [homeassistant] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
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

describe_sql() {
  cat <<'SCHEMA_SQL'
--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'automation'               AS relation,
    'entity_id*'               AS dimension,
    4                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor'            AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__battery'   AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__battery_charging' AS relation,
    'entity_id*'                      AS dimension,
    2                                 AS measures,
    '<on-change>'                     AS cadence,
    count(*)                          AS rows,
    CAST(min(time) AS VARCHAR)        AS oldest,
    CAST(max(time) AS VARCHAR)        AS newest
FROM binary_sensor__battery_charging
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__connectivity' AS relation,
    'entity_id*'                  AS dimension,
    2                             AS measures,
    '<on-change>'                 AS cadence,
    count(*)                      AS rows,
    CAST(min(time) AS VARCHAR)    AS oldest,
    CAST(max(time) AS VARCHAR)    AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__door'      AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__door
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__occupancy' AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__safety'    AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__safety
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                  AS relation,
    'entity_id*'               AS dimension,
    4                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'           AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                      AS relation,
    'entity_id*'               AS dimension,
    5                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                    AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'lock'                     AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM lock
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player'             AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'    AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__tv'         AS relation,
    'entity_id*'               AS dimension,
    3                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    6                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__atmospheric_pressure'   AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__battery'                AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__carbon_dioxide'         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__carbon_dioxide
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__current'                AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__current
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__energy'                 AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__enum'             AS relation,
    'entity_id*'               AS dimension,
    1                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__enum
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'               AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__pm25'                   AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__pm25
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__power'                  AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__precipitation'          AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__pressure'               AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__signal_strength'        AS relation,
    'entity_id/unit_of_measurement*' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__signal_strength
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__sound_pressure'         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__sound_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'            AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__timestamp'        AS relation,
    'entity_id*'               AS dimension,
    1                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__voltage'                AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__voltage
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__wind_speed'             AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                   AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
ORDER BY rows DESC;

-- measures
SELECT
    'automation'                                                         AS relation,
    'last_triggered'                                                     AS measure,
    'float'                                                              AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(last_triggered)                                                AS rows,
    CAST(min(time) FILTER (WHERE last_triggered IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE last_triggered IS NOT NULL) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'automation'                                                             AS relation,
    'last_triggered_str'                                                     AS measure,
    'str'                                                                    AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(last_triggered_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE last_triggered_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE last_triggered_str IS NOT NULL) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'automation'                                                AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'automation'                                                AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
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
    table_name = 'automation'
    AND column_name NOT IN (
        'entity_id', 'last_triggered', 'last_triggered_str', 'module', 'state', 'time',
        'value'
    )
UNION ALL
SELECT
    'binary_sensor'                                             AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor'                                             AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__battery'                                    AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__battery'                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__battery
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor__battery'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__battery_charging'                           AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__battery_charging
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__battery_charging'                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__battery_charging
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor__battery_charging'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__connectivity'                               AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__connectivity'                               AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor__connectivity'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__door'                                       AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__door
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__door'                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__door
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor__door'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__occupancy'                                  AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__occupancy'                                  AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor__occupancy'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__safety'                                     AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__safety
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__safety'                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__safety
WHERE
    module = 'homeassistant'
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
    table_name = 'binary_sensor__safety'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'climate'                                                                 AS relation,
    'current_temperature'                                                     AS measure,
    'float'                                                                   AS kind,
    '-'                                                                       AS unit,
    '<on-change>'                                                             AS period,
    count(current_temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE current_temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE current_temperature IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                                                             AS relation,
    'hvac_action_str'                                                     AS measure,
    'str'                                                                 AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(hvac_action_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE hvac_action_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE hvac_action_str IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                                                   AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                                                         AS relation,
    'temperature'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
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
    table_name = 'climate'
    AND column_name NOT IN (
        'current_temperature', 'entity_id', 'hvac_action_str', 'module', 'state',
        'temperature', 'time'
    )
UNION ALL
SELECT
    'device_tracker'                                            AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                            AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
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
    table_name = 'device_tracker'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'fan'                                                               AS relation,
    'direction_str'                                                     AS measure,
    'str'                                                               AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(direction_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE direction_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE direction_str IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                                                            AS relation,
    'percentage'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(percentage)                                                AS rows,
    CAST(min(time) FILTER (WHERE percentage IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE percentage IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                                                                AS relation,
    'percentage_str'                                                     AS measure,
    'str'                                                                AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(percentage_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE percentage_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE percentage_str IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                                                       AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
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
    table_name = 'fan'
    AND column_name NOT IN (
        'direction_str', 'entity_id', 'module', 'percentage', 'percentage_str', 'state',
        'time', 'value'
    )
UNION ALL
SELECT
    'light'                                                     AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
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
    table_name = 'light'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'lock'                                                      AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM lock
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'lock'                                                      AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM lock
WHERE
    module = 'homeassistant'
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
    table_name = 'lock'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'media_player'                                              AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM media_player
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player'                                              AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM media_player
WHERE
    module = 'homeassistant'
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
    table_name = 'media_player'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'media_player__speaker'                                     AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
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
    table_name = 'media_player__speaker'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'media_player__tv'                                                     AS relation,
    'sound_output_str'                                                     AS measure,
    'str'                                                                  AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(sound_output_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE sound_output_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE sound_output_str IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__tv'                                          AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__tv'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
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
    table_name = 'media_player__tv'
    AND column_name NOT IN ('entity_id', 'module', 'sound_output_str', 'state', 'time', 'value')
UNION ALL
SELECT
    'sensor'                                                         AS relation,
    'color_fill'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(color_fill)                                                AS rows,
    CAST(min(time) FILTER (WHERE color_fill IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE color_fill IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                             AS relation,
    'color_fill_str'                                                     AS measure,
    'str'                                                                AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(color_fill_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE color_fill_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE color_fill_str IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                         AS relation,
    'color_text'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(color_text)                                                AS rows,
    CAST(min(time) FILTER (WHERE color_text IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE color_text IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                             AS relation,
    'color_text_str'                                                     AS measure,
    'str'                                                                AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(color_text_str)                                                AS rows,
    CAST(min(time) FILTER (WHERE color_text_str IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE color_text_str IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                    AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor'
    AND column_name NOT IN (
        'color_fill', 'color_fill_str', 'color_text', 'color_text_str', 'entity_id',
        'module', 'state', 'time', 'unit_of_measurement', 'value'
    )
UNION ALL
SELECT
    'sensor__atmospheric_pressure'                              AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__atmospheric_pressure'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__battery'                                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__battery'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__carbon_dioxide'                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__carbon_dioxide
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__carbon_dioxide'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__current'                                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__current
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__current'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__energy'                                            AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__energy'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__enum'                                              AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__enum
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__enum'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time')
UNION ALL
SELECT
    'sensor__humidity'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__humidity'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__pm25'                                              AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__pm25
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__pm25'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__power'                                             AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__power'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__precipitation'                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__precipitation'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__pressure'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__pressure
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__pressure'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__signal_strength'                                   AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__signal_strength
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__signal_strength'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__sound_pressure'                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__sound_pressure
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__sound_pressure'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__temperature'                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__temperature'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__timestamp'                                         AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__timestamp'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time')
UNION ALL
SELECT
    'sensor__voltage'                                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__voltage
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__voltage'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__wind_speed'                                        AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
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
    table_name = 'sensor__wind_speed'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'switch'                                                    AS relation,
    'state'                                                     AS measure,
    'str'                                                       AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(state)                                                AS rows,
    CAST(min(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE state IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
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
    table_name = 'switch'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'automation'               AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor'            AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__battery'   AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__battery
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__battery_charging' AS relation,
    'entity_id*'                      AS dimension,
    entity_id                         AS entity,
    '-'                               AS declared,
    count(*)                          AS rows,
    CAST(min(time) AS VARCHAR)        AS oldest,
    CAST(max(time) AS VARCHAR)        AS newest
FROM binary_sensor__battery_charging
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__connectivity' AS relation,
    'entity_id*'                  AS dimension,
    entity_id                     AS entity,
    '-'                           AS declared,
    count(*)                      AS rows,
    CAST(min(time) AS VARCHAR)    AS oldest,
    CAST(max(time) AS VARCHAR)    AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__door'      AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__door
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__occupancy' AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__safety'    AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__safety
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'climate'                  AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'device_tracker'           AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'fan'                      AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'light'                    AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'lock'                     AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM lock
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'media_player'             AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'media_player__speaker'    AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'media_player__tv'         AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'sensor'                                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__atmospheric_pressure'              AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__battery'                           AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__carbon_dioxide'                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__carbon_dioxide
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__current'                           AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__current
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__energy'                            AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__enum'             AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__enum
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'sensor__humidity'                          AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__pm25'                              AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__pm25
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__power'                             AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__precipitation'                     AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__pressure'                          AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__pressure
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__signal_strength'                   AS relation,
    'entity_id/unit_of_measurement*'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__signal_strength
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__sound_pressure'                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__sound_pressure
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__temperature'                       AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__timestamp'        AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'sensor__voltage'                           AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__voltage
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__wind_speed'                        AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'switch'                   AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
GROUP BY entity_id
ORDER BY rows DESC;
SCHEMA_SQL
}

printf '\nSchema describe [%s] against [%s]\n' "homeassistant" "${INFLUXDB3_SERVICE_PROD}"
describe_sql | SCHEMA_ECHO=false query_sql
