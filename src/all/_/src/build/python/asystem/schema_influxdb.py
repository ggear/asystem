from asystem.schema import (NO, NULL, PLACEHOLDER, RUNNER, SUBJECT, YES, banner, literals,
                            script, select)


PLACEHOLDERS = {
    "float": "<number>",
    "int": "<number>i",
    "bool": "<0|1>i",
    "str": "<text>",
    "obj": "<object>",
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


def leaf(relation):
    tags = ["{}=<{}>".format(dimension.key, dimension.key) for dimension in relation.dimensions]
    fields = ["{}={}".format(measure.key, PLACEHOLDERS[measure.kind]) for measure in relation.persisted]
    lines = [banner(), "# {} [{}]".format(relation.path, relation.desc)]
    if fields:
        lines.append(relation.plugin + "".join("," + tag for tag in tags))
        lines += ["    {},".format(field) for field in fields[:-1]]
        lines.append("    {}".format(fields[-1]))
        lines.append("    <timestamp>")
    return "\n".join(lines) + "\n"


def where(relation, document, window=None):
    declared = {dimension.key for dimension in relation.dimensions}
    siblings = {dimension.key for sibling in measured(document, relation.plugin)
                for dimension in sibling.dimensions}
    predicates = ["{} IS NOT NULL".format(key) for key in sorted(declared)]
    predicates += ["{} IS NULL".format(key) for key in sorted(siblings - declared)]
    return predicates + (["time > now() - INTERVAL '{}'".format(window)] if window else [])


def measured(document, measurement):
    return [relation for relation in document.relations if relation.plugin == measurement]


def measurements(document):
    return sorted({relation.plugin for relation in document.relations})


def describe(document):
    relations = [relation for relation in document.relations if relation.persisted]
    return _statements([
        "-- dimensions", _describe_relations(relations, document),
        "-- measures", _describe_measures(document),
        "-- entities", _describe_entities(relations, document)])


def queries(document, relations):
    statements = []
    for relation in relations:
        if not relation.persisted:
            statements.append("-- {} [{}] declares no persisted measure, so nothing is written for it"
                              .format(relation.path, relation.desc))
            continue
        statements.append("-- {} [{}] every {}".format(relation.path, relation.desc, relation.cadence))
        statements += _absent(relation)
        selectors = [("date_bin(INTERVAL '1 hour', time)", "bucket")]
        selectors += [(dimension.key, "") for dimension in relation.dimensions]
        for measure in relation.measures:
            if not measure.persist or measure.kind in ("str", "obj"):
                continue
            if measure.kind == "bool":
                selectors.append(("avg({})".format(measure.key), measure.key + "_fraction"))
            elif measure.kind == "int":
                selectors.append(("last_value({} ORDER BY time)".format(measure.key), measure.key))
            else:
                selectors += [("{}({})".format(function, measure.key), "{}_{}".format(measure.key, suffix))
                              for function, suffix in (("avg", "avg"), ("min", "min"), ("max", "max"))]
        if len(selectors) == 1 + len(relation.dimensions):
            continue
        grouping = ["bucket"] + [dimension.key for dimension in relation.dimensions]
        statements.append(select(selectors, relation.plugin, where(relation, document, "7 days"),
                                 group_by=grouping, order_by=grouping))
    return _statements(statements)


def verify(document):
    statements = ["-- every column in every measurement is declared, rows come back only on drift"]
    for measurement in measurements(document):
        columns = {"time"}
        for relation in measured(document, measurement):
            columns.update(dimension.key for dimension in relation.dimensions)
            columns.update(measure.key for measure in relation.persisted)
        statements.append(select([("'{}'".format(measurement), "measurement"), ("column_name", "")],
                                 "information_schema.columns",
                                 ["table_name = '{}'".format(measurement),
                                  literals("column_name", sorted(columns))],
                                 order_by=["column_name"]))
    for relation in document.relations:
        if not relation.entities or relation.subject is None or not relation.persisted:
            continue
        statements.append("-- {} carries only its declared entities, rows come back only on drift"
                          .format(relation.path))
        statements.append(select(
            [("'{}'".format(relation.path), "relation"), (relation.subject.key, "entity"),
             ("count(*)", "rows_total")], relation.plugin,
            where(relation, document, "1 day") + [literals(relation.subject.key, relation.entities)],
            group_by=[relation.subject.key]))
    return _statements(statements)


def observe(document):
    statements = ["-- open entity domains, printed for eyeballing and never asserted"]
    for relation in document.relations:
        if relation.entities or relation.subject is None or not relation.persisted:
            continue
        statements.append(select(
            [("'{}'".format(relation.path), "relation"), (relation.subject.key, "entity"),
             ("count(*)", "rows_total"), ("max(time)", "last_seen")], relation.plugin,
            where(relation, document, "1 day"),
            group_by=[relation.subject.key], order_by=[relation.subject.key]))
    return _statements(statements)


def _describe_relations(relations, document):
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"), ("'{}'".format(_dimension(relation)), "dimension"),
                ("'{}'".format(relation.cadence), "cadence"),
                ("{}".format(len(relation.measures)), "measures"),
                ("{}".format(len(relation.persisted)), "persisted"),
                ("'{}'".format(_declared_entities(relation)), "declared"),
                ("count(DISTINCT {})".format(relation.subject.key) if relation.subject
                 else "'{}'".format(NULL), "observed"),
                ("count(*)", "rows"), ("min(time)", "oldest"), ("max(time)", "newest")],
               relation.plugin, where(relation, document))
        for relation in relations) + "\nORDER BY relation"


