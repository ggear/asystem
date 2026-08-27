import json
import os
import shutil
from os.path import abspath, exists, join

from asystem.schema.query import (
    BUCKET,
    NULL,
    PENDING,
    SchemaDialect,
    banner,
    declared_entity,
    describe_statements,
    literals,
    query_statements,
    recent,
    render_statements,
    select,
    vocabulary,
)
from asystem.schema.runner import RUNNER, describe_runner, mutate_runner, query_runner, resolved, verify_runner

DIALECT = "postgres"
SHIPPED = "database"
KINDS = ("float", "int", "bool")
TARGET = "POSTGRES_SERVICE_PROD"

TIME_COLUMNS = {
    "date": ("DATE", "INTERVAL '10 years'", "CURRENT_DATE", "1"),
    "timestamp": ("TIMESTAMPTZ", "INTERVAL '1 month'", "now()", "INTERVAL '1 day'"),
}

CONNECT = """
PSQL=(psql -h "${POSTGRES_SERVICE_PROD}" -p "${POSTGRES_API_PORT}" -U "${DATABASE_USER}" -d "${DATABASE_NAME}")
export PGPASSWORD="${DATABASE_PASSWORD}"
export PGTZ="${TZ:-UTC}"

query() {
  "${PSQL[@]}" -q -t -A -v ON_ERROR_STOP=1 -c "SELECT row_to_json(result) FROM ($1) AS result" 2>&1
}
""" + RUNNER


def artifacts(document, module_name, options):
    if options.time_column not in TIME_COLUMNS:
        raise ValueError("Build generate script [{}] unknown time_column [{}] expected one of {}"
                         .format(module_name, options.time_column, list(TIME_COLUMNS)))
    _validate(document, module_name)
    dialect = _dialect(options.time_column, options.timezone)
    written = {}
    for table, relations in _tabled(document).items():
        written["model/{}.sql".format(table)] = (leaf(relations, table, options), False)
        written["query/{}.sql".format(table)] = (query_statements(relations, dialect), False)
    written["describe.sh"] = (describe_runner(module_name, DIALECT, TARGET, connect(module_name),
                                              describe_statements(document, dialect)), True)
    written["query.sh"] = (query_runner(module_name, DIALECT, TARGET, connect(module_name)), True)
    written["verify.sh"] = (verify_runner(module_name, DIALECT, TARGET, connect(module_name),
                                          verify(document, options.rename, options.drop)), True)
    for table, statements in mutate(document, options.rename).items():
        written["mutate/rename/{}.sql".format(table)] = (statements, False)
    for table, statements in retire(document, options.drop).items():
        written["mutate/drop/{}.sql".format(table)] = (statements, False)
    written["mutate.sh"] = (mutate_runner(module_name, DIALECT, TARGET, connect(module_name),
                                          _mutate_body(module_name)), True)
    return written


def ship(document, module_name, module_root, schemas_dir, options):
    image_dir = abspath(join(module_root, "src/main/resources/image", SHIPPED))
    applier_path = abspath(join(module_root, "src/main/resources/image", SHIPPED + ".sh"))
    if exists(image_dir):
        shutil.rmtree(image_dir)
    if exists(applier_path):
        os.remove(applier_path)
    tables = sorted(_tabled(document))
    if not tables:
        return
    os.makedirs(image_dir, exist_ok=True)
    for table in tables:
        source_path = abspath(join(schemas_dir, DIALECT, "model", "{}.sql".format(table)))
        target_path = join(image_dir, "{}.sql".format(table))
        shutil.copyfile(source_path, target_path)
        columns_path = join(image_dir, "{}.json".format(table))
        with open(columns_path, 'w') as columns_file:
            columns_file.write(json.dumps(columns(table, options.time_column), indent=2) + "\n")
        print("Build generate script [{}] database table [{}] shipped to [{}] and [{}]"
              .format(module_name, table, target_path, columns_path))
    if not options.applier:
        return
    with open(applier_path, 'w') as applier_file:
        applier_file.write(applier_script(module_name))
    os.chmod(applier_path, 0o750)
    print("Build generate script [{}] database applier persisted to [{}]".format(module_name, applier_path))


def connect(module_name):
    prefix = module_name.upper()
    return resolved(module_name, (
        ("DATABASE_USER", ("{}_DATABASE_USER".format(prefix), "POSTGRES_USER_{}".format(prefix))),
        ("DATABASE_NAME", ("{}_DATABASE_NAME".format(prefix), "POSTGRES_DATABASE_{}".format(prefix))),
        ("DATABASE_PASSWORD", ("{}_DATABASE_PASSWORD".format(prefix), "POSTGRES_KEY_{}".format(prefix))),
    )) + CONNECT


