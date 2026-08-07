import functools
import glob
import inspect
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from os.path import abspath, dirname, join, realpath

import psycopg  # type: ignore[import-untyped]
import pytest
from psycopg import sql as psycopg_sql  # type: ignore[import-untyped]

sys.path.append('../../../main/python')

from wrangle import plugin
from wrangle.plugin import database

TIMEOUT_SECONDS = 10
TIMEOUT_QUERY_SECONDS = 5
TIMEOUT_WRANGLE_RUN_SECONDS = 120

HTTP_PORT = int(os.environ.get("WRANGLE_HTTP_PORT", "32410"))

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

_db_counts_after_run: dict[str, int] = {}

for key, value in list(plugin.load_profile(plugin.get_file(".env")).items()):
    os.environ[key] = value


def test_warmup():
    warmup_succeeded = False
    warmup_started_time = time.time()
    while not warmup_succeeded and (time.time() - warmup_started_time) < TIMEOUT_SECONDS:
        try:
            with connect() as database_connection, database_connection.cursor() as database_cursor:
                # noinspection PyUnresolvedReferences
                database_cursor.execute("SELECT 1")
                query_row: tuple = database_cursor.fetchone() or (None,)
                warmup_succeeded = query_row[0] == 1
        except Exception as exception:
            print(exception)
            print("Waiting for postgres server to come up ...")
            time.sleep(1)
    assert warmup_succeeded is True


def test_schema_ddl_applies_and_is_idempotent():
    for table_name in _database_plugin_tables():
        ddl = _read_generated(join("model", f"{table_name}.sql"))
        assert f"CREATE TABLE IF NOT EXISTS {table_name} (" in ddl
        with open(join(DIR_ROOT, "src/main/resources/image/database", f"{table_name}.sql")) as shipped_file:
            shipped = shipped_file.read()
        assert ddl == shipped, f"generated and shipped DDL differ for [{table_name}]"
        for attempt in ("first", "second"):
            with connect() as database_connection, database_connection.cursor() as database_cursor:
                try:
                    _execute(database_cursor, ddl)
                except Exception as exception:
                    pytest.fail(f"generated DDL for [{table_name}] failed on the {attempt} apply: {exception}")
        with connect() as database_connection, database_connection.cursor() as database_cursor:
            database_cursor.execute(
                "SELECT count(*) FROM timescaledb_information.hypertables WHERE hypertable_name = %s", (table_name,))
            row: tuple = database_cursor.fetchone() or (0,)
            assert row[0] == 1, f"[{table_name}] is not a hypertable after applying the generated DDL"
            database_cursor.execute(
                "SELECT count(*) FROM pg_indexes WHERE tablename = %s AND indexname LIKE %s",
                (table_name, f"{table_name}\\_%\\_time"))
            row = database_cursor.fetchone() or (0,)
            assert row[0] == len(database.database_schema_columns(table_name)["dimensions"]), \
                f"[{table_name}] is missing generated dimension indexes"


def test_schema_statements_execute():
    for sql_name in ("describe.sql", "verify.sql", *[f"query_{table}.sql" for table in _database_plugin_tables()]):
        for statement in _statements(_read_generated(join("query", sql_name))):
            with connect() as database_connection, database_connection.cursor() as database_cursor:
                try:
                    _execute(database_cursor, statement)
                    database_cursor.fetchall()
                except Exception as exception:
                    pytest.fail(f"generated statement in [{sql_name}] failed: {exception}\n{statement}")


def test_run():
    counters = run_wrangle_once()
    assert counters["Data"]["Delta Rows"] > 0
    assert counters["Data"]["Current Rows"] > 0
    assert counters["Data"]["Current Rows"] > counters["Data"]["Previous Rows"]
    assert counters["Sources"]["Downloaded"] > 0
    assert counters["Sources"]["Errored"] == 0
    assert counters["Data"]["Errored"] == 0
    assert counters["Egress"]["Errored"] == 0
    assert counters["Egress"]["Database Rows"] > 0
    _db_counts_after_run.update({table: query_table_count(table) for table in _database_plugin_tables()})
    assert all(count > 0 for count in _db_counts_after_run.values())


def test_rerun():
    counters = run_wrangle_once()
    assert counters["Data"]["Delta Rows"] == 0
    assert counters["Data"]["Current Rows"] > 0
    assert counters["Data"]["Current Rows"] == counters["Data"]["Previous Rows"]
    assert counters["Sources"]["Downloaded"] == 0
    assert counters["Sources"]["Errored"] == 0
    assert counters["Data"]["Errored"] == 0
    assert counters["Egress"]["Errored"] == 0
    assert counters["Egress"]["Database Rows"] == 0
    for table, count in _db_counts_after_run.items():
        assert query_table_count(table) == count


