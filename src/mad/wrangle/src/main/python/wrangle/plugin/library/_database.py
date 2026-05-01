import os

from ._config import config
from ._logging import print_log

database = None

DATABASE_ENV_VARS = ("WRANGLE_DATABASE_HOST", "WRANGLE_DATABASE_PORT",
                     "WRANGLE_DATABASE_NAME", "WRANGLE_DATABASE_TOKEN")


def database_open():
    global database
    if database is not None:
        database_close()
    if config.disable_uploads and config.disable_downloads:
        return
    missing = [name for name in DATABASE_ENV_VARS if not os.environ.get(name)]
    if missing:
        print_log("wrangle", f"Database disabled: missing environment variable(s) [{', '.join(missing)}]", level="warning")
        return
    try:
        from influxdb_client_3 import InfluxDBClient3
        database = InfluxDBClient3(
            host=f"http://{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}",
            token=os.environ["WRANGLE_DATABASE_TOKEN"],
            database=os.environ["WRANGLE_DATABASE_NAME"],
        )
        print_log("wrangle", f"Database connection opened to [{os.environ['WRANGLE_DATABASE_HOST']}:{os.environ['WRANGLE_DATABASE_PORT']}/{os.environ['WRANGLE_DATABASE_NAME']}]", level="debug")
    except Exception as exception:
        database = None
        print_log("wrangle", "Database disabled: connection failed", exception=exception, level="warning")


def database_close():
    global database
    if database is None:
        return
    try:
        database.close()
        print_log("wrangle", "Database connection closed", level="debug")
    except Exception as exception:
        print_log("wrangle", "Database close failed", exception=exception)
    database = None
