import os.path
from zoneinfo import ZoneInfo

MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))


SOURCE_DIR = os.path.abspath(os.path.join(MODULE_DIR, "../.."))


NOTEBOOK_DIR = os.path.join(MODULE_DIR, "src/main/notebook")


ENV_PATH = os.path.join(MODULE_DIR, ".env")


PINS_PATH = os.path.abspath(os.path.join(SOURCE_DIR, "../.py_deps_prod.txt"))


VERSION_PATH = os.path.abspath(os.path.join(SOURCE_DIR, "../.version"))


DATA_SOURCES = ("influxdb3", "postgres", "csv", "builder")


DATA_SOURCES_QUERIED = ("influxdb3", "postgres")


DATA_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


DATA_TIMEZONE = ZoneInfo("Australia/Perth")
DATA_SCHEMA = 2
DATA_RUN_FIRST = 1000
