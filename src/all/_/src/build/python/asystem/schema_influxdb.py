import json

from requests import post

from os.path import basename

from asystem.bootstrap import load_bootstrap_env_value, load_bootstrap_root
from asystem.schema import (
    BUCKET,
    NULL,
    RUNNER,
    SchemaDatabaseDimension,
    aggregations,
    banner,
    bucketed,
    declared_entity,
    declared_measure,
    describe_runner,
    dimension_label,
    grouping_keys,
    labels,
    literals,
    parted,
    parse_schema_document,
    query_runner,
    recent,
    render_statements,
    select,
    verify_runner,
    vocabulary,
)

DIALECT = "influxdb3"
TARGET = "INFLUXDB3_SERVICE_PROD"
MODULE = "module"
TAG = "<string>"

PLACEHOLDERS = {
    "float": "<float>",
    "int": "<int>",
    "bool": "<0|1>",
    "str": "<text>",
}

ENV = ".env"
TIME = "time"
SCHEMA = "iox"
DIMENSION = "Dictionary"
CADENCE = "<on-change>"
TIMEOUT = 120

KINDS = (
    ("Dictionary", "str"),
    ("Utf8", "str"),
    ("Boolean", "bool"),
    ("Int", "int"),
    ("Float", "float"),
    ("Decimal", "float"),
)

# noinspection HttpUrlsUsage
CONNECT = """
DATABASE_NAME="${DATABASE_NAME:-${INFLUXDB3_DATABASE_HOME}}"

query() {
  local response status
  response="$(curl -sS -w '\\n%{http_code}' -X POST \\
    "http://${INFLUXDB3_SERVICE_PROD}:${INFLUXDB3_API_PORT}/api/v3/query_sql" \\
    -H "Authorization: Bearer ${INFLUXDB3_TOKEN_ADMIN}" \\
    -H "Content-Type: application/json" \\
    --data-binary "$(jq -n --arg db "${DATABASE_NAME}" --arg q "$1" --arg format "${2:-json}" \\
      '{db: $db, q: $q, format: $format}')")"
  status="${response##*$'\\n'}"
  printf '%s' "${response%$'\\n'*}"
  [ "${status}" = "200" ]
}
""" + RUNNER


def artifacts(document, module_name, time_column="timestamp", retention=None):
    if time_column != "timestamp" or retention is not None:
        raise ValueError("Build generate script [{}] time_column and retention are postgres only, "
                         "the influxdb3 dialect must never be wired to them".format(module_name))
    _validate(document, module_name)
    written = {}
    for relation in document.relations:
        if relation.persisted:
            written["model/{}.lp".format(named(relation))] = (leaf(relation, document), False)
    for measurement in measurements(document):
        written["query/query_{}.sql".format(measurement)] = (
            queries(document, measured(document, measurement)), False)
    written["query.sh"] = (query_runner(module_name, DIALECT, TARGET, CONNECT), True)
    if document.discovered:
        return written
    written["query/describe.sql"] = (describe(document), False)
    written["query/verify.sql"] = (verify(document), False)
    written["describe.sh"] = (describe_runner(module_name, DIALECT, TARGET, CONNECT), True)
    written["verify.sh"] = (verify_runner(module_name, DIALECT, TARGET, CONNECT), True)
    return written


def ship(_document, _module_name, _module_root, _schemas_dir, _time_column="timestamp"):
    return None


