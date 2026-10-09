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
  echo "Schema script [network] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE_NAME="${DATABASE_NAME:-${NETWORK_DATABASE_NAME:-${INFLUXDB3_DATABASE_HOME:-}}}"
DATABASE_TOKEN="${DATABASE_TOKEN:-${NETWORK_DATABASE_TOKEN:-${INFLUXDB3_TOKEN_ADMIN:-}}}"

for VARIABLE in DATABASE_NAME DATABASE_TOKEN; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [network] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
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
    'certificate/endpoint' AS relation,
    'verified'             AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'verified') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'expiry_days'          AS measure,
    '15m'                  AS period,
    'd'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'expiry_days') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'validity_pct'         AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'validity_pct') = 0
UNION ALL
SELECT
    'certificate' AS relation,
    column_name   AS measure,
    '-'           AS period,
    '-'           AS unit,
    'undeclared'  AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'endpoint',
        'errors', 'errors_trend', 'expiry_days', 'full_duplex', 'full_duplex_trend',
        'module', 'port', 'port_trend', 'speed_mbps', 'speed_mbps_trend', 'time',
        'validity_pct', 'verified'
    )
ORDER BY fault, measure;

SELECT
    'diagnosis/plugin' AS relation,
    'ok'               AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'diagnosis'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'diagnosis/plugin' AS relation,
    'score'            AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'diagnosis'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'diagnosis'  AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'diagnosis'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'errors',
        'errors_trend', 'full_duplex', 'full_duplex_trend', 'module', 'ok', 'plugin',
        'port', 'port_trend', 'score', 'speed_mbps', 'speed_mbps_trend', 'time'
    )
ORDER BY fault, measure;

SELECT
    'domain/resolver' AS relation,
    'ok'              AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'domain/resolver' AS relation,
    'resolved'        AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'resolved') = 0
UNION ALL
SELECT
    'domain/resolver' AS relation,
    'latency_ms'      AS measure,
    '15m'             AS period,
    'ms'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'latency_ms') = 0
UNION ALL
SELECT
    'domain'     AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'errors',
        'errors_trend', 'full_duplex', 'full_duplex_trend', 'latency_ms', 'module', 'ok',
        'port', 'port_trend', 'resolved', 'resolver', 'speed_mbps', 'speed_mbps_trend',
        'time'
    )
ORDER BY fault, measure;

SELECT
    'ethernet/powered' AS relation,
    'power_w'          AS measure,
    '15m'              AS period,
    'W'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'power_w') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'up'              AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'up') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'restarted'       AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'restarted') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'overheating'     AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'overheating') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'experience_pct'  AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'experience_pct') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'throughput_mbps' AS measure,
    '15m'             AS period,
    'Mbps'            AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'throughput_mbps') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'network_pct'     AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'network_pct') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'clients'         AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'clients') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'cpu_pct'         AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'cpu_pct') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'memory_pct'      AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'memory_pct') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'temperature'     AS measure,
    '15m'             AS period,
    '°C'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'temperature') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'poe_w'           AS measure,
    '15m'             AS period,
    'W'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'poe_w') = 0
UNION ALL
SELECT
    'ethernet/switch' AS relation,
    'poe_pct'         AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'poe_pct') = 0
UNION ALL
SELECT
    'ethernet'   AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
    AND column_name NOT IN (
        'clients', 'coordinator', 'coordinator_trend', 'cpu_pct', 'degraded',
        'degraded_trend', 'errors', 'errors_trend', 'experience_pct', 'full_duplex',
        'full_duplex_trend', 'memory_pct', 'module', 'network_pct', 'overheating',
        'poe_pct', 'poe_w', 'port', 'port_trend', 'power_w', 'powered', 'restarted',
        'speed_mbps', 'speed_mbps_trend', 'switch', 'temperature', 'throughput_mbps',
        'time', 'up'
    )
ORDER BY fault, measure;

SELECT
    'internet/target' AS relation,
    'reachable'       AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'reachable') = 0
UNION ALL
SELECT
    'internet/target' AS relation,
    'loss_pct'        AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'loss_pct') = 0
UNION ALL
SELECT
    'internet/target' AS relation,
    'rtt_ms'          AS measure,
    '15m'             AS period,
    'ms'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'rtt_ms') = 0
