import contextlib
import os

import psycopg
from psycopg import sql

from .config import TIMEOUT_NETWORK_SECONDS, config
from .logger import print_log

DATABASE_ENV_VARS = (
    "WRANGLE_DATABASE_HOST",
    "WRANGLE_DATABASE_PORT",
    "WRANGLE_DATABASE_USER",
    "WRANGLE_DATABASE_PASSWORD",
)

DATABASE_QUERY_TEMPLATES = [
    (
        "SELECT\n"
        "   COUNT(*),\n"
        "   MIN(time) AS oldest,\n"
        "   MAX(time) AS newest\n"
        "FROM {table}"
    ),
    (
        "SELECT\n"
        "   COUNT(*),\n"
        "   type,\n"
        "   period,\n"
        "   unit,\n"
        "   MIN(time) AS oldest,\n"
        "   MAX(time) AS newest\n"
        "FROM {table}\n"
        "GROUP BY type, period, unit\n"
        "ORDER BY type, period, unit"
    ),
    (
        "SELECT time, type, period, unit, value\n"
        "FROM {table}\n"
        "WHERE\n"
        "   entity = (SELECT entity FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= CURRENT_DATE - INTERVAL '1 year'\n"
        "ORDER BY time DESC"
    ),
    (
        "SELECT time, entity, period, unit, value\n"
        "FROM {table}\n"
        "WHERE\n"
        "   type = (SELECT type FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= CURRENT_DATE - INTERVAL '90 days'\n"
        "ORDER BY time DESC\n"
        "LIMIT 50"
    ),
    (
        "SELECT time, entity, type, unit, value\n"
        "FROM {table}\n"
        "WHERE\n"
        "   period = (SELECT period FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= CURRENT_DATE - INTERVAL '180 days'\n"
        "ORDER BY time DESC\n"
        "LIMIT 50"
    ),
    (
        "SELECT time, entity, type, period, value\n"
        "FROM {table}\n"
        "WHERE\n"
        "   unit = (SELECT unit FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= CURRENT_DATE - INTERVAL '180 days'\n"
        "ORDER BY time DESC\n"
        "LIMIT 50"
    ),
    (
        "SELECT time, entity, value\n"
        "FROM {table}\n"
        "WHERE\n"
        "   type = (SELECT type FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND period = (SELECT period FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND unit = (SELECT unit FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= date_trunc('year', CURRENT_DATE)\n"
        "ORDER BY time DESC"
    ),
    (
        "SELECT DISTINCT ON (type, period, unit)\n"
        "   *\n"
        "FROM {table}\n"
        "WHERE\n"
        "   time >= CURRENT_DATE - INTERVAL '2 days'\n"
        "ORDER BY type, period, unit, time DESC"
    ),
    (
        "SELECT\n"
        "   time_bucket('1 week', time) AS bucket,\n"
        "   entity,\n"
        "   AVG(value)\n"
        "FROM {table}\n"
        "WHERE\n"
        "   type = (SELECT type FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= CURRENT_DATE - INTERVAL '1 year'\n"
        "GROUP BY bucket, entity\n"
        "ORDER BY bucket DESC, entity\n"
        "LIMIT 50"
    ),
    (
        "SELECT\n"
        "   time_bucket('1 month', time) AS bucket,\n"
        "   entity,\n"
        "   type,\n"
        "   AVG(value) AS mean,\n"
        "   MAX(value) AS high,\n"
        "   MIN(value) AS low,\n"
        "   MAX(value) - MIN(value) AS range\n"
        "FROM {table}\n"
        "WHERE\n"
        "   time >= date_trunc('year', CURRENT_DATE)\n"
        "GROUP BY bucket, entity, type\n"
        "ORDER BY bucket DESC, entity\n"
        "LIMIT 10"
    ),
    (
        "EXPLAIN ANALYZE\n"
        "SELECT time, value\n"
        "FROM {table}\n"
        "WHERE\n"
        "   entity = (SELECT entity FROM {table} ORDER BY time DESC LIMIT 1)\n"
        "   AND time >= CURRENT_DATE - INTERVAL '1 year'\n"
        "ORDER BY time DESC"
    ),
]

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


def database_drop(table_name):
    if database_conn is None:
        return False
    try:
        with database_conn.cursor() as cursor:
            cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table_name)))
        database_conn.commit()
        print_log("Wrangle", f"Database dropped table [{table_name}]", level="debug")
        return True
    except Exception as exception:
        print_log("wrangle", f"Database drop of table [{table_name}] failed", exception=exception, level="warning")
        with contextlib.suppress(Exception):
            database_conn.rollback()
        return False


def database_ensure_table(table_name, conn):
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                time   DATE  NOT NULL,
                entity TEXT  NOT NULL,
                type   TEXT  NOT NULL,
                period TEXT  NOT NULL,
                unit   TEXT  NOT NULL,
                value  FLOAT8 NOT NULL,
                PRIMARY KEY (time, entity, type, period, unit)
            )
        """)
        cur.execute(f"SELECT create_hypertable('{table_name}', 'time', chunk_time_interval => INTERVAL '10 years', if_not_exists => TRUE)")
        for column in ("entity", "type", "period", "unit"):
            cur.execute(f"CREATE INDEX IF NOT EXISTS {table_name}_{column}_time ON {table_name} ({column}, time DESC)")
        cur.execute("SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = %s LIMIT 1", (table_name,))
        if cur.fetchone() is None:
            cur.execute(f"ALTER TABLE {table_name} SET ("
                        "timescaledb.compress, "
                        "timescaledb.compress_segmentby = 'entity, type, period, unit', "
                        "timescaledb.compress_orderby = 'time DESC')")
            cur.execute(f"SELECT add_compression_policy('{table_name}', INTERVAL '1 year', if_not_exists => TRUE)")
        conn.commit()


def database_upsert(long_df, table_name, conn, dsn):
    stage = f"{table_name}_stage"
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE UNLOGGED TABLE IF NOT EXISTS {stage} (
                time   DATE  NOT NULL,
                entity TEXT  NOT NULL,
                type   TEXT  NOT NULL,
                period TEXT  NOT NULL,
                unit   TEXT  NOT NULL,
                value  FLOAT8 NOT NULL
            )
        """)
        cur.execute(f"TRUNCATE {stage}")
        conn.commit()
    try:
        long_df.write_database(stage, connection=dsn, if_table_exists="append", engine="adbc")
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {table_name} (time, entity, type, period, unit, value)
                SELECT time, entity, type, period, unit, value FROM {stage}
                ON CONFLICT (time, entity, type, period, unit)
                DO UPDATE SET value = EXCLUDED.value
                WHERE {table_name}.value IS DISTINCT FROM EXCLUDED.value
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
