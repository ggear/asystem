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
    echo "       mariadb describe print what the instance actually holds"
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
  echo "Schema script [mariadb] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

DATABASE_USER="${DATABASE_USER:-${MARIADB_DATABASE_USER:-${MARIADB_USER:-}}}"
DATABASE_PASSWORD="${DATABASE_PASSWORD:-${MARIADB_DATABASE_PASSWORD:-${MARIADB_KEY:-}}}"

for VARIABLE in DATABASE_USER DATABASE_PASSWORD; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [mariadb] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

MARIADB=(mariadb -h "${MARIADB_SERVICE_PROD}" -P "${MARIADB_API_PORT}"
  -u "${DATABASE_USER}" "--password=${DATABASE_PASSWORD}" --batch --raw)

tabulated() {
  jq -R -s 'split("\n") | map(select(length > 0))
    | if length < 2 then [] else (.[0] | split("\t")) as $columns
      | .[1:] | map(split("\t") | [$columns, .] | transpose | map({(.[0]): .[1]}) | add) end'
}

query() {
  local output status diagnostics
  diagnostics="$(mktemp)"
  output="$("${MARIADB[@]}" -e "$1" 2>"${diagnostics}")"
  status=$?
  if [ "${status}" != 0 ]; then
    cat "${diagnostics}"
    rm -f "${diagnostics}"
    return 1
  fi
  rm -f "${diagnostics}"
  printf '%s' "${output}" | tabulated
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

printf '\nSchema describe [%s] against [%s]\n' "mariadb" "${MARIADB_SERVICE_PROD}"

if ! command -v mariadb >/dev/null 2>&1; then
  echo "Schema script [mariadb] could not find the [mariadb] client on the PATH, install it with [brew install mariadb]" >&2
  exit 1
fi

DATABASES="SELECT
    s.SCHEMA_NAME                                                     AS 'database',
    count(t.TABLE_NAME)                                               AS 'tables',
    round(coalesce(sum(t.DATA_LENGTH + t.INDEX_LENGTH), 0) / 1048576, 1) AS 'megaBytes'
  FROM information_schema.SCHEMATA s
  LEFT JOIN information_schema.TABLES t ON t.TABLE_SCHEMA = s.SCHEMA_NAME
  WHERE s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
  GROUP BY s.SCHEMA_NAME
  ORDER BY 3 DESC"

databases() {
  query "${DATABASES}" | slurp '.[].database' | sort
}

catalogued() {
  query "SELECT
      t.TABLE_NAME                                                    AS 'table',
      count(c.COLUMN_NAME)                                            AS 'columns',
      round(coalesce(max(t.DATA_LENGTH + t.INDEX_LENGTH), 0) / 1048576, 1) AS 'megaBytes',
      coalesce(max(CASE WHEN c.DATA_TYPE IN ('timestamp', 'datetime', 'date')
        THEN c.COLUMN_NAME END), '-')                                 AS 'stamp',
      coalesce(max(CASE WHEN c.COLUMN_NAME IN ('dateTime', 'time', 'timestamp')
        AND c.DATA_TYPE IN ('int', 'bigint') THEN c.COLUMN_NAME END), '-') AS 'epoch'
    FROM information_schema.TABLES t
    LEFT JOIN information_schema.COLUMNS c
      ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
    WHERE t.TABLE_SCHEMA = '${1}' AND t.TABLE_TYPE = 'BASE TABLE'
    GROUP BY t.TABLE_NAME
    ORDER BY t.TABLE_NAME"
}

section "databases"
query_one "${DATABASES}" || exit 1
printf '\n'

for DATABASE_NAME in $(databases); do
  section "tables ${DATABASE_NAME}"
  CATALOGUE="$(catalogued "${DATABASE_NAME}")" || { fail "${DATABASE_NAME}" "${CATALOGUE}"; exit 1; }
  STATEMENT=""
  while IFS=$'\t' read -r TABLE COLUMNS SIZE STAMP EPOCH; do
    [ -z "${TABLE}" ] && continue
    EARLIEST=""
    LATEST=""
    if [ "${STAMP}" != "-" ]; then
      EARLIEST="DATE_FORMAT(min(\`${STAMP}\`), '%Y-%m-%d %H:%i:%s')"
      LATEST="DATE_FORMAT(max(\`${STAMP}\`), '%Y-%m-%d %H:%i:%s')"
    fi
    if [ "${EPOCH}" != "-" ]; then
      [ -n "${EARLIEST}" ] && EARLIEST="${EARLIEST}, "
      [ -n "${LATEST}" ] && LATEST="${LATEST}, "
      EARLIEST="${EARLIEST}DATE_FORMAT(FROM_UNIXTIME(min(\`${EPOCH}\`)), '%Y-%m-%d %H:%i:%s')"
      LATEST="${LATEST}DATE_FORMAT(FROM_UNIXTIME(max(\`${EPOCH}\`)), '%Y-%m-%d %H:%i:%s')"
    fi
    if [ -n "${EARLIEST}" ]; then
      OLDEST="coalesce(${EARLIEST}, '-')"
      NEWEST="coalesce(${LATEST}, '-')"
    else
      OLDEST="'-'"
      NEWEST="'-'"
    fi
    [ -n "${STATEMENT}" ] && STATEMENT="${STATEMENT} UNION ALL "
    STATEMENT="${STATEMENT}SELECT '${TABLE}' AS 'table', '${DATABASE_NAME}' AS 'module',"
    STATEMENT="${STATEMENT} ${COLUMNS} AS 'columns', count(*) AS 'rows', ${SIZE} AS 'megaBytes',"
    STATEMENT="${STATEMENT} ${OLDEST} AS 'oldest', ${NEWEST} AS 'newest'"
    STATEMENT="${STATEMENT} FROM \`${DATABASE_NAME}\`.\`${TABLE}\`"
  done < <(printf '%s' "${CATALOGUE}" | jq -r '.[] | [.table, .columns, .megaBytes, .stamp, .epoch] | @tsv')
  if [ -z "${STATEMENT}" ]; then
    printf 'no rows\n\n'
    continue
  fi
  query_one "${STATEMENT} ORDER BY 4 DESC" || exit 1
  printf '\n'
done