UNION ALL
SELECT
    'internet/target' AS relation,
    'jitter_ms'       AS measure,
    '15m'             AS period,
    'ms'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'jitter_ms') = 0
UNION ALL
SELECT
    'internet'   AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'errors',
        'errors_trend', 'full_duplex', 'full_duplex_trend', 'jitter_ms', 'loss_pct',
        'module', 'port', 'port_trend', 'reachable', 'rtt_ms', 'speed_mbps',
        'speed_mbps_trend', 'target', 'time'
    )
ORDER BY fault, measure;

SELECT
    'weewx/console' AS relation,
    'fresh'         AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
HAVING count(*) FILTER (WHERE column_name = 'fresh') = 0
UNION ALL
SELECT
    'weewx/console' AS relation,
    'quality_pct'   AS measure,
    '15m'           AS period,
    '%'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
HAVING count(*) FILTER (WHERE column_name = 'quality_pct') = 0
UNION ALL
SELECT
    'weewx'      AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
    AND column_name NOT IN (
        'console', 'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend',
        'errors', 'errors_trend', 'fresh', 'full_duplex', 'full_duplex_trend', 'module',
        'port', 'port_trend', 'quality_pct', 'speed_mbps', 'speed_mbps_trend', 'time'
    )
ORDER BY fault, measure;

SELECT
    'wireless/accesspoint' AS relation,
    'up'                   AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'up') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'restarted'            AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'restarted') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'overheating'          AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'overheating') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'experience_pct'       AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'experience_pct') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'throughput_mbps'      AS measure,
    '15m'                  AS period,
    'Mbps'                 AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'throughput_mbps') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'network_pct'          AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'network_pct') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'clients'              AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'clients') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'cpu_pct'              AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'cpu_pct') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'memory_pct'           AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'memory_pct') = 0
UNION ALL
SELECT
    'wireless'   AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
    AND column_name NOT IN (
        'accesspoint', 'clients', 'coordinator', 'coordinator_trend', 'cpu_pct', 'degraded',
        'degraded_trend', 'errors', 'errors_trend', 'experience_pct', 'full_duplex',
        'full_duplex_trend', 'memory_pct', 'module', 'network_pct', 'overheating', 'port',
        'port_trend', 'restarted', 'speed_mbps', 'speed_mbps_trend', 'throughput_mbps',
        'time', 'up'
    )
ORDER BY fault, measure;

SELECT
    'zigbee/device' AS relation,
    'available'     AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'available') = 0
UNION ALL
SELECT
    'zigbee/device' AS relation,
    'lqi'           AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'lqi') = 0
UNION ALL
SELECT
    'zigbee/device' AS relation,
    'weak'          AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'weak') = 0
UNION ALL
SELECT
    'zigbee/device' AS relation,
    'last_seen_s'   AS measure,
    '15m'           AS period,
    's'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'last_seen_s') = 0
UNION ALL
SELECT
    'zigbee/experience' AS relation,
    'experience_pct'    AS measure,
    '15m'               AS period,
    '%'                 AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'experience_pct') = 0
UNION ALL
SELECT
    'zigbee/router' AS relation,
    'available'     AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'available') = 0
UNION ALL
SELECT
    'zigbee/router' AS relation,
    'lqi'           AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'lqi') = 0
UNION ALL
SELECT
    'zigbee'     AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
    AND column_name NOT IN (
        'available', 'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend',
        'device', 'errors', 'errors_trend', 'experience', 'experience_pct', 'full_duplex',
        'full_duplex_trend', 'last_seen_s', 'lqi', 'module', 'port', 'port_trend', 'router',
        'speed_mbps', 'speed_mbps_trend', 'time', 'weak'
    )
ORDER BY fault, measure;
SCHEMA_SQL
}

printf '\nSchema verify [%s] against [%s]\n' "network" "${INFLUXDB3_SERVICE_PROD}"
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
  printf '\nSchema verify [%s] found [%s] retired measure(s) still carried, see mutate.sh\n' "network" "${PENDING}" >&2
fi
if [ "${FAULTS}" != "0" ]; then
  printf '\nSchema verify [%s] found [%s] fault row(s)\n' "network" "${FAULTS}" >&2
  exit 1
fi
printf '\nSchema verify [%s] found no drift\n' "network"