def _describe_measures(document):
    arms = []
    for measurement in measurements(document):
        columns = {"time"}
        for relation in measured(document, measurement):
            columns.update(dimension.key for dimension in relation.dimensions)
            persisted = {measure.key for measure in relation.persisted}
            for measure in relation.measures:
                columns.add(measure.key)
                declared = _declared_measure(relation, measure, measure.unit or NULL, measure.period or NULL)
                if measure.key not in persisted:
                    arms.append(select(declared + _absent_measure(), PLACEHOLDER))
                    continue
                arms.append(select(declared + [
                    ("CASE WHEN count({}) > 0 THEN '{}' ELSE '{}' END".format(measure.key, YES, NO), "observed"),
                    ("CAST(count({}) AS VARCHAR)".format(measure.key), "rows"),
                    ("CAST(min(time) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(measure.key), "oldest"),
                    ("CAST(max(time) FILTER (WHERE {} IS NOT NULL) AS VARCHAR)".format(measure.key), "newest")],
                    measurement, where(relation, document)))
        arms.append(select(
            [("'{}'".format(NULL), "relation"), ("column_name", "measure")] +
            [("'{}'".format(NULL), key) for key in ("kind", "unit", "period", "persisted")] +
            [("'{}'".format(YES), "observed")] +
            [("'{}'".format(NULL), key) for key in ("rows", "oldest", "newest")],
            "information_schema.columns",
            ["table_name = '{}'".format(measurement), literals("column_name", sorted(columns))]))
    return "\nUNION ALL\n".join(arms) + "\nORDER BY relation, measure"


def _declared_measure(relation, measure, unit, period):
    return [("'{}'".format(relation.path), "relation"), ("'{}'".format(measure.key), "measure"),
            ("'{}'".format(measure.kind), "kind"), ("'{}'".format(unit), "unit"),
            ("'{}'".format(period), "period"),
            ("'{}'".format(YES if measure.persist else NO), "persisted")]


def _absent_measure():
    return [("'{}'".format(NO), "observed")] + \
        [("'{}'".format(NULL), key) for key in ("rows", "oldest", "newest")]


def _describe_entities(relations, document):
    arms = [relation for relation in relations if relation.dimensions]
    if not arms:
        return ""
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"),
                ("'{}'".format(_dimension(relation)), "dimension"), (_entity(relation), "entity"),
                (_declared(relation), "declared"), ("count(*)", "rows"),
                ("min(time)", "oldest"), ("max(time)", "newest")],
               relation.plugin, where(relation, document),
               group_by=_grouping(_entity(relation), _declared(relation)))
        for relation in arms) + "\nORDER BY relation, entity"


def _declared_entities(relation):
    return len(relation.entities) if relation.entities else NULL


def _dimension(relation):
    return "/".join(dimension.key + (SUBJECT if dimension.subject else "")
                    for dimension in relation.dimensions) or NULL


def _entity(relation):
    keys = [dimension.key for dimension in relation.dimensions]
    return keys[0] if len(keys) == 1 else "concat({})".format(", '/', ".join(keys))


