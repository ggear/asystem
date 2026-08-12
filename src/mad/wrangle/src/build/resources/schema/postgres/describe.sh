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
    echo "       postgres describe print what production actually carries"
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
  echo "Schema script [wrangle] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE_USER="${DATABASE_USER:-${WRANGLE_DATABASE_USER:-${POSTGRES_USER_WRANGLE:-}}}"
DATABASE_NAME="${DATABASE_NAME:-${WRANGLE_DATABASE_NAME:-${POSTGRES_DATABASE_WRANGLE:-}}}"
DATABASE_PASSWORD="${DATABASE_PASSWORD:-${WRANGLE_DATABASE_PASSWORD:-${POSTGRES_KEY_WRANGLE:-}}}"

for VARIABLE in DATABASE_USER DATABASE_NAME DATABASE_PASSWORD; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [wrangle] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

PSQL=(psql -h "${POSTGRES_SERVICE_PROD}" -p "${POSTGRES_API_PORT}" -U "${DATABASE_USER}" -d "${DATABASE_NAME}")
export PGPASSWORD="${DATABASE_PASSWORD}"

query() {
  "${PSQL[@]}" -q -t -A -v ON_ERROR_STOP=1 -c "SELECT row_to_json(result) FROM ($1) AS result" 2>&1
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
    (if length == 1 and (.[0] | type) == "array" then .[0] else . end)
    | if length == 0 then "no rows" else
      (.[0] | keys_unsorted) as $columns
      | [range(0; $columns | length)] as $indexes
      | (map(. as $row | $columns
        | map(if $row[.] == null then "" else ($row[.] | tostring) end))) as $body
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
    'currency/rate'            AS relation,
    'entity*'                  AS dimension,
    5                          AS measures,
    '1d'                       AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type IN ('delta', 'snapshot')
UNION ALL
SELECT
    'equity/ticker'            AS relation,
    'entity*'                  AS dimension,
    16                         AS measures,
    '1d'                       AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type IN (
        'market-volume-spot', 'price-close', 'price-close-1d-change-percentage',
        'price-close-30d-change-percentage', 'price-close-365d-change-percentage',
        'price-close-90d-change-percentage', 'price-close-base',
        'price-close-base-1d-change-percentage', 'price-close-base-30d-change-percentage',
        'price-close-base-365d-change-percentage', 'price-close-base-90d-change-percentage',
        'price-close-spot', 'price-close-spot-1d-change-percentage',
        'price-close-spot-30d-change-percentage', 'price-close-spot-365d-change-percentage',
        'price-close-spot-90d-change-percentage'
    )
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'entity*'                  AS dimension,
    6                          AS measures,
    '1d'                       AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type IN ('mean')
ORDER BY rows DESC;

-- measures
SELECT
    'currency/rate'            AS relation,
    'snapshot'                 AS measure,
    'float'                    AS kind,
    '$'                        AS unit,
    '1d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type = 'snapshot'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'currency/rate'            AS relation,
    'delta'                    AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '1d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'currency/rate'            AS relation,
    'delta'                    AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '7d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '7d'
    AND unit = '%'
UNION ALL
SELECT
    'currency/rate'            AS relation,
    'delta'                    AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '30d'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'currency/rate'            AS relation,
    'delta'                    AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '365d'                     AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit                       AS unit,
    period                     AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type NOT IN ('delta', 'snapshot')
GROUP BY type, unit, period
UNION ALL
SELECT
    'equity/ticker'            AS relation,
    'market-volume-spot'       AS measure,
    'float'                    AS kind,
    '$'                        AS unit,
    '1d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type = 'market-volume-spot'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'            AS relation,
    'price-close'              AS measure,
    'float'                    AS kind,
    '$'                        AS unit,
    '1d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type = 'price-close'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'            AS relation,
    'price-close-base'         AS measure,
    'float'                    AS kind,
    '$'                        AS unit,
    '1d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type = 'price-close-base'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'            AS relation,
    'price-close-spot'         AS measure,
    'float'                    AS kind,
    '$'                        AS unit,
    '1d'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type = 'price-close-spot'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'                    AS relation,
    'price-close-1d-change-percentage' AS measure,
    'float'                            AS kind,
    '%'                                AS unit,
    '1d'                               AS period,
    count(*)                           AS rows,
    CAST(min(time) AS VARCHAR)         AS oldest,
    CAST(max(time) AS VARCHAR)         AS newest
FROM equity
WHERE
    type = 'price-close-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                         AS relation,
    'price-close-base-1d-change-percentage' AS measure,
    'float'                                 AS kind,
    '%'                                     AS unit,
    '1d'                                    AS period,
    count(*)                                AS rows,
    CAST(min(time) AS VARCHAR)              AS oldest,
    CAST(max(time) AS VARCHAR)              AS newest
FROM equity
WHERE
    type = 'price-close-base-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                         AS relation,
    'price-close-spot-1d-change-percentage' AS measure,
    'float'                                 AS kind,
    '%'                                     AS unit,
    '1d'                                    AS period,
    count(*)                                AS rows,
    CAST(min(time) AS VARCHAR)              AS oldest,
    CAST(max(time) AS VARCHAR)              AS newest
FROM equity
WHERE
    type = 'price-close-spot-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                     AS relation,
    'price-close-30d-change-percentage' AS measure,
    'float'                             AS kind,
    '%'                                 AS unit,
    '30d'                               AS period,
    count(*)                            AS rows,
    CAST(min(time) AS VARCHAR)          AS oldest,
    CAST(max(time) AS VARCHAR)          AS newest
FROM equity
WHERE
    type = 'price-close-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                          AS relation,
    'price-close-base-30d-change-percentage' AS measure,
    'float'                                  AS kind,
    '%'                                      AS unit,
    '30d'                                    AS period,
    count(*)                                 AS rows,
    CAST(min(time) AS VARCHAR)               AS oldest,
    CAST(max(time) AS VARCHAR)               AS newest
FROM equity
WHERE
    type = 'price-close-base-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                          AS relation,
    'price-close-spot-30d-change-percentage' AS measure,
    'float'                                  AS kind,
    '%'                                      AS unit,
    '30d'                                    AS period,
    count(*)                                 AS rows,
    CAST(min(time) AS VARCHAR)               AS oldest,
    CAST(max(time) AS VARCHAR)               AS newest
FROM equity
WHERE
    type = 'price-close-spot-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                     AS relation,
    'price-close-90d-change-percentage' AS measure,
    'float'                             AS kind,
    '%'                                 AS unit,
    '90d'                               AS period,
    count(*)                            AS rows,
    CAST(min(time) AS VARCHAR)          AS oldest,
    CAST(max(time) AS VARCHAR)          AS newest
FROM equity
WHERE
    type = 'price-close-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                          AS relation,
    'price-close-base-90d-change-percentage' AS measure,
    'float'                                  AS kind,
    '%'                                      AS unit,
    '90d'                                    AS period,
    count(*)                                 AS rows,
    CAST(min(time) AS VARCHAR)               AS oldest,
    CAST(max(time) AS VARCHAR)               AS newest
FROM equity
WHERE
    type = 'price-close-base-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                          AS relation,
    'price-close-spot-90d-change-percentage' AS measure,
    'float'                                  AS kind,
    '%'                                      AS unit,
    '90d'                                    AS period,
    count(*)                                 AS rows,
    CAST(min(time) AS VARCHAR)               AS oldest,
    CAST(max(time) AS VARCHAR)               AS newest
FROM equity
WHERE
    type = 'price-close-spot-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                      AS relation,
    'price-close-365d-change-percentage' AS measure,
    'float'                              AS kind,
    '%'                                  AS unit,
    '365d'                               AS period,
    count(*)                             AS rows,
    CAST(min(time) AS VARCHAR)           AS oldest,
    CAST(max(time) AS VARCHAR)           AS newest
FROM equity
WHERE
    type = 'price-close-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                           AS relation,
    'price-close-base-365d-change-percentage' AS measure,
    'float'                                   AS kind,
    '%'                                       AS unit,
    '365d'                                    AS period,
    count(*)                                  AS rows,
    CAST(min(time) AS VARCHAR)                AS oldest,
    CAST(max(time) AS VARCHAR)                AS newest
FROM equity
WHERE
    type = 'price-close-base-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                           AS relation,
    'price-close-spot-365d-change-percentage' AS measure,
    'float'                                   AS kind,
    '%'                                       AS unit,
    '365d'                                    AS period,
    count(*)                                  AS rows,
    CAST(min(time) AS VARCHAR)                AS oldest,
    CAST(max(time) AS VARCHAR)                AS newest
FROM equity
WHERE
    type = 'price-close-spot-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit                       AS unit,
    period                     AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type NOT IN (
        'market-volume-spot', 'price-close', 'price-close-1d-change-percentage',
        'price-close-30d-change-percentage', 'price-close-365d-change-percentage',
        'price-close-90d-change-percentage', 'price-close-base',
        'price-close-base-1d-change-percentage', 'price-close-base-30d-change-percentage',
        'price-close-base-365d-change-percentage', 'price-close-base-90d-change-percentage',
        'price-close-spot', 'price-close-spot-1d-change-percentage',
        'price-close-spot-30d-change-percentage', 'price-close-spot-365d-change-percentage',
        'price-close-spot-90d-change-percentage'
    )
GROUP BY type, unit, period
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'mean'                     AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '1mo'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '1mo'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'mean'                     AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '1y'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '1y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'mean'                     AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '5y'                       AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '5y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'mean'                     AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '10y'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '10y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'mean'                     AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '20y'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '20y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'            AS relation,
    'mean'                     AS measure,
    'float'                    AS kind,
    '%'                        AS unit,
    '40y'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '40y'
    AND unit = '%'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit                       AS unit,
    period                     AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type NOT IN ('mean')
GROUP BY type, unit, period
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'currency/rate'                                                                AS relation,
    'entity*'                                                                      AS dimension,
    entity                                                                         AS entity,
    CASE WHEN entity IN ('AUD/USD', 'AUD/GBP', 'AUD/SGD') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                       AS rows,
    CAST(min(time) AS VARCHAR)                                                     AS oldest,
    CAST(max(time) AS VARCHAR)                                                     AS newest
FROM currency
WHERE
    type IN ('delta', 'snapshot')
GROUP BY entity, CASE WHEN entity IN ('AUD/USD', 'AUD/GBP', 'AUD/SGD') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'equity/ticker'            AS relation,
    'entity*'                  AS dimension,
    entity                     AS entity,
    CASE WHEN entity IN (
        'ACDC', 'AORD', 'ATOI', 'AXJO', 'BANK', 'CLNE', 'EMKT', 'ERTH', 'GAME', 'GOLD',
        'IAF', 'MCK', 'MUK', 'MUS', 'MVW', 'NDQ', 'QSML', 'SIG', 'URNM', 'VAE', 'VAS',
        'VDHG', 'VGE', 'VGS', 'VHY', 'WDS'
    ) THEN 'yes' ELSE 'no' END AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type IN (
        'market-volume-spot', 'price-close', 'price-close-1d-change-percentage',
        'price-close-30d-change-percentage', 'price-close-365d-change-percentage',
        'price-close-90d-change-percentage', 'price-close-base',
        'price-close-base-1d-change-percentage', 'price-close-base-30d-change-percentage',
        'price-close-base-365d-change-percentage', 'price-close-base-90d-change-percentage',
        'price-close-spot', 'price-close-spot-1d-change-percentage',
        'price-close-spot-30d-change-percentage', 'price-close-spot-365d-change-percentage',
        'price-close-spot-90d-change-percentage'
    )
GROUP BY entity, CASE WHEN entity IN (
    'ACDC', 'AORD', 'ATOI', 'AXJO', 'BANK', 'CLNE', 'EMKT', 'ERTH', 'GAME', 'GOLD',
    'IAF', 'MCK', 'MUK', 'MUS', 'MVW', 'NDQ', 'QSML', 'SIG', 'URNM', 'VAE', 'VAS',
    'VDHG', 'VGE', 'VGS', 'VHY', 'WDS'
) THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'interest/rate'                                                           AS relation,
    'entity*'                                                                 AS dimension,
    entity                                                                    AS entity,
    CASE WHEN entity IN ('Bank', 'Inflation', 'Net') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                  AS rows,
    CAST(min(time) AS VARCHAR)                                                AS oldest,
    CAST(max(time) AS VARCHAR)                                                AS newest
FROM interest
WHERE
    type IN ('mean')
GROUP BY entity, CASE WHEN entity IN ('Bank', 'Inflation', 'Net') THEN 'yes' ELSE 'no' END
ORDER BY rows DESC;
SCHEMA_SQL
}

printf '\nSchema describe [%s] against [%s]\n' "wrangle" "${POSTGRES_SERVICE_PROD}"
printf -- '\n-- %s\n\n' "describe"
describe_sql | SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${POSTGRES_SERVICE_PROD}" \
  query_sql
