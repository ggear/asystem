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

PLACEHOLDERS = {
    "float": "<number>",
    "int": "<number>i",
    "bool": "<0|1>i",
    "str": "<text>",
}

# noinspection HttpUrlsUsage
CONNECT = """
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
            written["model/{}.lp".format(relation.scope)] = (leaf(relation, document), False)
    for measurement in measurements(document):
        written["query/query_{}.sql".format(measurement)] = (
            queries(document, measured(document, measurement)), False)
    written["query/describe.sql"] = (describe(document), False)
    written["query/verify.sql"] = (verify(document), False)
    written["describe.sh"] = (describe_runner(module_name, DIALECT, TARGET, CONNECT), True)
    written["query.sh"] = (query_runner(module_name, DIALECT, TARGET, CONNECT), True)
    written["verify.sh"] = (verify_runner(module_name, DIALECT, TARGET, CONNECT), True)
    return written


def ship(_document, _module_name, _module_root, _schemas_dir, _time_column="timestamp"):
    return None


def leaf(relation, document):
    tags = ["{}={}".format(MODULE, document.module)]
    tags += ["{}=<{}>".format(dimension.key, dimension.key) for dimension in relation.dimensions]
    fields = ["{}={}".format(measure.key, PLACEHOLDERS[measure.kind]) for measure in relation.persisted]
    lines = [banner(), ""] + vocabulary(relation, tags=[module_dimension(document)])
    if fields:
        lines.append("")
        lines.append(relation.plugin + "".join("," + tag for tag in tags))
        lines += ["    {},".format(field) for field in fields[:-1]]
        lines.append("    {}".format(fields[-1]))
        lines.append("    <timestamp>")
    return "\n".join(lines) + "\n"


def module_dimension(document):
    return SchemaDatabaseDimension(
        key=MODULE, description="module the rows are written by, always [{}]".format(document.module))


def where(relation, document, source=None, window=BUCKET):
    declared = {dimension.key for dimension in relation.dimensions}
    siblings = {dimension.key for sibling in measured(document, relation.plugin) for dimension in sibling.dimensions}
    predicates = ["{} = '{}'".format(MODULE, document.module)]
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


def _validate(document, module_name):
    scopes = {}
    for relation in document.relations:
        if not relation.persisted:
            continue
        if relation.scope in scopes:
            raise ValueError(
                "Build generate script [{}] relations [{}] and [{}] share the scope [{}] so both would write "
                "the same leaf, rename one scope".format(module_name, scopes[relation.scope], relation.path,
                                                         relation.scope))
        scopes[relation.scope] = relation.path
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