def columns(table, time_column):
    column_type, _, _, _ = TIME_COLUMNS[time_column]
    return {
        "table": table,
        "time": {"column": "time", "type": column_type},
        "dimensions": ["entity", "type", "period", "unit"],
        "value": {"column": "value", "type": "FLOAT8"},
        "strategy": "staging" if time_column == "date" else "direct",
    }


def leaf(relations, table, options):
    column_type, chunk_interval, _, _ = TIME_COLUMNS[options.time_column]
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
    if options.retention:
        lines += [
            "",
            "SELECT add_retention_policy('{}', INTERVAL '{}', if_not_exists => TRUE);".format(table, options.retention),
        ]
    return "\n".join(lines) + "\n"


def verify(document, rename=None, drop=None):
    statements = ["-- declared vocabulary against what the service actually wrote, rows come back only on drift"]
    retired = sorted(set(rename or {}) | set(drop or ()))
    observed = [literals("type", retired)] if retired else []
    for table, relations in _tabled(document).items():
        declared = [(relation.path,) + tuple_ for relation in relations for tuple_ in _vocabulary(relation)]
        values = ",\n".join("    ('{}', '{}', '{}', '{}')".format(*tuple_) for tuple_ in declared)
        statements.append(select(
            [("coalesce(d.relation, '{}')".format(table), "relation"), ("coalesce(d.type, o.type)", "measure"),
             ("coalesce(d.period, o.period)", "period"), ("coalesce(d.unit, o.unit)", "unit"),
             ("CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END", "fault")],
            "(VALUES\n{}\n) AS d(relation, type, period, unit)\n"
            "FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM {}{}) AS o\n"
            "    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit".format(
                values, table, " WHERE " + " AND ".join(observed) if observed else ""),
            ["d.type IS NULL OR o.type IS NULL"], order_by=["fault", "measure"]))
    if retired:
        statements.append("-- retired measures still carried, reported as [{}] and warned about rather than failing"
                          .format(PENDING))
        for table in sorted(_tabled(document)):
            statements.append(select(
                [("'{}'".format(table), "relation"), ("type", "measure"), ("period", "period"), ("unit", "unit"),
                 ("'{}'".format(PENDING), "fault")],
                "(SELECT DISTINCT type, period, unit FROM {}) AS o".format(table),
                [literals("type", retired, negate=False)], order_by=["measure"]))
    return render_statements(statements)


def applier_script(module_name):
    return """
#!/usr/bin/env bash
{banner}

set -euo pipefail

ROOT_DIR="$(dirname "$(readlink -f "$0")")/{shipped}"

PSQL=(psql -h "${{DATABASE_HOST}}" -p "${{DATABASE_PORT}}" -U "${{DATABASE_USER}}" -d "${{DATABASE_NAME}}")
export PGPASSWORD="${{DATABASE_PASSWORD}}"

printf '\\nSchema apply [%s] against [%s]\\n' "{module}" "${{DATABASE_HOST}}"
for SQL_FILE in "${{ROOT_DIR}}"/*.sql; do
  printf -- '\\n-- %s\\n\\n' "$(basename "${{SQL_FILE}}")"
  "${{PSQL[@]}}" -v ON_ERROR_STOP=1 -f "${{SQL_FILE}}"
done
""".format(banner=banner(), shipped=SHIPPED, module=module_name).strip() + "\n"


def mutate(document, rename):
    written = {}
    sources = {new: old for old, new in (rename or {}).items() if new}
    for table, relations in _tabled(document).items():
        statements = []
        for relation in relations:
            for measure in relation.carried(KINDS):
                source = sources.get(measure.key)
                if source is None:
                    continue
                statements.append(
                    "-- rewrite the renamed [{}] as [{}], idempotent and touching no rows once run".format(
                        source, measure.key))
                statements.append("UPDATE {}\nSET type = '{}'\nWHERE type = '{}'".format(
                    table, measure.key, source))
        if statements:
            written[table] = render_statements(statements)
    return written


def retire(document, drop):
    written = {}
    if not drop:
        return written
    for table in sorted(_tabled(document)):
        written[table] = render_statements([
            "-- delete the dropped measures, idempotent and touching no rows once run",
            "DELETE FROM {}\nWHERE {}".format(table, literals("type", sorted(drop), negate=False))])
    return written


