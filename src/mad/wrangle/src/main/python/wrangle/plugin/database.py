import contextlib
import json
import os
from os.path import isfile, join

import psycopg
from psycopg import sql

from .config import DATABASE_SCHEMA_DIRS, TIMEOUT_NETWORK_SECONDS, config
from .logger import print_log

_ensured_tables = set()
_schema_columns = {}

DATABASE_ENV_VARS = (
    "WRANGLE_DATABASE_HOST",
    "WRANGLE_DATABASE_PORT",
    "WRANGLE_DATABASE_USER",
    "WRANGLE_DATABASE_PASSWORD",
)


database_conn: psycopg.Connection | None = None
DSN: str | None = None


def database_open():
    global database_conn, DSN
    if database_conn is not None:
        database_close()
    if config.disable_database_uploads and config.disable_database_downloads:
        return
    missing = [name for name in DATABASE_ENV_VARS if not os.environ.get(name)]
    if missing:
        print_log(
            "wrangle",
            f"Database disabled: missing environment variable(s) [{', '.join(missing)}]",
            level="warning",
        )
        return
    try:
        connect_timeout = max(1, int(TIMEOUT_NETWORK_SECONDS))
        statement_timeout_ms = max(1, int(TIMEOUT_NETWORK_SECONDS * 1000))
        DSN = (
            f"postgresql://{os.environ['WRANGLE_DATABASE_USER']}:{os.environ['WRANGLE_DATABASE_PASSWORD']}"
            f"@{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}"
            f"/{os.environ['WRANGLE_DATABASE_USER']}"
        )
        database_conn = psycopg.connect(DSN, autocommit=False, connect_timeout=connect_timeout,
                                        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5,
                                        options=f"-c statement_timeout={statement_timeout_ms}")
        print_log(
            "Wrangle",
            f"Database connected to [{os.environ['WRANGLE_DATABASE_HOST']}:"
            f"{os.environ['WRANGLE_DATABASE_PORT']}/{os.environ['WRANGLE_DATABASE_USER']}]",
            level="debug",
        )
    except Exception as exception:
        database_conn = None
        DSN = None
        print_log(
            "wrangle",
            "Database disabled: connection failed",
            exception=exception,
            level="warning",
        )


def database_close():
    global database_conn, DSN
    if database_conn is None:
        return
    try:
        database_conn.close()
        print_log(
            "wrangle",
            "Database connection closed",
            level="debug",
        )
    except Exception as exception:
        print_log(
            "wrangle",
            "Database close failed",
            exception=exception,
        )
    database_conn = None
    DSN = None
    _ensured_tables.clear()


def database_drop(table_name):
    if database_conn is None:
        return False
    try:
        with database_conn.cursor() as cursor:
            cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))
        database_conn.commit()
        _ensured_tables.discard(table_name)
        print_log("Wrangle", f"Database dropped table [{table_name}]", level="debug")
        return True
    except Exception as exception:
        print_log("wrangle", f"Database drop of table [{table_name}] failed", exception=exception, level="warning")
        with contextlib.suppress(Exception):
            database_conn.rollback()
        return False


def database_schema_path(table_name, suffix="sql"):
    for schema_dir in DATABASE_SCHEMA_DIRS:
        schema_path = join(schema_dir, f"{table_name}.{suffix}")
        if isfile(schema_path):
            return schema_path
    raise FileNotFoundError(f"Database schema [{table_name}.{suffix}] not found in {list(DATABASE_SCHEMA_DIRS)}")


def database_schema_columns(table_name):
    if table_name not in _schema_columns:
        with open(database_schema_path(table_name, "json")) as columns_file:
            _schema_columns[table_name] = json.load(columns_file)
    return _schema_columns[table_name]


def database_ensure_table(table_name, conn):
    if table_name in _ensured_tables:
        return
    with open(database_schema_path(table_name)) as schema_file:
        schema_sql = schema_file.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
        conn.commit()
    _ensured_tables.add(table_name)


def database_upsert(long_df, table_name, conn, dsn):
    columns = database_schema_columns(table_name)
    time_column, value_column = columns["time"], columns["value"]
    key = [time_column["column"], *columns["dimensions"]]
    all_columns = [*key, value_column["column"]]
    stage_columns = ",\n                ".join(
        f"{name} {column_type} NOT NULL" for name, column_type in
        [(time_column["column"], time_column["type"])]
        + [(dimension, "TEXT") for dimension in columns["dimensions"]]
        + [(value_column["column"], value_column["type"])])
    stage = f"{table_name}_stage"
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE UNLOGGED TABLE IF NOT EXISTS {stage} (
                {stage_columns}
            )
        """)
        cur.execute(f"TRUNCATE {stage}")
        conn.commit()
    try:
        long_df.write_database(stage, connection=dsn, if_table_exists="append", engine="adbc")
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {table_name} ({", ".join(all_columns)})
                SELECT {", ".join(all_columns)} FROM {stage}
                ON CONFLICT ({", ".join(key)})
                DO UPDATE SET {value_column["column"]} = EXCLUDED.{value_column["column"]}
                WHERE {table_name}.{value_column["column"]} IS DISTINCT FROM EXCLUDED.{value_column["column"]}
            """)
            conn.commit()
    finally:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE {stage}")
            conn.commit()


def database_reconnect():
    global database_conn
    if config.disable_database_uploads and config.disable_database_downloads:
        return False
    if database_conn is not None and not database_conn.closed:
        try:
            with database_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            database_conn.rollback()
            return True
        except Exception as exception:
            print_log("wrangle", "Database connection lost, reconnecting", exception=exception, level="warning")
    database_open()
    return database_conn is not None
