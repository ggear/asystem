import os

import psycopg

from .config import NETWORK_TIMEOUT_SECONDS, config
from .logger import print_log

DATABASE_ENV_VARS = (
    "WRANGLE_DATABASE_HOST",
    "WRANGLE_DATABASE_PORT",
    "WRANGLE_DATABASE_USER",
    "WRANGLE_DATABASE_PASSWORD",
)

DATABASE_QUERY_TEMPLATES = [
    "SELECT COUNT(*), MIN(time) AS oldest, MAX(time) AS newest FROM {table}",
    "SELECT COUNT(*), type, period, unit, MIN(time) AS oldest, MAX(time) AS newest FROM {table} GROUP BY type, period, unit ORDER BY type, period, unit",
    "SELECT * FROM {table} WHERE time >= CURRENT_DATE ORDER BY time DESC",
    "SELECT * FROM {table} WHERE time >= CURRENT_DATE - INTERVAL '2 days' ORDER BY time DESC",
    "SELECT * FROM {table} WHERE time >= date_trunc('year', CURRENT_DATE) ORDER BY time DESC LIMIT 10",
    "SELECT * FROM {table} ORDER BY time DESC LIMIT 10",
    "SELECT time_bucket('1 week', time) AS bucket, type, AVG(value) FROM {table} GROUP BY bucket, type ORDER BY bucket DESC LIMIT 20",
    "SELECT time_bucket('1 month', time) AS bucket, type, MAX(value) FROM {table} GROUP BY bucket, type ORDER BY bucket DESC LIMIT 20",
    "SELECT time_bucket('1 month', time) AS bucket, entity, type, AVG(value) AS mean, MAX(value) AS high, MIN(value) AS low, MAX(value) - MIN(value) AS range "
    "FROM {table} WHERE time >= date_trunc('year', CURRENT_DATE) GROUP BY bucket, entity, type ORDER BY bucket DESC, entity LIMIT 10",
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
        connect_timeout = max(1, int(NETWORK_TIMEOUT_SECONDS))
        statement_timeout_ms = max(1, int(NETWORK_TIMEOUT_SECONDS * 1000))
        DSN = (
            f"postgresql://{os.environ['WRANGLE_DATABASE_USER']}:{os.environ['WRANGLE_DATABASE_PASSWORD']}"
            f"@{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}"
            f"/{os.environ['WRANGLE_DATABASE_USER']}"
        )
        database_conn = psycopg.connect(DSN, autocommit=False, connect_timeout=connect_timeout,
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
