from asystem.schema.runner import RUNNER, instance_runner, resolved

DIALECT = "mariadb"
TARGET = "MARIADB_SERVICE_PROD"

CONNECT = """
MARIADB=(mariadb -h "${MARIADB_SERVICE_PROD}" -P "${MARIADB_API_PORT}"
  -u "${DATABASE_USER}" "--password=${DATABASE_PASSWORD}" --batch --raw)

tabulated() {
  jq -R -s 'split("\\n") | map(select(length > 0))
    | if length < 2 then [] else (.[0] | split("\\t")) as $columns
      | .[1:] | map(split("\\t") | [$columns, .] | transpose | map({(.[0]): .[1]}) | add) end'
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
""" + RUNNER

INSTANCE = """
if ! command -v mariadb >/dev/null 2>&1; then
  echo "Schema script [SCHEMA_MODULE] could not find the [mariadb] client on the PATH, install it with [brew install mariadb]" >&2
  exit 1
fi

DATABASES="SELECT
    s.SCHEMA_NAME                                                     AS 'database',
    s.DEFAULT_CHARACTER_SET_NAME                                      AS 'charset',
    count(t.TABLE_NAME)                                               AS 'tables',
    coalesce(sum(t.DATA_LENGTH + t.INDEX_LENGTH), 0)                  AS 'bytes'
  FROM information_schema.SCHEMATA s
  LEFT JOIN information_schema.TABLES t ON t.TABLE_SCHEMA = s.SCHEMA_NAME
  WHERE s.SCHEMA_NAME NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
  GROUP BY s.SCHEMA_NAME, s.DEFAULT_CHARACTER_SET_NAME
  ORDER BY 4 DESC"

USERS="SELECT
    User                                                              AS 'user',
    Host                                                              AS 'host'
  FROM mysql.user ORDER BY User, Host"

databases() {
  query "${DATABASES}" | slurp '.[].database' | sort
}

section "databases"
query_one "${DATABASES}" || exit 1
printf '\\n'

section "users"
query_one "${USERS}" || exit 1
printf '\\n'

for DATABASE_NAME in $(databases); do
  section "tables ${DATABASE_NAME}"
  query_one "SELECT
      TABLE_NAME                                                      AS 'table',
      ENGINE                                                          AS 'engine',
      coalesce(TABLE_ROWS, 0)                                         AS 'rows',
      coalesce(DATA_LENGTH + INDEX_LENGTH, 0)                         AS 'bytes',
      coalesce(CAST(CREATE_TIME AS CHAR), '-')                        AS 'created',
      coalesce(CAST(UPDATE_TIME AS CHAR), '-')                        AS 'updated'
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = '${DATABASE_NAME}'
    ORDER BY 4 DESC" || exit 1
  printf '\\n'
done
"""


def instance(module_name, zone=""):
    return instance_runner(module_name, DIALECT, TARGET, connect(module_name),
                           INSTANCE.replace("SCHEMA_MODULE", module_name))


def connect(module_name):
    prefix = module_name.upper()
    return resolved(module_name, (
        ("DATABASE_USER", ("{}_DATABASE_USER".format(prefix), "MARIADB_USER")),
        ("DATABASE_PASSWORD", ("{}_DATABASE_PASSWORD".format(prefix), "MARIADB_KEY")),
    )) + CONNECT
