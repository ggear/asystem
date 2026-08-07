import json
import os
import shutil
from os.path import abspath, exists, join

from asystem.schema import (BUCKET, NULL, RUNNER, aggregations, banner, bucketed,
                            declared_entity,
                            declared_measure, describe_runner, dimension_label, grouping_keys, labels,
                            literals, parted, query_runner, recent, render_statements, select,
                            verify_runner, vocabulary)

DIALECT = "postgres"
TARGET = "POSTGRES_SERVICE_PROD"

TIME_COLUMNS = {
    "date": ("DATE", "INTERVAL '10 years'", "CURRENT_DATE", "1"),
    "timestamp": ("TIMESTAMPTZ", "INTERVAL '1 month'", "now()", "INTERVAL '1 day'"),
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


def artifacts(document, module_name, time_column="timestamp", retention=None):
    if time_column not in TIME_COLUMNS:
        raise ValueError("Build generate script [{}] unknown time_column [{}] expected one of {}"
                         .format(module_name, time_column, list(TIME_COLUMNS)))
    _validate(document, module_name)
    written = {}
    for table, relations in _tabled(document).items():
        written["model/{}.sql".format(table)] = (leaf(relations, table, time_column, retention), False)
        written["query/query_{}.sql".format(table)] = (queries(relations, table, time_column), False)
    written["query/describe.sql"] = (describe(document), False)
    written["query/verify.sql"] = (verify(document), False)
    written["describe.sh"] = (describe_runner(module_name, DIALECT, TARGET, connect(module_name)), True)
    written["query.sh"] = (query_runner(module_name, DIALECT, TARGET, connect(module_name)), True)
    written["verify.sh"] = (verify_runner(module_name, DIALECT, TARGET, connect(module_name)), True)
    return written


def ship(document, module_name, module_root, schemas_dir, time_column="timestamp"):
    image_dir = abspath(join(module_root, "src/main/resources/image/database"))
    if exists(image_dir):
        shutil.rmtree(image_dir)
    os.makedirs(image_dir, exist_ok=True)
    for table in sorted(_tabled(document)):
        source_path = abspath(join(schemas_dir, DIALECT, "model", "{}.sql".format(table)))
        target_path = join(image_dir, "{}.sql".format(table))
        shutil.copyfile(source_path, target_path)
        columns_path = join(image_dir, "{}.json".format(table))
        with open(columns_path, 'w') as columns_file:
            columns_file.write(json.dumps(columns(table, time_column), indent=2) + "\n")
        print("Build generate script [{}] database table [{}] shipped to [{}] and [{}]"
              .format(module_name, table, target_path, columns_path))
    applier_path = abspath(join(module_root, "src/main/resources/image/database.sh"))
    with open(applier_path, 'w') as applier_file:
        applier_file.write(applier_script(module_name))
    os.chmod(applier_path, 0o750)
    print("Build generate script [{}] database applier persisted to [{}]".format(module_name, applier_path))


def connect(module_name):
    return RESOLVE % {"prefix": module_name.upper(), "module": module_name} + CONNECT


def columns(table, time_column):
    column_type, _, _, _ = TIME_COLUMNS[time_column]
    return {
        "table": table,
        "time": {"column": "time", "type": column_type},
        "dimensions": ["entity", "type", "period", "unit"],
        "value": {"column": "value", "type": "FLOAT8"},
        "strategy": "staging" if time_column == "date" else "direct",
    }


def leaf(relations, table, time_column, retention):
    column_type, chunk_interval, _, _ = TIME_COLUMNS[time_column]
    lines = [banner("--"), ""]
    for relation in relations:
        lines += vocabulary(relation, "--")
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


def describe(document):
    relations = [(relation, table) for table, tabled in _tabled(document).items() for relation in tabled]
    return render_statements([
        "-- dimensions", _describe_relations(relations),
        "-- measures", _describe_measures(document),
        "-- entities", _describe_entities(relations)])


def queries(relations, table, time_column):
    _, _, now, _ = TIME_COLUMNS[time_column]
    floor = BUCKET if time_column == "date" else None
    statements = []
    for relation in relations:
        if not relation.persisted:
            statements.append("-- {} [{}] declares no persisted measure, so nothing is written for it"
                              .format(relation.path, relation.description))
            continue
        bucket = bucketed(relation.cadence, floor)
        heading = "-- {} [{}] every {}, bucketed [{}] across the newest two buckets".format(
            relation.path, relation.description, relation.cadence, bucket)
        measured_selectors, measured_keys = [], {}
        for measure in relation.measures:
            if not measure.persist or measure.kind == "str":
                continue
            filtered = _filtered(relation, measure)
            for function, suffix in aggregations(measure, relation.cadence):
                alias = "_".join(part for part in (_named(relation, measure), suffix) if part)
                measured_selectors.append((_aggregate(function, filtered), alias))
                measured_keys[alias] = measure.key
        if not measured_selectors:
            continue
        subject = [relation.subject.key] if relation.subject else []
        label = labels(["bucket"] + subject + [alias for _, alias in measured_selectors], ["time"])
        parts = parted(measured_selectors, len(subject) + 1, {alias: label[alias].strip('"') for _, alias in measured_selectors})
        for index, part in enumerate(parts):
            statements.append(heading)
            statements.append("-- part {} of {}:".format(index + 1, len(parts)))
            selectors = [("time_bucket('{}', time)".format(bucket), label["bucket"])]
            selectors += [("entity", label[key]) for key in subject]
            selectors += [(expression, label[alias]) for expression, alias in part]
            grouping = [label["bucket"]] + ["entity" for _ in subject]
            keys = {measured_keys[alias] for _, alias in part}
            statements.append(select(selectors, table,
                                     [_types(relation, negate=False, keys=keys, width=None)]
                                     + recent(table, bucket, now),
                                     group_by=grouping, order_by=grouping))
    return render_statements(statements)


def verify(document):
    statements = ["-- declared vocabulary against what the service actually wrote, rows come back only on drift"]
    for table, relations in _tabled(document).items():
        declared = [(relation.path,) + tuple_ for relation in relations for tuple_ in _vocabulary(relation)]
        values = ",\n".join("    ('{}', '{}', '{}', '{}')".format(*tuple_) for tuple_ in declared)
        statements.append(select(
            [("coalesce(d.relation, '{}')".format(table), "relation"), ("coalesce(d.type, o.type)", "measure"),
             ("coalesce(d.period, o.period)", "period"), ("coalesce(d.unit, o.unit)", "unit"),
             ("CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END", "fault")],
            "(VALUES\n{}\n) AS d(relation, type, period, unit)\n"
            "FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM {}) AS o\n"
            "    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit".format(values, table),
            ["d.type IS NULL OR o.type IS NULL"], order_by=["fault", "measure"]))
    return render_statements(statements)


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
        select([("'{}'".format(relation.path), "relation"), ("'{}'".format(dimension_label(relation)), "dimension"),
                ("{}".format(len(relation.measures)), "measures"),
                ("'{}'".format(relation.cadence), "cadence"),
                ("count(*)", "rows"), ("min(time)", "oldest"), ("max(time)", "newest")],
               table, [_types(relation, negate=False)])
        for relation, table in relations) + "\nORDER BY rows DESC"


