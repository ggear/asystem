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
    echo "       vernemq query print the retained payload of every declared topic"
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
  echo "Schema script [tempstat] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

BROKER_SERVICE="${BROKER_SERVICE:-${TEMPSTAT_BROKER_SERVICE:-${VERNEMQ_SERVICE_PROD:-}}}"
BROKER_PORT="${BROKER_PORT:-${TEMPSTAT_BROKER_PORT:-${VERNEMQ_API_PORT:-}}}"

for VARIABLE in BROKER_SERVICE BROKER_PORT; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [tempstat] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

table() {
  jq -sr --argjson clip 0 '
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

BROKER_ARGS=(-h "${BROKER_SERVICE}" -p "${BROKER_PORT}")

topics() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%r %t' -t "$1" -W 5 2>/dev/null | sed -n 's/^1 //p' | grep -E "${2:-.}" | sort -u || true
}

payload() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%r\n%p' -t "$1" -C 1 -W 2 2>/dev/null | awk 'NR==1{if($0!="1") exit} NR>1' || true
}

declared() {
  find "${ROOT_DIR}/model" -type f -name 'payload' -print0 2>/dev/null |
    while IFS= read -r -d '' LEAF; do
      TOPIC="${LEAF#"${ROOT_DIR}"/model/}"
      printf '%s\n' "${TOPIC%/payload}"
    done | sort -u
}

listed() {
  jq -R '{topic: .}' | table
}

faulted() {
  jq -nc --arg topic "$1" --arg fault "$2" '{topic: $topic, fault: $fault}'
}

printf '\nSchema query [%s] against [%s]\n' "tempstat" "${BROKER_SERVICE}"
while IFS= read -r TOPIC; do
  printf -- '\n-- %s\n\n' "${TOPIC}"
  payload "${TOPIC}"
  printf '\n'
done < <(declared)
