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
    echo "       postgres verify assert production matches the declaration"
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
export PGTZ="${TZ:-UTC}"

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

verify_sql() {
  cat <<'SCHEMA_SQL'
--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    coalesce(d.relation, 'currency')                              AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('currency/rate', 'snapshot', '1d', '$'),
    ('currency/rate', 'delta', '1d', '%'),
    ('currency/rate', 'delta', '7d', '%'),
    ('currency/rate', 'delta', '30d', '%'),
    ('currency/rate', 'delta', '365d', '%')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM currency) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;

SELECT
    coalesce(d.relation, 'equity')                                AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('equity/ticker', 'market-volume-spot', '1d', '$'),
    ('equity/ticker', 'price-close', '1d', '$'),
    ('equity/ticker', 'price-close-base', '1d', '$'),
    ('equity/ticker', 'price-close-spot', '1d', '$'),
    ('equity/ticker', 'price-close-1d-change-percentage', '1d', '%'),
    ('equity/ticker', 'price-close-base-1d-change-percentage', '1d', '%'),
    ('equity/ticker', 'price-close-spot-1d-change-percentage', '1d', '%'),
    ('equity/ticker', 'price-close-30d-change-percentage', '30d', '%'),
    ('equity/ticker', 'price-close-base-30d-change-percentage', '30d', '%'),
    ('equity/ticker', 'price-close-spot-30d-change-percentage', '30d', '%'),
    ('equity/ticker', 'price-close-90d-change-percentage', '90d', '%'),
    ('equity/ticker', 'price-close-base-90d-change-percentage', '90d', '%'),
    ('equity/ticker', 'price-close-spot-90d-change-percentage', '90d', '%'),
    ('equity/ticker', 'price-close-365d-change-percentage', '365d', '%'),
    ('equity/ticker', 'price-close-base-365d-change-percentage', '365d', '%'),
    ('equity/ticker', 'price-close-spot-365d-change-percentage', '365d', '%')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM equity) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;

SELECT
    coalesce(d.relation, 'interest')                              AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('interest/rate', 'mean', '1mo', '%'),
    ('interest/rate', 'mean', '1y', '%'),
    ('interest/rate', 'mean', '5y', '%'),
    ('interest/rate', 'mean', '10y', '%'),
    ('interest/rate', 'mean', '20y', '%'),
    ('interest/rate', 'mean', '40y', '%')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM interest) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;
SCHEMA_SQL
}

printf '\nSchema verify [%s] against [%s]\n' "wrangle" "${POSTGRES_SERVICE_PROD}"
printf -- '\n-- %s\n\n' "verify"

FAULTS=0
while IFS= read -r STATEMENT; do
  [ -z "${STATEMENT}" ] && continue
  if ! RESULT="$(query "${STATEMENT}")"; then
    fail "${STATEMENT}" "${RESULT}"
    exit 1
  fi
  COUNT="$(printf '%s' "${RESULT}" | rows)"
  if [ "${COUNT}" != "0" ]; then
    FAULTS=$((FAULTS + COUNT))
    printf '%s\n' "${RESULT}" | table
    printf '\n'
  fi
done < <(verify_sql | statements)

if [ "${FAULTS}" != "0" ]; then
  printf '\nSchema verify [%s] found [%s] fault row(s)\n' "wrangle" "${FAULTS}" >&2
  exit 1
fi
printf '\nSchema verify [%s] found no drift\n' "wrangle"