class Discover:
    """Reflect a live influxdb3 database into the documented schema JSON.

    A service that declares its schema in code reflects it through [load_schema_document]. A database
    written by something outside this repo declares nothing, so its schema is only knowable by asking
    the database what it holds. This asks, and emits the very same document the go and rust reflectors
    print, so a discovered schema reaches [write_schema_database] by the same path a declared one does
    and is validated by the same rules.

    Nothing here knows any module, only influxdb3. The vocabulary a discovered document cannot carry
    (what a relation means, what a measure is worth, how often it is written) is the caller's to supply
    through [label] and [cadence], or to set on the returned document before handing it on.

    Every table in [database] becomes one relation named by the table, since a discovered table has no
    scope to divide it. Dictionary columns become dimensions carrying their distinct values, the subject
    being the widest of them, and every other column but [time] becomes a measure typed by mapping its
    arrow type onto a declared kind.

    Discovery is scoped to the rows one module wrote, [module] defaulting to the calling module's
    directory name, which is the value every module tags its rows with. Every table is checked for a
    row carrying it and skipped when it holds none, so a database shared by several writers yields
    only what this module wrote. The module tag is dropped from the dimensions, the dialect owning
    it. Pass an empty [module] to discover a whole database regardless of who wrote it.
    """

    def __init__(self, database=None, module=None, label="", cadence=CADENCE,
                 target=None, port=None, token=None, timeout=TIMEOUT, module_root=None):
        self.module = basename(module_root or load_bootstrap_root()) if module is None else module
        self.label = label
        self.cadence = cadence
        self.timeout = timeout
        self.database = database or self._env("INFLUXDB3_DATABASE_HOME", module_root)
        self.target = target or self._env(TARGET, module_root)
        self.port = port or self._env("INFLUXDB3_API_PORT", module_root)
        self.token = token or self._env("INFLUXDB3_TOKEN_ADMIN", module_root)
        if not self.target or not self.database:
            raise ValueError("Build generate script [{}] influxdb3 discovery found no target [{}] or database [{}] "
                             "in the module env file [{}]".format(module, self.target, self.database, ENV))

    def document(self):
        document = parse_schema_document(self.json(), self.module or self.database)
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
        return [(row["column_name"], kind(row["data_type"]), DIMENSION in row["data_type"]) for row in self.query(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = '{}' AND table_name = '{}' AND column_name != '{}' "
            "ORDER BY column_name".format(SCHEMA, table, TIME))]

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
        response = post("http://{}:{}/api/v3/query_sql".format(self.target, self.port),
                        headers={"Authorization": "Bearer {}".format(self.token)},
                        json={"db": self.database, "q": statement, "format": "json"}, timeout=self.timeout)
        if response.status_code != 200:
            raise ValueError("Build generate script [{}] influxdb3 discovery query failed [{}] status [{}] "
                             "response [{}]".format(self.module, statement, response.status_code, response.text))
        return response.json()

    @staticmethod
    def _env(name, module_root):
        return load_bootstrap_env_value(name, filename=ENV, module_root=module_root)


def kind(data_type):
    for pattern, declared in KINDS:
        if pattern in data_type:
            return declared
    raise ValueError("Build generate script influxdb3 discovery found unmappable arrow type [{}]".format(data_type))


def named(relation):
    return relation.scope or relation.plugin


def leaf(relation, document):
    tags = ["{}={}".format(MODULE, document.module)]
    tags += ["{}={}".format(dimension.key, TAG) for dimension in relation.dimensions]
    fields = ["{}={}".format(measure.key, PLACEHOLDERS[measure.kind]) for measure in relation.persisted]
    lines = [banner(), ""] + vocabulary(
        relation, tags=[module_dimension(document)], entities=_borrowed(relation, document))
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
        predicates += ["{} IS NOT NULL".format(key) for key in sorted(declared)]
        predicates += ["{} IS NULL".format(key) for key in sorted(siblings - declared)]
    return predicates + (recent(source, window) if source else [])


def measured(document, measurement):
    return [relation for relation in document.relations if relation.plugin == measurement]


def measurements(document):
    return sorted({relation.plugin for relation in document.relations})


def describe(document):
    relations = [relation for relation in document.relations if relation.persisted]
    return render_statements([
        "-- dimensions", _describe_relations(relations, document),
        "-- measures", _describe_measures(document),
        "-- entities", _describe_entities(relations, document)])


def queries(document, relations):
    statements = []
    for relation in relations:
        if not relation.persisted:
            statements.append("-- {} [{}] declares no persisted measure, so nothing is written for it"
                              .format(relation.path, relation.description))
            continue
        bucket = bucketed(relation.cadence)
        heading = "-- {} [{}] every {}, bucketed [{}] across the newest two buckets".format(
            relation.path, relation.description, relation.cadence, bucket)
        measured_selectors = []
        for measure in relation.persisted:
            for function, suffix in aggregations(measure, relation.cadence):
                measured_selectors.append((_aggregate(function, measure.key),
                                           "_".join(part for part in (measure.key, suffix) if part)))
        if not measured_selectors:
            continue
        keys = [dimension.key for dimension in relation.dimensions]
        label = labels(["bucket"] + keys + [alias for _, alias in measured_selectors], ["time"])
        parts = parted(measured_selectors, len(keys) + 1, {alias: label[alias].strip('"') for _, alias in measured_selectors})
        for index, part in enumerate(parts):
            statements.append(heading)
            statements.append("-- part {} of {}:".format(index + 1, len(parts)))
            selectors = [("date_bin(INTERVAL '{}', time)".format(bucket), label["bucket"])]
            selectors += [(key, label[key]) for key in keys]
            selectors += [(expression, label[alias]) for expression, alias in part]
            grouping = [label["bucket"]] + keys
            statements.append(select(selectors, relation.plugin, where(relation, document, relation.plugin, bucket),
                                     group_by=grouping, order_by=grouping))
    return render_statements(statements)


