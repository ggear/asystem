import os.path
from zoneinfo import ZoneInfo

from asystem.model import PROJECT_SPLITS

MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
SOURCE_DIR = os.path.abspath(os.path.join(MODULE_DIR, "../.."))
NOTEBOOK_DIR = os.path.join(MODULE_DIR, "src/main/notebook")
PINS_PATH = os.path.abspath(os.path.join(SOURCE_DIR, "../.py_deps_prod.txt"))
VERSION_PATH = os.path.abspath(os.path.join(SOURCE_DIR, "../.version"))
DATA_SPLITS = PROJECT_SPLITS
DATA_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DATA_TIMEZONE = ZoneInfo("Australia/Perth")
