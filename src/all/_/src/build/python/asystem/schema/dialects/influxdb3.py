import json
import re
from datetime import datetime
from os.path import basename
from zoneinfo import ZoneInfo

from requests import post
from requests.exceptions import RequestException

from asystem.bootstrap import load_bootstrap_env_value, load_bootstrap_root
from asystem.schema.document import SchemaDatabaseDimension, SchemaUnreachable, parse_schema_document
from asystem.schema.query import (
    BUCKET,
    NULL,
    PENDING,
    SchemaDialect,
    banner,
    declared_entity,
    describe_statements,
    expanded,
    literals,
    query_statements,
    recent,
    render_statements,
    select,
    unioned,
    vocabulary,
)
from asystem.schema.runner import RUNNER, describe_runner, mutate_runner, query_runner, resolved, verify_runner

DIALECT = "influxdb3"
TARGET = "INFLUXDB3_SERVICE_PROD"
MODULE = "module"

KINDS = ("float", "int", "bool", "str")
TAG = "<string>"

PLACEHOLDERS = {
    "float": "<float>",
    "int": "<int>",
    "bool": "<0|1>",
    "str": "<text>",
}

ENV = ".env"
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
TIME = "time"
SCHEMA = "iox"
DIMENSION = "Dictionary"
CADENCE = "<on-change>"
TIMEOUT = 120

ARROW = (
    ("Dictionary", "str"),
    ("Utf8", "str"),
    ("Boolean", "bool"),
    ("Int", "int"),
    ("Float", "float"),
    ("Decimal", "float"),
)

# noinspection HttpUrlsUsage
CONNECT = """
query() {
  local response status
  response="$(curl -sS -w '\\n%{http_code}' -X POST \\
    "http://${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}/api/v3/query_sql" \\
    -H "Authorization: Bearer ${DATABASE_TOKEN}" \\
    -H "Content-Type: application/json" \\
    --data-binary "$(jq -n --arg db "${DATABASE_NAME}" --arg q "$1" --arg format "${2:-json}" \\
      '{db: $db, q: $q, format: $format}')")"
  status="${response##*$'\\n'}"
  printf '%s' "${response%$'\\n'*}"
  [ "${status}" = "200" ]
}

write_lp() {
  local response status
  response="$(curl -sS -w '\\n%{http_code}' -X POST \\
    "http://${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}/api/v3/write_lp?db=${DATABASE_NAME}&precision=nanosecond" \\
    -H "Authorization: Bearer ${DATABASE_TOKEN}" \\
    -H "Content-Type: text/plain" \\
    --data-binary @-)"
  status="${response##*$'\\n'}"
  if [ "${status}" != "204" ] && [ "${status}" != "200" ]; then
    printf 'write failed with status [%s] body [%s]\\n' "${status}" "${response%$'\\n'*}" >&2
    return 1
  fi
}
""" + RUNNER


def artifacts(document, module_name, options):
    if options.time_column != "timestamp" or options.retention or options.applier:
        raise ValueError("Build generate script [{}] time_column, retention and applier are postgres only, "
                         "the influxdb3 dialect must never be wired to them".format(module_name))
    _validate(document, module_name)
    dialect = _dialect(document, options.timezone)
    written = {}
    for relation in document.relations:
        if relation.carried(KINDS):
            written["model/{}.lp".format(named(relation))] = (leaf(relation, document), False)
    for measurement in measurements(document):
        written["query/{}.sql".format(measurement)] = (
            query_statements(measured(document, measurement), dialect), False)
    written["query.sh"] = (query_runner(module_name, DIALECT, TARGET, connect(module_name)), True)
    written["describe.sh"] = (describe_runner(module_name, DIALECT, TARGET, connect(module_name),
                                              describe_statements(document, dialect)), True)
    if document.discovered:
        return written
    written["verify.sh"] = (verify_runner(module_name, DIALECT, TARGET, connect(module_name),
                                          verify(document, options.rename, options.drop)), True)
    for measurement, statements in mutate(document, options.rename).items():
        written["mutate/rename/{}.sql".format(measurement)] = (statements, False)
    for measurement, statements in retire(document, options.drop).items():
        written["mutate/drop/{}.sql".format(measurement)] = (statements, False)
    written["mutate.sh"] = (mutate_runner(module_name, DIALECT, TARGET, connect(module_name),
                                          _mutate_body(module_name)), True)
    return written


def ship(document, module_name, module_root, schemas_dir, options):
    return None