def verify(document):
    statements = ["-- declared vocabulary against what the service actually wrote, rows come back only on drift"]
    for measurement in measurements(document):
        columns = {"time", MODULE}
        arms = []
        for relation in measured(document, measurement):
            columns.update(dimension.key for dimension in relation.dimensions)
            for measure in relation.persisted:
                columns.add(measure.key)
                arms.append(select(
                    [("'{}'".format(relation.path), "relation"), ("'{}'".format(measure.key), "measure"),
                     ("'{}'".format(relation.span(measure) or NULL), "period"),
                     ("'{}'".format(measure.unit or NULL), "unit"), ("'missing'", "fault")],
                    "information_schema.columns", ["table_name = '{}'".format(measurement)],
                    having=["count(*) FILTER (WHERE column_name = '{}') = 0".format(measure.key)]))
        arms.append(select(
            [("'{}'".format(measurement), "relation"), ("column_name", "measure"),
             ("'{}'".format(NULL), "period"), ("'{}'".format(NULL), "unit"), ("'undeclared'", "fault")],
            "information_schema.columns",
            ["table_name = '{}'".format(measurement), literals("column_name", sorted(columns))]))
        statements.append("\nUNION ALL\n".join(arms) + "\nORDER BY fault, measure")
    return render_statements(statements)


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
        if not relation.persisted:
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


def _describe_relations(relations, document):
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"), ("'{}'".format(dimension_label(relation)), "dimension"),
                ("{}".format(len(relation.measures)), "measures"),
                ("'{}'".format(relation.cadence), "cadence"),
                ("count(*)", "rows"), ("min(time)", "oldest"), ("max(time)", "newest")],
               relation.plugin, where(relation, document))
        for relation in relations) + "\nORDER BY rows DESC"


def _describe_measures(document):
    arms = []
    for measurement in measurements(document):
        columns = {"time", MODULE}
        for relation in measured(document, measurement):
            columns.update(dimension.key for dimension in relation.dimensions)
            persisted = {measure.key for measure in relation.persisted}
            for measure in relation.measures:
                columns.add(measure.key)
                if measure.key not in persisted:
                    continue
                declared = declared_measure(relation, measure, measure.unit or NULL, relation.span(measure) or NULL)
                arms.append(select(declared + [
                    ("count({})".format(measure.key), "rows"),
                    ("CAST(min(time) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(measure.key), "oldest"),
                    ("CAST(max(time) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(measure.key), "newest")],
                                   measurement, where(relation, document)))
        arms.append(select(
            [("'{}'".format(NULL), "relation"), ("column_name", "measure")] +
            [("'{}'".format(NULL), key) for key in ("kind", "unit", "period")] +
            [("CAST(NULL AS BIGINT)", "rows")] +
            [("CAST(NULL AS VARCHAR)", key) for key in ("oldest", "newest")],
            "information_schema.columns",
            ["table_name = '{}'".format(measurement), literals("column_name", sorted(columns))]))
    return "\nUNION ALL\n".join(arms) + "\nORDER BY rows DESC NULLS LAST"


def _describe_entities(relations, document):
    arms = [relation for relation in relations if relation.dimensions]
    if not arms:
        return ""
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"),
                ("'{}'".format(dimension_label(relation)), "dimension"), (_entity(relation), "entity"),
                (declared_entity(relation), "declared"), ("count(*)", "rows"),
                ("min(time)", "oldest"), ("max(time)", "newest")],
               relation.plugin, where(relation, document),
               group_by=grouping_keys(_entity(relation), declared_entity(relation)))
        for relation in arms) + "\nORDER BY rows DESC"


def _entity(relation):
    keys = [dimension.key for dimension in relation.dimensions]
    return keys[0] if len(keys) == 1 else "concat({})".format(", '/', ".join(keys))


def _aggregate(function, column):
    if function == "last":
        return _rounded("last_value({} ORDER BY time)".format(column))
    return _rounded("{}({})".format(function, column))


def _rounded(expression):
    return "round({}, 1)".format(expression)
