from asystem.schema import (NO, NULL, PLACEHOLDER, RUNNER, SUBJECT, YES, banner, indent,
                            literals, script, select)

TIME_COLUMNS = {
    "date": ("DATE", "INTERVAL '10 years'", "CURRENT_DATE"),
    "timestamp": ("TIMESTAMPTZ", "INTERVAL '1 month'", "now()"),
}

RESOLVE = """
DATABASE_USER="${DATABASE_USER:-${%(prefix)s_DATABASE_USER:-${POSTGRES_USER_%(prefix)s:-}}}"
DATABASE_NAME="${DATABASE_NAME:-${%(prefix)s_DATABASE_NAME:-${POSTGRES_DATABASE_%(prefix)s:-}}}"
DATABASE_PASSWORD="${DATABASE_PASSWORD:-${%(prefix)s_DATABASE_PASSWORD:-${POSTGRES_KEY_%(prefix)s:-}}}"

for VARIABLE in DATABASE_USER DATABASE_NAME DATABASE_PASSWORD; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [%(module)s] could not resolve [${VARIABLE}] from [${VARIABLE}] or \
[%(prefix)s_${VARIABLE}] or its POSTGRES_ equivalent, declare it in the module env files" >&2
    exit 1
  fi
done
"""

CONNECT = """
PSQL=(psql -h "${POSTGRES_SERVICE_PROD}" -p "${POSTGRES_API_PORT}" -U "${DATABASE_USER}" -d "${DATABASE_NAME}")
export PGPASSWORD="${DATABASE_PASSWORD}"

query() {
  "${PSQL[@]}" -q -t -A -v ON_ERROR_STOP=1 -c "SELECT row_to_json(result) FROM ($1) AS result" 2>&1
}
""" + RUNNER


def connect(module_name):
    return RESOLVE % {"prefix": module_name.upper(), "module": module_name} + CONNECT


def columns(table, time_column):
    column_type, _, _ = TIME_COLUMNS[time_column]
    return {
        "table": table,
        "time": {"column": "time", "type": column_type},
        "dimensions": ["entity", "type", "period", "unit"],
        "value": {"column": "value", "type": "FLOAT8"},
        "strategy": "staging" if time_column == "date" else "direct",
    }


def leaf(relations, table, time_column, retention):
    column_type, chunk_interval, _ = TIME_COLUMNS[time_column]
    lines = [banner("--"), ""]
    for relation in relations:
        lines.append("-- {} [{}]".format(relation.path, relation.desc))
        lines.append("-- vocabulary, one row per declared (entity, type, period, unit)")
        lines += ["--   entity {}".format(entity) for entity in relation.entities] or \
                 ["--   entity <open domain, owned by a live third party source>"]
        for measure in relation.measures:
            lines.append("--   type {} period {} unit {} [{}]".format(
                measure.key, measure.period or relation.cadence, measure.unit, measure.desc))
        lines.append("--")
    lines = lines[:-1]
    lines += [
        "",
        "CREATE TABLE IF NOT EXISTS {} (".format(table),
        "    time   {} NOT NULL,".format(column_type.ljust(6)),
        "    entity TEXT   NOT NULL,",
        "    type   TEXT   NOT NULL,",
        "    period TEXT   NOT NULL,",
        "    unit   TEXT   NOT NULL,",
        "    value  FLOAT8 NOT NULL,",
        "    PRIMARY KEY (time, entity, type, period, unit)",
        ");",
        "",
        "SELECT create_hypertable('{}', 'time', chunk_time_interval => {}, if_not_exists => TRUE);".format(
            table, chunk_interval),
        "",
    ]
    for column in ("entity", "type", "period", "unit"):
        lines.append("CREATE INDEX IF NOT EXISTS {0}_{1}_time ON {0} ({1}, time DESC);".format(table, column))
    lines += [
        "",
        "DO $$",
        "BEGIN",
        "    IF NOT EXISTS (SELECT 1 FROM timescaledb_information.compression_settings "
        "WHERE hypertable_name = '{}') THEN".format(table),
        "        ALTER TABLE {} SET (".format(table),
        "            timescaledb.compress,",
        "            timescaledb.compress_segmentby = 'entity, type, period, unit',",
        "            timescaledb.compress_orderby = 'time DESC');",
        "        PERFORM add_compression_policy('{}', INTERVAL '1 year', if_not_exists => TRUE);".format(table),
        "    END IF;",
        "END $$;",
    ]
    if retention:
        lines += [
            "",
            "SELECT add_retention_policy('{}', INTERVAL '{}', if_not_exists => TRUE);".format(table, retention),
        ]
    return "\n".join(lines) + "\n"