def _grouping(entity, declared):
    return [entity] + ([declared] if declared.startswith("CASE") else [])


def _declared(relation):
    if not relation.entities or relation.subject is None:
        return "'{}'".format(NULL)
    return "CASE WHEN {} THEN '{}' ELSE '{}' END".format(
        literals(relation.subject.key, relation.entities, negate=False), YES, NO)


def _absent(relation):
    absent = [(measure.key, measure.kind, "not persisted" if not measure.persist else "carried as a tag")
              for measure in relation.measures
              if not measure.persist or measure.kind in ("str", "obj")]
    if not absent:
        return []
    key_width = max(len(key) for key, _, _ in absent)
    kind_width = max(len(kind) for _, kind, _ in absent)
    return ["-- {} {} is declared but {}, so it is absent by design".format(
        key.ljust(key_width), "[{}]".format(kind).ljust(kind_width + 2), reason)
        for key, kind, reason in absent]


def describe_script(module_name, dialect):
    return script(module_name, dialect, "describe", "print what production actually carries", CONNECT, """
printf '\\n'
SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${{INFLUXDB3_SERVICE_PROD}}" \\
  query_file "${{ROOT_DIR}}/sql/describe.sql"
""".format(module_name))


def query_script(module_name, dialect):
    return script(module_name, dialect, "query", "run the generated query for every declared relation", CONNECT, """
printf '\\nSchema query [%s] against [%s]\\n\\n' "{}" "${{INFLUXDB3_SERVICE_PROD}}"
FAULTS=0
for SQL_FILE in "${{ROOT_DIR}}"/sql/query_*.sql; do
  printf '\\n== %s ==\\n' "$(basename "${{SQL_FILE}}")"
  query_file "${{SQL_FILE}}" || FAULTS=$((FAULTS + 1))
done
[ "${{FAULTS}}" = 0 ]
""".format(module_name))


def verify_script(module_name, dialect):
    return script(module_name, dialect, "verify", "assert production matches the declaration", CONNECT, """
printf '\\nSchema verify [%s] against [%s]\\n\\n' "{}" "${{INFLUXDB3_SERVICE_PROD}}"

FAULTS=0
while IFS= read -r STATEMENT; do
  [ -z "${{STATEMENT}}" ] && continue
  if ! RESULT="$(query "${{STATEMENT}}")"; then
    fail "${{STATEMENT}}" "${{RESULT}}"
    exit 1
  fi
  ROWS="$(printf '%s' "${{RESULT}}" | jq 'length')"
  if [ "${{ROWS}}" != "0" ]; then
    FAULTS=$((FAULTS + ROWS))
    printf '%s\\n' "${{RESULT}}" | table
    printf '\\n'
  fi
done < <(statements "${{ROOT_DIR}}/sql/verify.sql")

printf '\\nSchema verify [%s] observed entities of open domains\\n\\n' "{}"
query_file "${{ROOT_DIR}}/sql/observe.sql"

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema verify [%s] found [%s] fault row(s)\\n' "{}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema verify [%s] found no drift\\n' "{}"
""".format(module_name, module_name, module_name, module_name))


def discover_script(module_name, dialect, document):
    open_relations = [relation for relation in document.relations
                      if not relation.entities and relation.subject is not None and relation.persisted]
    return script(module_name, dialect, "discover", "draft a declaration from what production carries", CONNECT, """
printf '\\nSchema discover [%s] against [%s], a drafting aid that is never an input to the build\\n\\n' "{}" "${{INFLUXDB3_SERVICE_PROD}}"
{}
""".format(module_name, "\n".join(
        'printf \'\\n== %s ==\\n\' "{}"\nquery_one "SELECT DISTINCT {} AS entity FROM {} '
        'WHERE {} ORDER BY {}" || exit 1'.format(
            relation.path, relation.subject.key, relation.plugin,
            " AND ".join(where(relation, document, "7 days")), relation.subject.key)
        for relation in open_relations) or 'printf \'no open entity domains declared\\n\''))


def _statements(statements):
    blocks, block = [], []
    for statement in statements:
        if block and not block[-1].startswith("--"):
            blocks.append(block)
            block = []
        block.append(statement if statement.startswith("--") else statement + ";")
    if block:
        blocks.append(block)
    return banner("--") + "\n\n" + "\n\n".join("\n".join(block) for block in blocks) + "\n"
