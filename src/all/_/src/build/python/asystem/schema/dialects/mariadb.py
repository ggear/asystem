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
    count(t.TABLE_NAME)                                               AS 'tables',
    round(coalesce(sum(t.DATA_LENGTH + t.INDEX_LENGTH), 0) / 1048576, 1) AS 'size'
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
      round(coalesce(max(t.DATA_LENGTH + t.INDEX_LENGTH), 0) / 1048576, 1) AS 'size',
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
printf '\\n'

for DATABASE_NAME in $(databases); do
  section "tables ${DATABASE_NAME}"
  CATALOGUE="$(catalogued "${DATABASE_NAME}")" || { fail "${DATABASE_NAME}" "${CATALOGUE}"; exit 1; }
  STATEMENT=""
  while IFS=$'\\t' read -r TABLE COLUMNS SIZE STAMP EPOCH; do
    [ -z "${TABLE}" ] && continue
    EARLIEST=""
    LATEST=""
    if [ "${STAMP}" != "-" ]; then
      EARLIEST="DATE_FORMAT(min(\\`${STAMP}\\`), '%Y-%m-%d %H:%i:%s')"
      LATEST="DATE_FORMAT(max(\\`${STAMP}\\`), '%Y-%m-%d %H:%i:%s')"
    fi
    if [ "${EPOCH}" != "-" ]; then
      [ -n "${EARLIEST}" ] && EARLIEST="${EARLIEST}, "
      [ -n "${LATEST}" ] && LATEST="${LATEST}, "
      EARLIEST="${EARLIEST}DATE_FORMAT(FROM_UNIXTIME(min(\\`${EPOCH}\\`)), '%Y-%m-%d %H:%i:%s')"
      LATEST="${LATEST}DATE_FORMAT(FROM_UNIXTIME(max(\\`${EPOCH}\\`)), '%Y-%m-%d %H:%i:%s')"
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
    STATEMENT="${STATEMENT} ${COLUMNS} AS 'columns', count(*) AS 'rows', ${SIZE} AS 'size',"
    STATEMENT="${STATEMENT} ${OLDEST} AS 'oldest', ${NEWEST} AS 'newest'"
    STATEMENT="${STATEMENT} FROM \\`${DATABASE_NAME}\\`.\\`${TABLE}\\`"
  done < <(printf '%s' "${CATALOGUE}" | jq -r '.[] | [.table, .columns, .size, .stamp, .epoch] | @tsv')
  if [ -z "${STATEMENT}" ]; then
    printf 'no rows\\n\\n'
    continue
  fi
  query_one "${STATEMENT} ORDER BY 4 DESC" || exit 1
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