def _mutate_body(module_name):
    return """
printf '\\nSchema mutate [%s] against [%s]\\n' "{module}" "${{{target}}}"
FAULTS=0
for SQL_FILE in "${{ROOT_DIR}}"/mutate/rename/*.sql "${{ROOT_DIR}}"/mutate/drop/*.sql; do
  [ -e "${{SQL_FILE}}" ] || continue
  SCHEMA_LABEL="$(dirname "${{SQL_FILE}}" | xargs basename)/$(basename "${{SQL_FILE}}")"
  query_sql < "${{SQL_FILE}}" || FAULTS=$((FAULTS + 1))
done

if [ "${{FAULTS}}" != "0" ]; then
  printf '\\nSchema mutate [%s] failed [%s] statement(s)\\n' "{module}" "${{FAULTS}}" >&2
  exit 1
fi
printf '\\nSchema mutate [%s] rewrote and deleted with no faults\\n' "{module}"
""".format(target=TARGET, module=module_name)


def _dialect(time_column, zone=""):
    _, _, now, _ = TIME_COLUMNS[time_column]
    return SchemaDialect(
        source=lambda relation: relation.plugin,
        predicates=lambda relation: [_types(relation, negate=False)],
        groups=lambda document: list(_tabled(document).items()),
        measured=lambda relation, measure: [
            "type = '{}'".format(measure.key),
            "period = '{}'".format(relation.span(measure) or NULL),
            "unit = '{}'".format(measure.unit or NULL)],
        counted=lambda _: "count(*)",
        stamped=lambda function, _: "CAST({}(time) AS VARCHAR)".format(function),
        entity=lambda _: "entity",
        declared=lambda relation: declared_entity(relation, "entity"),
        undeclared=lambda table, _, declared, __: _describe_undeclared(table, declared),
        bucket=lambda bucket: _binned(bucket, zone if time_column != "date" else ""),
        subject=lambda relation: [("entity", relation.subject.key)] if relation.subject else [],
        alias=_named,
        aggregate=lambda relation, measure, function: _aggregate(function, _filtered(relation, measure)),
        windowed=lambda relation, keys, bucket: [_types(relation, negate=False, keys=keys, width=None)]
        + recent(relation.plugin, bucket, now),
        observed="count(DISTINCT time)",
        kinds=KINDS,
        floor=BUCKET if time_column == "date" else "")


def _describe_undeclared(table, declared):
    return select(
        [("'{}'".format(NULL), "relation"), ("type", "measure"), ("'{}'".format(NULL), "kind"),
         ("unit", "unit"), ("period", "period"), ("count(*)", "rows"),
         ("CAST(min(time) AS VARCHAR)", "oldest"), ("CAST(max(time) AS VARCHAR)", "newest")],
        table, [literals("type", declared)], group_by=["type", "unit", "period"])


def _tabled(document):
    tabled = {}
    for relation in document.relations:
        if relation.carried(KINDS):
            tabled.setdefault(relation.plugin, []).append(relation)
    return {table: tabled[table] for table in sorted(tabled)}


def _validate(document, module_name):
    for table, relations in _tabled(document).items():
        keys = {}
        for relation in relations:
            for measure in relation.carried(KINDS):
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
    for measure in relation.carried(KINDS):
        tuple_ = (measure.key, relation.span(measure), measure.unit)
        if tuple_ in seen:
            continue
        seen.add(tuple_)
        series.append(tuple_)
    return series


def _named(relation, measure):
    name = measure.key.replace("-", "_")
    if len([other for other in relation.measures if other.key == measure.key]) > 1:
        name = "{}_{}".format(name, relation.span(measure))
    return name


def _filtered(relation, measure):
    period = relation.span(measure)
    keyed = [other for other in relation.measures if other.key == measure.key]
    periods = {relation.span(other) for other in keyed}
    units = {other.unit for other in keyed if relation.span(other) == period}
    predicates = ["type = '{}'".format(measure.key)]
    if len(periods) > 1:
        predicates.append("period = '{}'".format(period))
    if len(units) > 1:
        predicates.append("unit = '{}'".format(measure.unit))
    return " AND ".join(predicates)


def _aggregate(function, predicate):
    if function == "count":
        return "count(*) FILTER (WHERE {})".format(predicate)
    if function == "distinct":
        return "count(DISTINCT value) FILTER (WHERE {})".format(predicate)
    if function == "last":
        return _rounded("last(value, time) FILTER (WHERE {})".format(predicate))
    return _rounded("{}(value) FILTER (WHERE {})".format(function, predicate))


def _binned(bucket, zone):
    if not zone or zone == "UTC":
        return "time_bucket('{}', time)".format(bucket)
    return "time_bucket('{}', time, '{}')".format(bucket, zone)


def _rounded(expression):
    return "round({}::numeric, 1)".format(
        expression if expression.isidentifier() else "({})".format(expression))
