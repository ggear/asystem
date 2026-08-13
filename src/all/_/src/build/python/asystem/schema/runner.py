from asystem.schema.query import TEXT, banner

REPORT = r"""
fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}
"""

TABLE = r"""
table() {
  jq -sr '
    def title: split("_") | map(if length > 0 then (.[0:1] | ascii_upcase) + .[1:] else . end) | join(" ");
    def numeric: type == "number" or (type == "string" and test("^-?[0-9]+([.][0-9]+)?$"));
    def placeholder: . == "-" or . == "";
    def clip: if length > SCHEMA_TEXT_WIDTH then .[0:SCHEMA_TEXT_TRIM] + "..." else . end;
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
""".replace("SCHEMA_TEXT_WIDTH", str(TEXT)).replace("SCHEMA_TEXT_TRIM", str(TEXT - 3))

RUNNER = REPORT + TABLE + r"""
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
"""


def resolved(module_name, variables):
    lines = [""]
    for variable, fallbacks in variables:
        chain = "${{{}:-}}".format(fallbacks[-1])
        for fallback in reversed(fallbacks[:-1]):
            chain = "${{{}:-{}}}".format(fallback, chain)
        lines.append('{0}="${{{0}:-{1}}}"'.format(variable, chain))
    lines += [
        "",
        "for VARIABLE in {}; do".format(" ".join(variable for variable, _ in variables)),
        '  if [ -z "${!VARIABLE}" ]; then',
        '    echo "Schema script [{}] could not resolve [${{VARIABLE}}] from it or any fallback, '
        'declare it in the module env files" >&2'.format(module_name),
        "    exit 1",
        "  fi",
        "done",
        "",
    ]
    return "\n".join(lines)


def script(module_name, dialect, name, summary, connect, body):
    return """
#!/usr/bin/env bash
{}

set -uo pipefail

SCHEMA_VERBOSE=${{SCHEMA_VERBOSE:-false}}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    SCHEMA_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${{0}} [-v|--verbose] [-h|--help]"
    echo "       {} {} {}"
    exit 2
    ;;
  *)
    shift
    ;;
  esac
done

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODULE_DIR="${{ROOT_DIR}}"
while [ "${{MODULE_DIR}}" != "/" ] && [ ! -f "${{MODULE_DIR}}/.env" ]; do
  MODULE_DIR="$(dirname "${{MODULE_DIR}}")"
done

if [ ! -f "${{MODULE_DIR}}/.env" ]; then
  echo "Schema script [{}] could not find env file [.env] searching up from [${{ROOT_DIR}}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${{MODULE_DIR}}/.env"
set +a

if [ "${{SCHEMA_VERBOSE}}" == true ]; then
  set -x
fi

{}

{}
    """.format(banner(), dialect, name, summary, module_name, connect.strip(), body.strip()).strip() + "\n"


def describe_runner(module_name, dialect, target, connect, sql):
    return script(module_name, dialect, "describe", "print what production actually carries", connect, """
describe_sql() {{
  cat <<'SCHEMA_SQL'
{sql}
SCHEMA_SQL
}}

printf '\\nSchema describe [%s] against [%s]\\n' "{module}" "${{{target}}}"
printf -- '\\n-- %s\\n\\n' "describe"
describe_sql | SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${{{target}}}" \\
  query_sql
""".format(target=target, module=module_name, sql=sql.strip()))


def query_runner(module_name, dialect, target, connect):
    return script(module_name, dialect, "query", "run the generated query for every declared relation", connect, """
printf '\\nSchema query [%s] against [%s]\\n\\n' "{module}" "${{{target}}}"
FAULTS=0
for SQL_FILE in "${{ROOT_DIR}}"/query/*.sql; do
  SCHEMA_LABEL="$(basename "${{SQL_FILE}}")"
  query_sql < "${{SQL_FILE}}" || FAULTS=$((FAULTS + 1))
done
[ "${{FAULTS}}" = 0 ]
""".format(target=target, module=module_name))


def verify_runner(module_name, dialect, target, connect, sql):
    return script(module_name, dialect, "verify", "assert production matches the declaration", connect, """
verify_sql() {{
  cat <<'SCHEMA_SQL'
{sql}
SCHEMA_SQL
}}

printf '\\nSchema verify [%s] against [%s]\\n' "{module}" "${{{target}}}"
printf -- '\\n-- %s\\n\\n' "verify"

FAULTS=0
while IFS= read -r STATEMENT; do
  [ -z "${{STATEMENT}}" ] && continue
  if ! RESULT="$(query "${{STATEMENT}}")"; then
    fail "${{STATEMENT}}" "${{RESULT}}"
    exit 1
  fi
  COUNT="$(printf '%s' "${{RESULT}}" | rows)"
  if [ "${{COUNT}}" != "0" ]; then
    FAULTS=$((FAULTS + COUNT))
    printf '%s\\n' "${{RESULT}}" | table
    printf '\\n'
  fi
done < <(verify_sql | statements)

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema verify [%s] found [%s] fault row(s)\\n' "{module}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema verify [%s] found no drift\\n' "{module}"
""".format(target=target, module=module_name, sql=sql.strip()))