def describe(document, tables_by_path):
    relations = [(relation, tables_by_path[relation.path]) for relation in document.relations]
    return _statements([
        "-- dimensions", _describe_relations(relations),
        "-- measures", _describe_measures(relations, tables_by_path),
        "-- entities", _describe_entities(relations)])


def queries(relations, table, time_column):
    _, _, now = TIME_COLUMNS[time_column]
    vocabulary = [tuple_ for relation in relations for tuple_ in _vocabulary(relation)]
    statements = ["-- {} [{}]".format(relation.path, relation.desc) for relation in relations]
    statements.append(
        "-- every query below is deliberately rich but row bounded, so a paste into psql stays readable")

    statements.append("-- coverage, one row per declared series with its span, density and gap count")
    statements.append("WITH bounds AS (\n{}\n),\ngaps AS (\n{}\n)\n{}".format(
        "\n".join(indent(select(
            [("type", ""), ("period", ""), ("unit", ""), ("entity", ""),
             ("min(time)", "oldest"), ("max(time)", "newest"), ("count(*)", "rows_total")], table,
            group_by=["type", "period", "unit", "entity"]))),
        "\n".join(indent(select(
            [("type", ""), ("period", ""), ("unit", ""), ("entity", ""),
             ("count(*) FILTER (WHERE step > expected)", "gaps_total")],
            "(\n{}\n) AS stepped".format("\n".join(indent(select(
                [("type", ""), ("period", ""), ("unit", ""), ("entity", ""),
                 ("time - lag(time) OVER (PARTITION BY type, period, unit, entity ORDER BY time)", "step"),
                 ("INTERVAL '1 day'", "expected")], table)))),
            group_by=["type", "period", "unit", "entity"]))),
        select([("b.type", ""), ("b.period", ""), ("b.unit", ""), ("count(*)", "entities"),
                ("sum(b.rows_total)", "rows_total"), ("min(b.oldest)", "oldest"),
                ("max(b.newest)", "newest"), ("sum(g.gaps_total)", "gaps_total")],
               "bounds AS b JOIN gaps AS g USING (type, period, unit, entity)",
               group_by=["b.type", "b.period", "b.unit"],
               order_by=["b.type", "b.period", "b.unit"])))

    statements.append("-- latest reading per declared series, with its rank against the trailing year")
    statements.append(select(
        [("type", ""), ("period", ""), ("unit", ""), ("entity", ""), ("time", ""), ("value", ""),
         ("percent_rank() OVER (PARTITION BY type, period, unit, entity ORDER BY value)", "pct_rank_year")],
        table, ["time >= {} - INTERVAL '1 year'".format(now)],
        distinct_on=["type", "period", "unit", "entity"],
        order_by=["type", "period", "unit", "entity", "time DESC"]))

    statements.append("-- monthly distribution per series, quartiles and swing, last year only")
    statements.append(select(
        [("time_bucket('1 month', time)", "bucket"), ("type", ""), ("period", ""), ("unit", ""),
         ("count(*)", "rows_total"), ("avg(value)", "mean"),
         ("percentile_cont(0.25) WITHIN GROUP (ORDER BY value)", "p25"),
         ("percentile_cont(0.50) WITHIN GROUP (ORDER BY value)", "median"),
         ("percentile_cont(0.75) WITHIN GROUP (ORDER BY value)", "p75"),
         ("max(value) - min(value)", "swing")],
        table, ["time >= {} - INTERVAL '1 year'".format(now)],
        group_by=["bucket", "type", "period", "unit"],
        order_by=["bucket DESC", "type", "period", "unit"], limit=50))

    statements.append("-- biggest movers, each series compared against its own trailing 30 reading mean")
    statements.append("WITH trailing_mean AS (\n{}\n)\n{}".format(
        "\n".join(indent(select(
            [("type", ""), ("period", ""), ("unit", ""), ("entity", ""), ("time", ""), ("value", ""),
             ("avg(value) OVER (PARTITION BY type, period, unit, entity ORDER BY time "
              "ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING)", "mean_30")],
            table, ["time >= {} - INTERVAL '90 days'".format(now)]))),
        select([("type", ""), ("period", ""), ("unit", ""), ("entity", ""), ("time", ""), ("value", ""),
                ("mean_30", ""), ("value - mean_30", "drift")],
               "trailing_mean", ["mean_30 IS NOT NULL"],
               order_by=["abs(value - mean_30) DESC"], limit=20)))

    statements.append("-- staleness, series whose newest reading is behind the table as a whole")
    statements.append(select(
        [("type", ""), ("period", ""), ("unit", ""), ("entity", ""), ("max(time)", "newest"),
         ("(SELECT max(time) FROM {}) - max(time)".format(table), "behind")],
        table, group_by=["type", "period", "unit", "entity"],
        having=["max(time) < (SELECT max(time) FROM {})".format(table)],
        order_by=["behind DESC"], limit=20))

    for metric_type, period, unit in vocabulary:
        statements.append("-- {} [{}] in [{}], yearly shape across entities".format(metric_type, period, unit))
        statements.append(select(
            [("time_bucket('1 month', time)", "bucket"), ("entity", ""), ("avg(value)", "mean"),
             ("min(value)", "low"), ("max(value)", "high"), ("count(*)", "rows_total")],
            table, ["type = '{}'".format(metric_type), "period = '{}'".format(period),
                    "unit = '{}'".format(unit), "time >= {} - INTERVAL '1 year'".format(now)],
            group_by=["bucket", "entity"], order_by=["bucket DESC", "entity"], limit=30))
    return _statements(statements)


