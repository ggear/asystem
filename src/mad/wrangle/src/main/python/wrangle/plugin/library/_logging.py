import traceback
from datetime import datetime

from ._config import config

LOG_LEVELS = {"debug": 10, "info": 20, "warning": 30, "error": 40, "fatal": 50}


def log_enabled(level):
    return LOG_LEVELS.get(level, 20) >= LOG_LEVELS.get(config.log_level, 20)


def print_log(process, messages, exception=None, level="info"):
    effective_level = "error" if exception is not None else level
    if not log_enabled(effective_level):
        return
    prefix = f"{effective_level.upper()} [{process}] [{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}]: "
    if type(messages) is not list:
        messages = [messages]
    for line in messages:
        if len(line) > 0:
            print(f"{prefix}{line}")
    if exception is not None:
        print(f"{prefix}{(chr(10) + prefix).join(traceback.format_exc().splitlines())}")