def _describe_measures(document):
    arms = []
    for table, relations in _tabled(document).items():
        declared = set()
        for relation in relations:
            persisted = {measure.key for measure in relation.persisted}
            for measure in relation.measures:
                period = measure.period or relation.cadence or NULL
                unit = measure.unit or NULL
                if measure.key not in persisted:
                    continue
                selectors = declared_measure(relation, measure, unit, period)
                declared.add(measure.key)
                arms.append(select(selectors + [
                    ("count(*)", "rows"),
                    ("CAST(min(time) AS VARCHAR)", "oldest"),
                    ("CAST(max(time) AS VARCHAR)", "newest")], table,
                    ["type = '{}'".format(measure.key), "period = '{}'".format(period),
                     "unit = '{}'".format(unit)]))
        arms.append(select(
            [("'{}'".format(NULL), "relation"), ("type", "measure"), ("'{}'".format(NULL), "kind"),
             ("unit", ""), ("period", ""), ("count(*)", "rows"),
             ("CAST(min(time) AS VARCHAR)", "oldest"), ("CAST(max(time) AS VARCHAR)", "newest")],
            table, [literals("type", sorted(declared))], group_by=["type", "unit", "period"]))
    return "\nUNION ALL\n".join(arms) + "\nORDER BY rows DESC NULLS LAST"



def _describe_entities(relations):
    return "\nUNION ALL\n".join(
        select([("'{}'".format(relation.path), "relation"),
                ("'{}'".format(dimension_label(relation)), "dimension"), ("entity", ""),
                (declared_entity(relation, "entity"), "declared"), ("count(*)", "rows"),
                ("min(time)", "oldest"), ("max(time)", "newest")],
               table, [_types(relation, negate=False)],
               group_by=grouping_keys("entity", declared_entity(relation, "entity")))
        for relation, table in relations) + "\nORDER BY rows DESC"




def _tabled(document):
    tabled = {}
    for relation in document.relations:
        if relation.persisted:
            tabled.setdefault(relation.plugin, []).append(relation)
    return {table: tabled[table] for table in sorted(tabled)}


def _validate(document, module_name):
    for table, relations in _tabled(document).items():
        keys = {}
        for relation in relations:
            for measure in relation.persisted:
                if measure.key in keys and keys[measure.key] != relation.path:
                    raise ValueError(
                        "Build generate script [{}] relations [{}] and [{}] share the table [{}] and the measure "
                        "[{}] so neither can be told apart by type, rename one measure or fold them together"
                        .format(module_name, keys[measure.key], relation.path, table, measure.key))
                keys[measure.key] = relation.path


def _types(relation, negate=True, keys=None, width: int | None = 92):
    types = {metric_type for metric_type, _, _ in _vocabulary(relation)}
    return literals("type", sorted(types if keys is None else types & keys), negate=negate, width=width)




def _vocabulary(relation):
    seen, series = set(), []
    for measure in relation.measures:
        if not measure.persist:
            continue
        tuple_ = (measure.key, measure.period or relation.cadence, measure.unit)
        if tuple_ in seen:
            continue
        seen.add(tuple_)
        series.append(tuple_)
    return series


def _named(relation, measure):
    name = measure.key.replace("-", "_")
    if len([other for other in relation.measures if other.key == measure.key]) > 1:
        name = "{}_{}".format(name, measure.period or relation.cadence)
    return name


def _filtered(relation, measure):
    period = measure.period or relation.cadence
    keyed = [other for other in relation.measures if other.key == measure.key]
    periods = {other.period or relation.cadence for other in keyed}
    units = {other.unit for other in keyed if (other.period or relation.cadence) == period}
    predicates = ["type = '{}'".format(measure.key)]
    if len(periods) > 1:
        predicates.append("period = '{}'".format(period))
    if len(units) > 1:
        predicates.append("unit = '{}'".format(measure.unit))
    return " AND ".join(predicates)


def _aggregate(function, predicate):
    if function == "last":
        return _rounded("last(value, time) FILTER (WHERE {})".format(predicate))
    return _rounded("{}(value) FILTER (WHERE {})".format(function, predicate))


def _rounded(expression):
    return "round({}::numeric, 1)".format(
        expression if expression.isidentifier() else "({})".format(expression))