def verify(document, tables_by_path):
    statements = ["-- declared vocabulary against what the service actually wrote, "
                  "rows come back only on drift"]
    for table in sorted(set(tables_by_path.values())):
        relations = [relation for relation in document.relations if tables_by_path[relation.path] == table]
        declared = [tuple_ for relation in relations for tuple_ in _vocabulary(relation)]
        values = ",\n".join("    ('{}', '{}', '{}')".format(*tuple_) for tuple_ in declared)
        statements.append(select(
            [("'{}'".format(table), "relation"), ("coalesce(d.type, o.type)", "type"),
             ("coalesce(d.period, o.period)", "period"), ("coalesce(d.unit, o.unit)", "unit"),
             ("CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END", "fault")],
            "(VALUES\n{}\n) AS d(type, period, unit)\n"
            "FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM {}) AS o\n"
            "    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit".format(values, table),
            ["d.type IS NULL OR o.type IS NULL"]))
        entities_all = [entity for relation in relations for entity in relation.entities]
        if entities_all and all(relation.entities for relation in relations):
            statements.append(select(
                [("'{}'".format(table), "relation"), ("entity", ""), ("count(*)", "rows_total"),
                 ("'undeclared'", "fault")],
                table, [literals("entity", sorted(set(entities_all)))], group_by=["entity"]))
    return _statements(statements)


def observe(document, tables_by_path):
    statements = ["-- open entity domains, printed for eyeballing and never asserted"]
    for table in sorted(set(tables_by_path.values())):
        relations = [relation for relation in document.relations if tables_by_path[relation.path] == table]
        if all(relation.entities for relation in relations):
            continue
        statements.append(select(
            [("'{}'".format(table), "relation"), ("entity", ""), ("count(*)", "rows_total"),
             ("max(time)", "last_seen")], table, group_by=["entity"], order_by=["entity"]))
    return _statements(statements)


