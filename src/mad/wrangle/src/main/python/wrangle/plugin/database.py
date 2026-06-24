import os

import psycopg

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
        "SELECT DISTINCT ON (type, period, unit)\n"
        "   *\n"
        "FROM {table}\n"
        "WHERE\n"
        "   time >= CURRENT_DATE\n"
        "ORDER BY type, period, unit, time DESC"
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
        "SELECT *\n"
        "FROM {table}\n"
        "WHERE\n"
        "   time >= date_trunc('year', CURRENT_DATE)\n"
        "ORDER BY time DESC\n"
        "LIMIT 10"
    ),
    (
        "SELECT *\n"
        "FROM {table}\n"
        "ORDER BY time DESC\n"
        "LIMIT 10"
    ),
    (
        "SELECT\n"
        "   time_bucket('1 week', time) AS bucket,\n"
        "   type,\n"
        "   AVG(value)\n"
        "FROM {table}\n"
        "GROUP BY bucket, type\n"
        "ORDER BY bucket DESC\n"
        "LIMIT 20"
    ),
    (
        "SELECT\n"
        "   time_bucket('1 month', time) AS bucket,\n"
        "   type,\n"
        "   MAX(value)\n"
        "FROM {table}\n"
        "GROUP BY bucket, type\n"
        "ORDER BY bucket DESC\n"
        "LIMIT 20"
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
