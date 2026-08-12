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

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

SCHEMA_ECHO=${SCHEMA_ECHO:-true}
SCHEMA_ACTION=${SCHEMA_ACTION:-Describe}
SCHEMA_TARGET=${SCHEMA_TARGET:-}
SCHEMA_LABEL=${SCHEMA_LABEL:-}

statements() {
  sed -e 's/--.*$//' | tr '\n' ' ' | tr ';' '\n' |
    sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
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

rows() {
  jq -s '(if length == 1 and (.[0] | type) == "array" then .[0] else . end) | length'
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
    'ethernet/port'            AS relation,
    'port*'                    AS dimension,
    5                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
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
    3                          AS measures,
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
    AND column_name NOT IN ('endpoint', 'expiry_days', 'module', 'time', 'validity_pct', 'verified')
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
    AND column_name NOT IN ('module', 'ok', 'plugin', 'score', 'time')
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
    AND column_name NOT IN ('latency_ms', 'module', 'ok', 'resolved', 'resolver', 'time')
UNION ALL
SELECT
    'ethernet/port'                                          AS relation,
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
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                                  AS relation,
    'speed_mbps'                                                     AS measure,
    'int'                                                            AS kind,
    'Mbps'                                                           AS unit,
    '15m'                                                            AS period,
    count(speed_mbps)                                                AS rows,
    CAST(min(time) FILTER (WHERE speed_mbps IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE speed_mbps IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                                   AS relation,
    'full_duplex'                                                     AS measure,
    'bool'                                                            AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(full_duplex)                                                AS rows,
    CAST(min(time) FILTER (WHERE full_duplex IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE full_duplex IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                                AS relation,
    'degraded'                                                     AS measure,
    'bool'                                                         AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(degraded)                                                AS rows,
    CAST(min(time) FILTER (WHERE degraded IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE degraded IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                              AS relation,
    'errors'                                                     AS measure,
    'int'                                                        AS kind,
    '-'                                                          AS unit,
    '15m'                                                        AS period,
    count(errors)                                                AS rows,
    CAST(min(time) FILTER (WHERE errors IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE errors IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
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
    AND column_name NOT IN ('degraded', 'errors', 'full_duplex', 'module', 'port', 'speed_mbps', 'time', 'up')
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
    AND column_name NOT IN ('jitter_ms', 'loss_pct', 'module', 'reachable', 'rtt_ms', 'target', 'time')
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
    AND column_name NOT IN ('console', 'fresh', 'module', 'quality_pct', 'time')
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
    AND column_name NOT IN ('accesspoint', 'clients', 'experience_pct', 'module', 'time', 'up')
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
UNION ALL
SELECT
    'zigbee/device'                                                   AS relation,
    'coordinator'                                                     AS measure,
    'bool'                                                            AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(coordinator)                                                AS rows,
    CAST(min(time) FILTER (WHERE coordinator IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE coordinator IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
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
    AND column_name NOT IN ('available', 'coordinator', 'device', 'lqi', 'module', 'time', 'weak')
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
    'ethernet/port'            AS relation,
    'port*'                    AS dimension,
    port                       AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
GROUP BY port
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
    'wireless/accesspoint'     AS relation,
    'accesspoint*'             AS dimension,
    accesspoint                AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
GROUP BY accesspoint
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
GROUP BY device
ORDER BY rows DESC;
SCHEMA_SQL
}

printf '\nSchema describe [%s] against [%s]\n' "network" "${INFLUXDB3_SERVICE_PROD}"
printf -- '\n-- %s\n\n' "describe"
describe_sql | SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${INFLUXDB3_SERVICE_PROD}" \
  query_sql