def describe_script(module_name, dialect):
    return script(module_name, dialect, "describe", "print what the production tables actually carry", connect(module_name), """
printf '\\n'
SCHEMA_ECHO=false SCHEMA_ACTION=Describe SCHEMA_TARGET="${{POSTGRES_SERVICE_PROD}}" \\
  query_file "${{ROOT_DIR}}/sql/describe.sql"
""".format(module_name))


def query_script(module_name, dialect):
    return script(module_name, dialect, "query", "run the generated query for every declared relation", connect(module_name), """
printf '\\nSchema query [%s] against [%s]\\n\\n' "{}" "${{POSTGRES_SERVICE_PROD}}"
FAULTS=0
for SQL_FILE in "${{ROOT_DIR}}"/sql/query_*.sql; do
  printf '\\n== %s ==\\n' "$(basename "${{SQL_FILE}}")"
  query_file "${{SQL_FILE}}" || FAULTS=$((FAULTS + 1))
done
[ "${{FAULTS}}" = 0 ]
""".format(module_name))


def verify_script(module_name, dialect):
    return script(module_name, dialect, "verify", "assert production matches the declaration", connect(module_name), """
printf '\\nSchema verify [%s] against [%s]\\n\\n' "{}" "${{POSTGRES_SERVICE_PROD}}"

if ! FAULTS="$("${{PSQL[@]}}" -v ON_ERROR_STOP=1 -t -A -f "${{ROOT_DIR}}/sql/verify.sql" | grep -c .)"; then
  FAULTS=0
fi
if ! OUTPUT="$("${{PSQL[@]}}" -v ON_ERROR_STOP=1 -f "${{ROOT_DIR}}/sql/verify.sql" 2>&1)"; then
  fail "${{ROOT_DIR}}/sql/verify.sql" "${{OUTPUT}}"
  exit 1
fi
if [ "${{FAULTS}}" != "0" ]; then
  query_file "${{ROOT_DIR}}/sql/verify.sql" || exit 1
fi

printf '\\nSchema verify [%s] observed entities of open domains\\n\\n' "{}"
query_file "${{ROOT_DIR}}/sql/observe.sql" || exit 1

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema verify [%s] found [%s] fault row(s)\\n' "{}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema verify [%s] found no drift\\n' "{}"
""".format(module_name, module_name, module_name, module_name, module_name))


def discover_script(module_name, dialect, tables):
    return script(module_name, dialect, "discover", "draft a declaration from what production carries", connect(module_name), """
printf '\\nSchema discover [%s] against [%s], a drafting aid that is never an input to the build\\n\\n' "{}" "${{POSTGRES_SERVICE_PROD}}"
{}
""".format(module_name, "\n".join(
        'printf \'\\n== %s ==\\n\' "{0}"\nquery_one "SELECT DISTINCT entity, type, period, unit '
        'FROM {0} ORDER BY entity, type, period, unit" || exit 1'.format(table) for table in tables)))


def applier_script(module_name):
    return """
#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

set -euo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")/database"

PSQL=(psql -h "${{DATABASE_HOST}}" -p "${{DATABASE_PORT}}" -U "${{DATABASE_USER}}" -d "${{DATABASE_NAME}}")
export PGPASSWORD="${{DATABASE_PASSWORD}}"

printf '\\nSchema apply [%s] against [%s]\\n\\n' "{}" "${{DATABASE_HOST}}"
for SQL_FILE in "${{ROOT_DIR}}"/*.sql; do
  printf '%s\\n' "$(basename "${{SQL_FILE}}")"
  "${{PSQL[@]}}" -v ON_ERROR_STOP=1 -f "${{SQL_FILE}}"
done
""".format(module_name).strip() + "\n"


def _describe_relations(relations):
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"), ("'{}'".format(_dimension(relation)), "dimension"),
                ("'{}'".format(relation.cadence), "cadence"),
                ("{}".format(len(relation.measures)), "measures"),
                ("{}".format(len(relation.persisted)), "persisted"),
                ("'{}'".format(_declared_entities(relation)), "declared"),
                ("count(DISTINCT entity)" if relation.subject else "'{}'".format(NULL),
                 "observed"),
                ("count(*)", "rows"), ("min(time)", "oldest"), ("max(time)", "newest")],
               table, [_types(relation, negate=False)])
        for relation, table in relations) + "\nORDER BY relation"