def test_schema_verify_reports_no_drift():
    faults = []
    for statement in _statements(_read_generated(join("query", "verify.sql"))):
        with connect() as database_connection, database_connection.cursor() as database_cursor:
            _execute(database_cursor, statement)
            faults.extend(database_cursor.fetchall())
    assert faults == [], f"generated verify.sql reported drift between the declaration and what was written: {faults}"


def test_reprocess():
    counters = run_wrangle_once(force_reprocessing=True)
    assert counters["Data"]["Delta Rows"] > 0
    assert counters["Data"]["Current Rows"] > 0
    assert counters["Data"]["Previous Rows"] == 0
    assert counters["Sources"]["Downloaded"] == 0
    assert counters["Sources"]["Errored"] == 0
    assert counters["Data"]["Errored"] == 0
    assert counters["Egress"]["Errored"] == 0
    assert counters["Egress"]["Database Rows"] > 0
    for table, count in _db_counts_after_run.items():
        assert query_table_count(table) >= count


_DOCKER_LOG_SKIP = (": Starting ...", ": Environment:", "]:   WRANGLE_")


def _stream_docker_logs(log_process: subprocess.Popen) -> None:  # type: ignore[type-arg]
    for line in log_process.stdout:  # type: ignore[union-attr]
        if not any(skip in line for skip in _DOCKER_LOG_SKIP):
            sys.stdout.write(line)
            sys.stdout.flush()


def run_wrangle_once(force_reprocessing=False):
    caller = inspect.stack()[1].function
    separator = "#" * 80
    print(f"\n{separator}\n")
    print(f"system_test.py::{caller}")
    print(f"\n{separator}\n")
    sys.stdout.flush()
    body = json.dumps({"force_reprocessing": force_reprocessing}).encode()
    request = urllib.request.Request(
        f"http://localhost:{HTTP_PORT}/api/v1/run",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    log_process = subprocess.Popen(["docker", "logs", "-f", "wrangle"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log_thread = threading.Thread(target=_stream_docker_logs, args=(log_process,), daemon=True)
    log_thread.start()
    try:
        response = urllib.request.urlopen(request, timeout=TIMEOUT_WRANGLE_RUN_SECONDS + TIMEOUT_SECONDS)
        return json.loads(response.read())["counters"]["summary"]
    finally:
        log_process.kill()
        log_process.wait()
        log_thread.join(timeout=2)
        print()


def _read_generated(relative_path: str) -> str:
    generated_path = join(DIR_ROOT, "src/build/resources/schema/postgres", relative_path)
    assert os.path.isfile(generated_path), f"missing generated artifact [{generated_path}]"
    with open(generated_path) as generated_file:
        return generated_file.read()


def _execute(database_cursor, statement: str) -> None:
    database_cursor.execute(psycopg_sql.SQL(statement))  # pyright: ignore[reportArgumentType]


def _statements(text: str) -> list[str]:
    stripped = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    return [statement.strip() for statement in stripped.split(";") if statement.strip()]


def connect():
    missing = [name for name in database.DATABASE_ENV_VARS if not os.environ.get(name)]
    if missing:
        pytest.fail(f"missing required database environment variable(s): {', '.join(missing)}")
    return psycopg.connect((
        f"postgresql://{os.environ['WRANGLE_DATABASE_USER']}:{os.environ['WRANGLE_DATABASE_PASSWORD']}"
        f"@{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}"
        f"/{os.environ['WRANGLE_DATABASE_USER']}"
    ), connect_timeout=TIMEOUT_SECONDS, autocommit=True, options=f"-c statement_timeout={TIMEOUT_QUERY_SECONDS * 1000}")


def query_table_count(table_name: str) -> int:
    with connect() as database_connection, database_connection.cursor() as database_cursor:
        # noinspection SqlNoDataSourceInspection, SqlDialectInspection
        database_cursor.execute(psycopg_sql.SQL("SELECT COUNT(*) FROM {}").format(psycopg_sql.Identifier(table_name)))
        row: tuple = database_cursor.fetchone() or (0,)
        return row[0]


@functools.lru_cache
def _database_plugin_tables() -> list[str]:
    model_dir = join(DIR_ROOT, "src/build/resources/schema/postgres/model")
    return sorted(os.path.basename(model_path)[:-len(".sql")] for model_path in glob.glob(join(model_dir, "*.sql")))


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
