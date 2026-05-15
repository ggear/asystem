import os

import psycopg

from .config import config
from .logger import print_log

database_conn: psycopg.Connection | None = None
DSN: str | None = None

DATABASE_ENV_VARS = (
    "WRANGLE_DATABASE_HOST",
    "WRANGLE_DATABASE_PORT",
    "WRANGLE_DATABASE_NAME",
    "WRANGLE_DATABASE_USER",
    "WRANGLE_DATABASE_PASSWORD",
)


def database_open():
    global database_conn, DSN
    if database_conn is not None:
        database_close()
    if config.disable_repo_uploads and config.disable_repo_downloads:
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
        DSN = (
            f"postgresql://{os.environ['WRANGLE_DATABASE_USER']}:{os.environ['WRANGLE_DATABASE_PASSWORD']}"
            f"@{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}"
            f"/{os.environ['WRANGLE_DATABASE_NAME']}"
        )
        database_conn = psycopg.connect(DSN, autocommit=False)
        print_log(
            "wrangle",
            f"Database connected to [{os.environ['WRANGLE_DATABASE_HOST']}:"
            f"{os.environ['WRANGLE_DATABASE_PORT']}/{os.environ['WRANGLE_DATABASE_NAME']}]",
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