def connect(module_name):
    return resolved(module_name, (
        ("DATABASE_NAME", ("{}_DATABASE_NAME".format(module_name.upper()), "INFLUXDB3_DATABASE_HOME")),
        ("DATABASE_TOKEN", ("{}_DATABASE_TOKEN".format(module_name.upper()), "INFLUXDB3_TOKEN_ADMIN")),
    )) + CONNECT


class Discover:

    def __init__(self, database=None, module=None, label="", cadence=CADENCE,
                 target=None, port=None, token=None, timeout=TIMEOUT, module_root=None):
        self.module = basename(module_root or load_bootstrap_root()) if module is None else module
        self.label = label
        self.cadence = cadence
        self.timeout = timeout
        self.database = database or self._named("DATABASE_NAME", "INFLUXDB3_DATABASE_HOME", module_root)
        self.target = target or self._env(TARGET, module_root)
        self.port = port or self._env("INFLUXDB3_API_PORT", module_root)
        self.token = token or self._named("DATABASE_TOKEN", "INFLUXDB3_TOKEN_ADMIN", module_root)
        if not self.target or not self.database:
            raise ValueError("Build generate script [{}] influxdb3 discovery found no target [{}] or database [{}] "
                             "in the module env file [{}]".format(self.module, self.target, self.database, ENV))

    def document(self):
        try:
            document = parse_schema_document(self.json(), self.module or self.database)
        except SchemaUnreachable as unreachable:
            print("Build generate script [{}] could not connect to {} with error [{}]"
                  .format(self.module or self.database, DIALECT, unreachable))
            return None
        document.discovered = True
        return document

    def json(self):
        return json.dumps({"module": self.module or self.database,
                           "database": {"relations": [relation for relation in
                                                      (self.relation(table) for table in self.tables()) if relation]}},
                          indent=2)

    def relation(self, table):
        columns = self.columns(table)
        if not self.holds(table, columns):
            return None
        dimensions, measures = [], []
        for column, declared, dimension in columns:
            if self.module and column == MODULE:
                continue
            if dimension:
                dimensions.append({"key": column, "description": self.described(column),
                                   "entities": self.values(table, column)})
            else:
                measures.append({"key": column, "kind": declared, "description": self.described("value")})
        if not measures:
            return None
        subject = max(dimensions, key=lambda dimension: (len(dimension["entities"]), dimension["key"]), default=None)
        if subject is not None:
            subject["subject"] = True
        return {"path": table, "description": self.described(table),
                "cadence": self.cadence, "dimensions": dimensions, "measures": measures}

    def tables(self):
        return [row["table_name"] for row in self.query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = '{}' ORDER BY table_name".format(SCHEMA))]

    def columns(self, table):
        return [(row["column_name"], self.kind(row["data_type"]), DIMENSION in row["data_type"])
                for row in self.query(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema = '{}' AND table_name = '{}' AND column_name != '{}' "
                    "ORDER BY column_name".format(SCHEMA, table, TIME))]

    def kind(self, data_type):
        for pattern, declared in ARROW:
            if pattern in data_type:
                return declared
        raise ValueError("Build generate script [{}] influxdb3 discovery found unmappable arrow type [{}]"
                         .format(self.module, data_type))

    def holds(self, table, columns):
        if not self.module:
            return True
        if not any(column == MODULE for column, _, _ in columns):
            return False
        return bool(self.query('SELECT 1 AS held FROM "{}" WHERE {} = \'{}\' LIMIT 1'.format(
            table, MODULE, self.module)))

    def values(self, table, column):
        rows = self.query('SELECT DISTINCT "{}" AS value FROM "{}" WHERE {} ORDER BY 1'.format(
            column, table, " AND ".join(self.predicates(column))))
        return [str(row["value"]) for row in rows if row.get("value") is not None]

    def predicates(self, column):
        predicates = ['"{}" IS NOT NULL'.format(column)]
        if self.module:
            predicates.append("{} = '{}'".format(MODULE, self.module))
        return predicates

    def described(self, name):
        return "{} {}".format(self.label, name).strip()

    # noinspection HttpUrlsUsage
    def query(self, statement):
        try:
            response = post("http://{}:{}/api/v3/query_sql".format(self.target, self.port),
                            headers={"Authorization": "Bearer {}".format(self.token)},
                            json={"db": self.database, "q": statement, "format": "json"}, timeout=self.timeout)
        except RequestException as exception:
            raise SchemaUnreachable(exception) from exception
        if response.status_code != 200:
            raise ValueError("Build generate script [{}] influxdb3 discovery query failed [{}] status [{}] "
                             "response [{}]".format(self.module, statement, response.status_code, response.text))
        return response.json()

    def _named(self, scoped, backend, module_root):
        return (self._env("{}_{}".format((self.module or "").upper(), scoped), module_root)
                or self._env(backend, module_root))

    @staticmethod
    def _env(name, module_root):
        return load_bootstrap_env_value(name, filename=ENV, module_root=module_root)


def named(relation):
    return relation.scope or relation.plugin


def column(key):
    return key if IDENTIFIER.match(key) else '"{}"'.format(key.replace('"', '""'))


def leaf(relation, document):
    borrowed = _borrowed(relation, document)
    tags = ["{}={}".format(MODULE, document.module)]
    tags += ["{}={}".format(dimension.key, _values(relation, dimension, borrowed))
             for dimension in relation.dimensions]
    fields = ["{}={}".format(measure.key, PLACEHOLDERS[measure.kind]) for measure in relation.carried(KINDS)]
    lines = [banner(), ""] + vocabulary(
        relation, tags=[module_dimension(document)], entities=borrowed)
    if fields:
        lines.append("")
        lines.append(relation.plugin + ",")
        lines += ["  {},".format(tag) for tag in tags[:-1]]
        lines.append("  {}".format(tags[-1]))
        lines += ["    {},".format(field) for field in fields[:-1]]
        lines.append("    {}".format(fields[-1]))
        lines.append("  <timestamp>")
    return "\n".join(lines) + "\n"


def module_dimension(document):
    return SchemaDatabaseDimension(key=MODULE, description="always '{}'".format(document.module))


def where(relation, document, source=None, window=BUCKET):
    predicates = ["{} = '{}'".format(MODULE, document.module)]
    if not document.discovered:
        declared = {dimension.key for dimension in relation.dimensions}
        siblings = {dimension.key for sibling in measured(document, relation.plugin)
                    for dimension in sibling.dimensions}
        predicates += ["{} IS NOT NULL".format(column(key)) for key in sorted(declared)]
        predicates += ["{} IS NULL".format(column(key)) for key in sorted(siblings - declared)]
    return predicates + (recent(source, window) if source else [])


def measured(document, measurement):
    return [relation for relation in document.relations if relation.plugin == measurement]


def measurements(document):
    return sorted({relation.plugin for relation in document.relations})


def verify(document, rename=None, drop=None):
    statements = ["-- declared vocabulary against what the service actually wrote, rows come back only on drift"]
    retired = sorted(set(rename or {}) | set(drop or ()))
    for measurement in measurements(document):
        columns = {TIME, MODULE} | set(retired)
        arms = []
        for relation in measured(document, measurement):
            columns.update(dimension.key for dimension in relation.dimensions)
            for measure in relation.carried(KINDS):
                columns.add(measure.key)
                arms.append(select(
                    [("'{}'".format(relation.path), "relation"), ("'{}'".format(measure.key), "measure"),
                     ("'{}'".format(relation.span(measure) or NULL), "period"),
                     ("'{}'".format(measure.unit or NULL), "unit"), ("'missing'", "fault")],
                    "information_schema.columns", ["table_name = '{}'".format(measurement)],
                    having=["count(*) FILTER (WHERE column_name = '{}') = 0".format(measure.key)]))
        arms.append(_undeclared(measurement, sorted(columns)))
        statements.append(unioned(arms, order_by=["fault", "measure"]))
    if retired:
        statements.append("-- retired measures still carried, reported as [{}] and warned about rather than failing"
                          .format(PENDING))
        for measurement in measurements(document):
            statements.append(unioned([_pending(measurement, name) for name in retired],
                                      order_by=["measure"]))
    return render_statements(statements)


def _pending(measurement, name):
    return select(
        [("'{}'".format(measurement), "relation"), ("'{}'".format(name), "measure"),
         ("'{}'".format(NULL), "period"), ("'{}'".format(NULL), "unit"), ("'{}'".format(PENDING), "fault")],
        "information_schema.columns", ["table_name = '{}'".format(measurement)],
        having=["count(*) FILTER (WHERE column_name = '{}') > 0".format(name)])


def mutate(document, rename):
    written = {}
    sources = {new: old for old, new in (rename or {}).items() if new}
    for measurement in measurements(document):
        statements = []
        for relation in measured(document, measurement):
            for measure in relation.carried(KINDS):
                source = sources.get(measure.key)
                if source is None:
                    continue
                statements.append("-- backfill [{}] from the renamed [{}], one line of protocol per row".format(
                    measure.key, source))
                statements.append(select(
                    [(_protocol(measurement, relation, measure, source), "line")], measurement,
                    where(relation, document) + ["{} IS NOT NULL".format(column(source))],
                    order_by=[TIME]))
        if statements:
            written[measurement] = render_statements(statements)
    return written


def retire(document, drop):
    written = {}
    if not drop:
        return written
    for measurement in measurements(document):
        written[measurement] = render_statements([
            "-- influxdb3 has no column delete and dropping the table would take every other column with it, "
            "so a dropped measure stays in the catalog and this reports the residue it still carries",
            unioned([_retired(measurement, name) for name in sorted(drop)], order_by=["measure"])])
    return written


def _retired(measurement, name):
    return select(
        [("'{}'".format(measurement), "relation"), ("'{}'".format(name), "measure"),
         ("count({})".format(column(name)), "carried"),
         ("CAST(min({}) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(TIME, column(name)), "oldest"),
         ("CAST(max({}) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(TIME, column(name)), "newest")],
        measurement)


def _protocol(measurement, relation, measure, source):
    tags = ["'{}'".format(measurement), "',{}=' || {}".format(MODULE, column(MODULE))]
    for dimension in sorted(dimension.key for dimension in relation.dimensions):
        tags.append("',{}=' || {}".format(dimension, column(dimension)))
    tags.append("' {}=' || {}".format(measure.key, _protocol_value(measure, source)))
    tags.append("' ' || CAST(CAST({} AS BIGINT) AS VARCHAR)".format(TIME))
    return " ||\n        ".join(tags)


def _protocol_value(measure, source):
    if measure.kind == "str":
        return "'\"' || {} || '\"'".format(column(source))
    if measure.kind in ("int", "bool"):
        return "CAST(CAST({} AS BIGINT) AS VARCHAR) || 'i'".format(column(source))
    return "CAST({} AS VARCHAR)".format(column(source))


def _mutate_body(module_name):
    return """
printf '\\nSchema mutate [%s] against [%s]\\n' "{module}" "${{{target}}}"
FAULTS=0
POINTS=0
for SQL_FILE in "${{ROOT_DIR}}"/mutate/rename/*.sql; do
  [ -e "${{SQL_FILE}}" ] || continue
  printf -- '\\n-- rename/%s\\n\\n' "$(basename "${{SQL_FILE}}")"
  while IFS= read -r STATEMENT; do
    [ -z "${{STATEMENT}}" ] && continue
    if ! RESULT="$(query "${{STATEMENT}}")"; then
      fail "${{STATEMENT}}" "${{RESULT}}"
      FAULTS=$((FAULTS + 1))
      continue
    fi
    COUNT="$(printf '%s' "${{RESULT}}" | rows)"
    if [ "${{COUNT}}" = "0" ]; then
      printf 'read [0] points, nothing to backfill\\n'
      continue
    fi
    if ! printf '%s' "${{RESULT}}" | jq -r '.[].line' | write_lp; then
      FAULTS=$((FAULTS + 1))
      continue
    fi
    POINTS=$((POINTS + COUNT))
    printf 'backfilled [%s] points\\n' "${{COUNT}}"
  done < <(statements < "${{SQL_FILE}}")
done

for SQL_FILE in "${{ROOT_DIR}}"/mutate/drop/*.sql; do
  [ -e "${{SQL_FILE}}" ] || continue
  printf -- '\\n-- drop/%s\\n\\n' "$(basename "${{SQL_FILE}}")"
  printf 'influxdb3 has no column delete, so a dropped measure stays in the catalog and is silenced in verify only\\n\\n'
  while IFS= read -r STATEMENT; do
    [ -z "${{STATEMENT}}" ] && continue
    if ! RESULT="$(query "${{STATEMENT}}")"; then
      fail "${{STATEMENT}}" "${{RESULT}}"
      FAULTS=$((FAULTS + 1))
      continue
    fi
    printf '%s\\n' "${{RESULT}}" | table
    printf '\\n'
  done < <(statements < "${{SQL_FILE}}")
done

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema mutate [%s] failed [%s] statement(s)\\n' "{module}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema mutate [%s] backfilled [%s] points with no faults\\n' "{module}" "${{POINTS}}"
""".format(target=TARGET, module=module_name)


def _dialect(document, zone=""):
    return SchemaDialect(
        source=lambda relation: relation.plugin,
        predicates=lambda relation: where(relation, document),
        groups=lambda _: [(measurement, measured(document, measurement)) for measurement in measurements(document)],
        measured=lambda relation, _: where(relation, document),
        counted=lambda measure: "count({})".format(column(measure.key)),
        stamped=lambda function, measure: "CAST({}(time) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(
            function, column(measure.key)),
        entity=_entity,
        declared=_declared,
        undeclared=lambda measurement, relations, declared, keyed: _describe_undeclared(
            measurement, relations, keyed),
        bucket=lambda bucket: _binned(bucket, zone),
        localised=lambda expression: _localised(expression, zone),
        subject=lambda relation: [(column(dimension.key), dimension.key) for dimension in relation.dimensions],
        alias=lambda _, measure: measure.key,
        aggregate=lambda _, measure, function: _aggregate(function, column(measure.key), measure.kind),
        windowed=lambda relation, _, bucket: where(relation, document, relation.plugin, bucket),
        kinds=KINDS)


def _describe_undeclared(measurement, relations, keyed):
    columns = set(keyed) | {TIME, MODULE}
    for relation in relations:
        columns.update(dimension.key for dimension in relation.dimensions)
    return select(
        [("'{}'".format(NULL), "relation"), ("column_name", "measure"), ("'{}'".format(NULL), "kind")] +
        [("'{}'".format(NULL), key) for key in ("unit", "period")] +
        [("CAST(NULL AS BIGINT)", "rows")] +
        [("CAST(NULL AS VARCHAR)", key) for key in ("oldest", "newest")],
        "information_schema.columns",
        ["table_name = '{}'".format(measurement), literals("column_name", sorted(columns))])


def _undeclared(measurement, columns):
    return select(
        [("'{}'".format(measurement), "relation"), ("column_name", "measure"),
         ("'{}'".format(NULL), "period"), ("'{}'".format(NULL), "unit"), ("'undeclared'", "fault")],
        "information_schema.columns",
        ["table_name = '{}'".format(measurement), literals("column_name", columns)])


def _values(relation, dimension, borrowed):
    values = expanded(relation, dimension, borrowed)
    return values[0] if len(values) == 1 else TAG


def _borrowed(relation, document):
    borrowed = {}
    for dimension in relation.dimensions:
        if dimension.subject:
            continue
        for sibling in document.relations:
            subject = sibling.subject
            if subject is not None and subject.key == dimension.key and sibling.entities:
                borrowed[dimension.key] = sibling.entities
                break
    return borrowed


def _validate(document, module_name):
    scopes = {}
    for relation in document.relations:
        if not relation.carried(KINDS):
            continue
        if named(relation) in scopes:
            raise ValueError(
                "Build generate script [{}] relations [{}] and [{}] share the scope [{}] so both would write "
                "the same leaf, rename one scope".format(module_name, scopes[named(relation)], relation.path,
                                                         named(relation)))
        scopes[named(relation)] = relation.path
    for measurement in measurements(document):
        dimensions = {}
        for relation in measured(document, measurement):
            keyed = tuple(sorted(dimension.key for dimension in relation.dimensions))
            if keyed in dimensions:
                raise ValueError(
                    "Build generate script [{}] relations [{}] and [{}] share the measurement [{}] and declare the "
                    "same dimensions {} so neither can be told apart, give one a distinguishing dimension or fold "
                    "them together".format(module_name, dimensions[keyed], relation.path, measurement, list(keyed)))
            dimensions[keyed] = relation.path


def _declared(relation):
    return declared_entity(relation, column(relation.subject.key) if relation.subject is not None else None)


def _entity(relation):
    keys = [column(dimension.key) for dimension in relation.dimensions]
    return keys[0] if len(keys) == 1 else "concat({})".format(", '/', ".join(keys))


def _aggregate(function, expression, kind):
    if function == "count":
        return "count({})".format(expression)
    if function == "distinct":
        return "count(DISTINCT {})".format(expression)
    if function == "last":
        latest = "last_value({} ORDER BY time)".format(expression)
        return latest if kind == "str" else _rounded(latest)
    return _rounded("{}({})".format(function, expression))


def _binned(bucket, zone):
    return "date_bin(INTERVAL '{}', {})".format(bucket, _localised("time", zone))


def _localised(expression, zone):
    offset = _offset(zone)
    return expression if not offset else "{} + INTERVAL '{} minute'".format(expression, offset)


def _offset(zone):
    if not zone or zone == "UTC":
        return 0
    shift = datetime(2000, 1, 1, tzinfo=ZoneInfo(zone)).utcoffset()
    return 0 if shift is None else int(shift.total_seconds() // 60)


def _rounded(expression):
    return "round({}, 1)".format(expression)