def _describe_measures(relations, tables_by_path):
    arms = []
    for table in sorted(set(tables_by_path.values())):
        declared = set()
        for relation, owner in relations:
            if owner != table:
                continue
            persisted = {measure.key for measure in relation.persisted}
            for measure in relation.measures:
                period = measure.period or relation.cadence or NULL
                unit = measure.unit or NULL
                columns = _declared_measure(relation, measure, unit, period)
                if measure.key not in persisted:
                    arms.append(select(columns + _absent_measure(), PLACEHOLDER))
                    continue
                declared.add(measure.key)
                arms.append(select(columns + [
                    ("CASE WHEN count(*) > 0 THEN '{}' ELSE '{}' END".format(YES, NO), "observed"),
                    ("CAST(count(*) AS VARCHAR)", "rows"),
                    ("CAST(min(time) AS VARCHAR)", "oldest"),
                    ("CAST(max(time) AS VARCHAR)", "newest")], table,
                    ["type = '{}'".format(measure.key), "period = '{}'".format(period),
                     "unit = '{}'".format(unit)]))
        arms.append(select(
            [("'{}'".format(NULL), "relation"), ("type", "measure"), ("'{}'".format(NULL), "kind"),
             ("unit", ""), ("period", ""), ("'{}'".format(NULL), "persisted"),
             ("'{}'".format(YES), "observed"), ("CAST(count(*) AS VARCHAR)", "rows"),
             ("CAST(min(time) AS VARCHAR)", "oldest"), ("CAST(max(time) AS VARCHAR)", "newest")],
            table, [literals("type", sorted(declared))], group_by=["type", "unit", "period"]))
    return "\nUNION ALL\n".join(arms) + "\nORDER BY relation, measure, unit, period"


def _declared_measure(relation, measure, unit, period):
    return [("'{}'".format(relation.path), "relation"), ("'{}'".format(measure.key), "measure"),
            ("'{}'".format(measure.kind), "kind"), ("'{}'".format(unit), "unit"),
            ("'{}'".format(period), "period"),
            ("'{}'".format(YES if measure.persist else NO), "persisted")]


def _absent_measure():
    return [("'{}'".format(NO), "observed")] + \
        [("'{}'".format(NULL), key) for key in ("rows", "oldest", "newest")]


def _describe_entities(relations):
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"),
                ("'{}'".format(_dimension(relation)), "dimension"), ("entity", ""),
                (_declared(relation), "declared"), ("count(*)", "rows"),
                ("min(time)", "oldest"), ("max(time)", "newest")],
               table, [_types(relation, negate=False)],
               group_by=_grouping("entity", _declared(relation)))
        for relation, table in relations) + "\nORDER BY relation, entity"


def _declared_entities(relation):
    return len(relation.entities) if relation.entities else NULL


def _dimension(relation):
    return "/".join(dimension.key + (SUBJECT if dimension.subject else "")
                    for dimension in relation.dimensions) or NULL


def _types(relation, negate=True):
    return literals("type", sorted({metric_type for metric_type, _, _ in _vocabulary(relation)}),
                    negate=negate)


def _grouping(entity, declared):
    return [entity] + ([declared] if declared.startswith("CASE") else [])


def _declared(relation):
    if not relation.entities or relation.subject is None:
        return "'{}'".format(NULL)
    return "CASE WHEN {} THEN '{}' ELSE '{}' END".format(
        literals("entity", relation.entities, negate=False), YES, NO)


def _vocabulary(relation):
    seen, vocabulary = set(), []
    for measure in relation.measures:
        if not measure.persist:
            continue
        tuple_ = (measure.key, measure.period or relation.cadence, measure.unit)
        if tuple_ in seen:
            continue
        seen.add(tuple_)
        vocabulary.append(tuple_)
    return vocabulary


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
