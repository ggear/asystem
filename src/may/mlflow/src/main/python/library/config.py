import os.path
from zoneinfo import ZoneInfo

from asystem.model import PROJECT_SPLITS

MODULE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
SOURCE_DIR = os.path.abspath(os.path.join(MODULE_DIR, "../.."))
MODEL_DIR = os.path.join(MODULE_DIR, "src/main/model")
DATA_SPLITS = PROJECT_SPLITS
DATA_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DATA_TIMEZONE = ZoneInfo("Australia/Perth")
CONSUMER_SLOTS = ("default", "release")
