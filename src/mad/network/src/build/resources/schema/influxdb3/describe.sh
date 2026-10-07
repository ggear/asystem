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

describe_sql() {
  cat <<'SCHEMA_SQL'
--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'certificate/endpoint'     AS relation,
    'endpoint*'                AS dimension,
    3                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
UNION ALL
SELECT
    'diagnosis/plugin'         AS relation,
    'plugin*'                  AS dimension,
    2                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
UNION ALL
SELECT
    'domain/resolver'          AS relation,
    'resolver*'                AS dimension,
    3                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
UNION ALL
SELECT
    'ethernet/powered'         AS relation,
    'powered*'                 AS dimension,
    1                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND powered IS NOT NULL
    AND switch IS NULL
UNION ALL
SELECT
    'ethernet/switch'          AS relation,
    'switch*'                  AS dimension,
    12                         AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'internet/target'          AS relation,
    'target*'                  AS dimension,
    4                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'weewx/console'            AS relation,
    'console*'                 AS dimension,
    2                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'     AS relation,
    'accesspoint*'             AS dimension,
    9                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'zigbee/device'            AS relation,
    'device*'                  AS dimension,
    4                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
UNION ALL
SELECT
    'zigbee/experience'        AS relation,
    'experience*'              AS dimension,
    1                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND experience IS NOT NULL
    AND device IS NULL
ORDER BY rows DESC;

-- measures
SELECT
    'certificate/endpoint'                                         AS relation,
    'verified'                                                     AS measure,
    'bool'                                                         AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(verified)                                                AS rows,
    CAST(min(time) FILTER (WHERE verified IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE verified IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
UNION ALL
SELECT
    'certificate/endpoint'                                            AS relation,
    'expiry_days'                                                     AS measure,
    'float'                                                           AS kind,
    'd'                                                               AS unit,
    '15m'                                                             AS period,
    count(expiry_days)                                                AS rows,
    CAST(min(time) FILTER (WHERE expiry_days IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE expiry_days IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
UNION ALL
SELECT
    'certificate/endpoint'                                             AS relation,
    'validity_pct'                                                     AS measure,
    'float'                                                            AS kind,
    '%'                                                                AS unit,
    '15m'                                                              AS period,
    count(validity_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE validity_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE validity_pct IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
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
    table_name = 'certificate'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'endpoint',
        'errors', 'errors_trend', 'expiry_days', 'full_duplex', 'full_duplex_trend',
        'module', 'port', 'port_trend', 'speed_mbps', 'speed_mbps_trend', 'time',
        'validity_pct', 'verified'
    )
UNION ALL
SELECT
    'diagnosis/plugin'                                       AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
UNION ALL
SELECT
    'diagnosis/plugin'                                          AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
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
    table_name = 'diagnosis'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'errors',
        'errors_trend', 'full_duplex', 'full_duplex_trend', 'module', 'ok', 'plugin',
        'port', 'port_trend', 'score', 'speed_mbps', 'speed_mbps_trend', 'time'
    )
UNION ALL
SELECT
    'domain/resolver'                                        AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
UNION ALL
SELECT
    'domain/resolver'                                              AS relation,
    'resolved'                                                     AS measure,
    'bool'                                                         AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(resolved)                                                AS rows,
    CAST(min(time) FILTER (WHERE resolved IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE resolved IS NOT NULL) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
UNION ALL
SELECT
    'domain/resolver'                                                AS relation,
    'latency_ms'                                                     AS measure,
    'float'                                                          AS kind,
    'ms'                                                             AS unit,
    '15m'                                                            AS period,
    count(latency_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE latency_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latency_ms IS NOT NULL) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
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
    table_name = 'domain'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'errors',
        'errors_trend', 'full_duplex', 'full_duplex_trend', 'latency_ms', 'module', 'ok',
        'port', 'port_trend', 'resolved', 'resolver', 'speed_mbps', 'speed_mbps_trend',
        'time'
    )
UNION ALL
SELECT
    'ethernet/powered'                                            AS relation,
    'power_w'                                                     AS measure,
    'float'                                                       AS kind,
    'W'                                                           AS unit,
    '15m'                                                         AS period,
    count(power_w)                                                AS rows,
    CAST(min(time) FILTER (WHERE power_w IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE power_w IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND powered IS NOT NULL
    AND switch IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                        AS relation,
    'up'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(up)                                                AS rows,
    CAST(min(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                               AS relation,
    'restarted'                                                     AS measure,
    'bool'                                                          AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(restarted)                                                AS rows,
    CAST(min(time) FILTER (WHERE restarted IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE restarted IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                                 AS relation,
    'overheating'                                                     AS measure,
    'bool'                                                            AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(overheating)                                                AS rows,
    CAST(min(time) FILTER (WHERE overheating IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE overheating IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                                    AS relation,
    'experience_pct'                                                     AS measure,
    'float'                                                              AS kind,
    '%'                                                                  AS unit,
    '15m'                                                                AS period,
    count(experience_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                                     AS relation,
    'throughput_mbps'                                                     AS measure,
    'float'                                                               AS kind,
    'Mbps'                                                                AS unit,
    '15m'                                                                 AS period,
    count(throughput_mbps)                                                AS rows,
    CAST(min(time) FILTER (WHERE throughput_mbps IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE throughput_mbps IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                                 AS relation,
    'network_pct'                                                     AS measure,
    'float'                                                           AS kind,
    '%'                                                               AS unit,
    '15m'                                                             AS period,
    count(network_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE network_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE network_pct IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                             AS relation,
    'clients'                                                     AS measure,
    'int'                                                         AS kind,
    '-'                                                           AS unit,
    '15m'                                                         AS period,
    count(clients)                                                AS rows,
    CAST(min(time) FILTER (WHERE clients IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE clients IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                             AS relation,
    'cpu_pct'                                                     AS measure,
    'float'                                                       AS kind,
    '%'                                                           AS unit,
    '15m'                                                         AS period,
    count(cpu_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE cpu_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE cpu_pct IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                                AS relation,
    'memory_pct'                                                     AS measure,
    'float'                                                          AS kind,
    '%'                                                              AS unit,
    '15m'                                                            AS period,
    count(memory_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE memory_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE memory_pct IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                                 AS relation,
    'temperature'                                                     AS measure,
    'float'                                                           AS kind,
    '°C'                                                              AS unit,
    '15m'                                                             AS period,
    count(temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                           AS relation,
    'poe_w'                                                     AS measure,
    'float'                                                     AS kind,
    'W'                                                         AS unit,
    '15m'                                                       AS period,
    count(poe_w)                                                AS rows,
    CAST(min(time) FILTER (WHERE poe_w IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE poe_w IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
UNION ALL
SELECT
    'ethernet/switch'                                             AS relation,
    'poe_pct'                                                     AS measure,
    'float'                                                       AS kind,
    '%'                                                           AS unit,
    '15m'                                                         AS period,
    count(poe_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE poe_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE poe_pct IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
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
    table_name = 'ethernet'
    AND column_name NOT IN (
        'clients', 'coordinator', 'coordinator_trend', 'cpu_pct', 'degraded',
        'degraded_trend', 'errors', 'errors_trend', 'experience_pct', 'full_duplex',
        'full_duplex_trend', 'memory_pct', 'module', 'network_pct', 'overheating',
        'poe_pct', 'poe_w', 'port', 'port_trend', 'power_w', 'powered', 'restarted',
        'speed_mbps', 'speed_mbps_trend', 'switch', 'temperature', 'throughput_mbps',
        'time', 'up'
    )
UNION ALL
SELECT
    'internet/target'                                               AS relation,
    'reachable'                                                     AS measure,
    'bool'                                                          AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(reachable)                                                AS rows,
    CAST(min(time) FILTER (WHERE reachable IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE reachable IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'internet/target'                                              AS relation,
    'loss_pct'                                                     AS measure,
    'float'                                                        AS kind,
    '%'                                                            AS unit,
    '15m'                                                          AS period,
    count(loss_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE loss_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE loss_pct IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'internet/target'                                            AS relation,
    'rtt_ms'                                                     AS measure,
    'float'                                                      AS kind,
    'ms'                                                         AS unit,
    '15m'                                                        AS period,
    count(rtt_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE rtt_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE rtt_ms IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'internet/target'                                               AS relation,
    'jitter_ms'                                                     AS measure,
    'float'                                                         AS kind,
    'ms'                                                            AS unit,
    '15m'                                                           AS period,
    count(jitter_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE jitter_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE jitter_ms IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
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
    table_name = 'internet'
    AND column_name NOT IN (
        'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend', 'errors',
        'errors_trend', 'full_duplex', 'full_duplex_trend', 'jitter_ms', 'loss_pct',
        'module', 'port', 'port_trend', 'reachable', 'rtt_ms', 'speed_mbps',
        'speed_mbps_trend', 'target', 'time'
    )
UNION ALL
SELECT
    'weewx/console'                                             AS relation,
    'fresh'                                                     AS measure,
    'bool'                                                      AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(fresh)                                                AS rows,
    CAST(min(time) FILTER (WHERE fresh IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE fresh IS NOT NULL) AS VARCHAR) AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
UNION ALL
SELECT
    'weewx/console'                                                   AS relation,
    'quality_pct'                                                     AS measure,
    'float'                                                           AS kind,
    '%'                                                               AS unit,
    '15m'                                                             AS period,
    count(quality_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE quality_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE quality_pct IS NOT NULL) AS VARCHAR) AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
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
    table_name = 'weewx'
    AND column_name NOT IN (
        'console', 'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend',
        'errors', 'errors_trend', 'fresh', 'full_duplex', 'full_duplex_trend', 'module',
        'port', 'port_trend', 'quality_pct', 'speed_mbps', 'speed_mbps_trend', 'time'
    )
UNION ALL
SELECT
    'wireless/accesspoint'                                   AS relation,
    'up'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(up)                                                AS rows,
    CAST(min(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                          AS relation,
    'restarted'                                                     AS measure,
    'bool'                                                          AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(restarted)                                                AS rows,
    CAST(min(time) FILTER (WHERE restarted IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE restarted IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                            AS relation,
    'overheating'                                                     AS measure,
    'bool'                                                            AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(overheating)                                                AS rows,
    CAST(min(time) FILTER (WHERE overheating IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE overheating IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                               AS relation,
    'experience_pct'                                                     AS measure,
    'float'                                                              AS kind,
    '%'                                                                  AS unit,
    '15m'                                                                AS period,
    count(experience_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                                AS relation,
    'throughput_mbps'                                                     AS measure,
    'float'                                                               AS kind,
    'Mbps'                                                                AS unit,
    '15m'                                                                 AS period,
    count(throughput_mbps)                                                AS rows,
    CAST(min(time) FILTER (WHERE throughput_mbps IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE throughput_mbps IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                            AS relation,
    'network_pct'                                                     AS measure,
    'float'                                                           AS kind,
    '%'                                                               AS unit,
    '15m'                                                             AS period,
    count(network_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE network_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE network_pct IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                        AS relation,
    'clients'                                                     AS measure,
    'int'                                                         AS kind,
    '-'                                                           AS unit,
    '15m'                                                         AS period,
    count(clients)                                                AS rows,
    CAST(min(time) FILTER (WHERE clients IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE clients IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                        AS relation,
    'cpu_pct'                                                     AS measure,
    'float'                                                       AS kind,
    '%'                                                           AS unit,
    '15m'                                                         AS period,
    count(cpu_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE cpu_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE cpu_pct IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                           AS relation,
    'memory_pct'                                                     AS measure,
    'float'                                                          AS kind,
    '%'                                                              AS unit,
    '15m'                                                            AS period,
    count(memory_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE memory_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE memory_pct IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
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
    table_name = 'wireless'
    AND column_name NOT IN (
        'accesspoint', 'clients', 'coordinator', 'coordinator_trend', 'cpu_pct', 'degraded',
        'degraded_trend', 'errors', 'errors_trend', 'experience_pct', 'full_duplex',
        'full_duplex_trend', 'memory_pct', 'module', 'network_pct', 'overheating', 'port',
        'port_trend', 'restarted', 'speed_mbps', 'speed_mbps_trend', 'throughput_mbps',
        'time', 'up'
    )
UNION ALL
SELECT
    'zigbee/device'                                                 AS relation,
    'available'                                                     AS measure,
    'bool'                                                          AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(available)                                                AS rows,
    CAST(min(time) FILTER (WHERE available IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE available IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
UNION ALL
SELECT
    'zigbee/device'                                           AS relation,
    'lqi'                                                     AS measure,
    'int'                                                     AS kind,
    '-'                                                       AS unit,
    '15m'                                                     AS period,
    count(lqi)                                                AS rows,
    CAST(min(time) FILTER (WHERE lqi IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE lqi IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
UNION ALL
SELECT
    'zigbee/device'                                            AS relation,
    'weak'                                                     AS measure,
    'bool'                                                     AS kind,
    '-'                                                        AS unit,
    '15m'                                                      AS period,
    count(weak)                                                AS rows,
    CAST(min(time) FILTER (WHERE weak IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE weak IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
UNION ALL
SELECT
    'zigbee/device'                                                   AS relation,
    'last_seen_s'                                                     AS measure,
    'int'                                                             AS kind,
    's'                                                               AS unit,
    '15m'                                                             AS period,
    count(last_seen_s)                                                AS rows,
    CAST(min(time) FILTER (WHERE last_seen_s IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE last_seen_s IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
UNION ALL
SELECT
    'zigbee/experience'                                                  AS relation,
    'experience_pct'                                                     AS measure,
    'float'                                                              AS kind,
    '%'                                                                  AS unit,
    '15m'                                                                AS period,
    count(experience_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND experience IS NOT NULL
    AND device IS NULL
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
    table_name = 'zigbee'
    AND column_name NOT IN (
        'available', 'coordinator', 'coordinator_trend', 'degraded', 'degraded_trend',
        'device', 'errors', 'errors_trend', 'experience', 'experience_pct', 'full_duplex',
        'full_duplex_trend', 'last_seen_s', 'lqi', 'module', 'port', 'port_trend',
        'speed_mbps', 'speed_mbps_trend', 'time', 'weak'
    )
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'certificate/endpoint'                                                        AS relation,
    'endpoint*'                                                                   AS dimension,
    endpoint                                                                      AS entity,
    CASE WHEN endpoint IN ('home.janeandgraham.com:443') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                      AS rows,
    CAST(min(time) AS VARCHAR)                                                    AS oldest,
    CAST(max(time) AS VARCHAR)                                                    AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
GROUP BY endpoint, CASE WHEN endpoint IN ('home.janeandgraham.com:443') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'diagnosis/plugin'                                                                                                            AS relation,
    'plugin*'                                                                                                                     AS dimension,
    plugin                                                                                                                        AS entity,
    CASE WHEN plugin IN ('certificate', 'domain', 'ethernet', 'internet', 'weewx', 'wireless', 'zigbee') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                                                      AS rows,
    CAST(min(time) AS VARCHAR)                                                                                                    AS oldest,
    CAST(max(time) AS VARCHAR)                                                                                                    AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
GROUP BY plugin, CASE WHEN plugin IN ('certificate', 'domain', 'ethernet', 'internet', 'weewx', 'wireless', 'zigbee') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'domain/resolver'                                                                                      AS relation,
    'resolver*'                                                                                            AS dimension,
    resolver                                                                                               AS entity,
    CASE WHEN resolver IN ('cloudflare', 'google', 'quad9', 'opendns', 'adguard') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                               AS rows,
    CAST(min(time) AS VARCHAR)                                                                             AS oldest,
    CAST(max(time) AS VARCHAR)                                                                             AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
GROUP BY resolver, CASE WHEN resolver IN ('cloudflare', 'google', 'quad9', 'opendns', 'adguard') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'ethernet/powered'         AS relation,
    'powered*'                 AS dimension,
    powered                    AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND powered IS NOT NULL
    AND switch IS NULL
GROUP BY powered
UNION ALL
SELECT
    'ethernet/switch'                                                           AS relation,
    'switch*'                                                                   AS dimension,
    switch                                                                      AS entity,
    CASE WHEN switch IN ('udm-dar', 'usw-dar-ceiling') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                    AS rows,
    CAST(min(time) AS VARCHAR)                                                  AS oldest,
    CAST(max(time) AS VARCHAR)                                                  AS newest
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
GROUP BY switch, CASE WHEN switch IN ('udm-dar', 'usw-dar-ceiling') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'internet/target'                                                                         AS relation,
    'target*'                                                                                 AS dimension,
    target                                                                                    AS entity,
    CASE WHEN target IN ('gateway', '1.1.1.1', '8.8.8.8', '9.9.9.9') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                  AS rows,
    CAST(min(time) AS VARCHAR)                                                                AS oldest,
    CAST(max(time) AS VARCHAR)                                                                AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
GROUP BY target, CASE WHEN target IN ('gateway', '1.1.1.1', '8.8.8.8', '9.9.9.9') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'weewx/console'                                                  AS relation,
    'console*'                                                       AS dimension,
    console                                                          AS entity,
    CASE WHEN console IN ('weatherstation') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                         AS rows,
    CAST(min(time) AS VARCHAR)                                       AS oldest,
    CAST(max(time) AS VARCHAR)                                       AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
GROUP BY console, CASE WHEN console IN ('weatherstation') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'wireless/accesspoint'                                                                                            AS relation,
    'accesspoint*'                                                                                                    AS dimension,
    accesspoint                                                                                                       AS entity,
    CASE WHEN accesspoint IN ('uap-dar-hallway', 'uap-dar-deck-north', 'uap-dar-deck-south') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                                          AS rows,
    CAST(min(time) AS VARCHAR)                                                                                        AS oldest,
    CAST(max(time) AS VARCHAR)                                                                                        AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
GROUP BY accesspoint, CASE WHEN accesspoint IN ('uap-dar-hallway', 'uap-dar-deck-north', 'uap-dar-deck-south') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'zigbee/device'            AS relation,
    'device*'                  AS dimension,
    device                     AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
GROUP BY device
UNION ALL
SELECT
    'zigbee/experience'                                                 AS relation,
    'experience*'                                                       AS dimension,
    experience                                                          AS entity,
    CASE WHEN experience IN ('router', 'mesh') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                            AS rows,
    CAST(min(time) AS VARCHAR)                                          AS oldest,
    CAST(max(time) AS VARCHAR)                                          AS newest
FROM zigbee
WHERE
    module = 'network'
    AND experience IS NOT NULL
    AND device IS NULL
GROUP BY experience, CASE WHEN experience IN ('router', 'mesh') THEN 'yes' ELSE 'no' END
ORDER BY rows DESC;
SCHEMA_SQL
}

printf '\nSchema describe [%s] against [%s]\n' "network" "${INFLUXDB3_SERVICE_PROD}"
describe_sql | SCHEMA_ECHO=false query_sql
