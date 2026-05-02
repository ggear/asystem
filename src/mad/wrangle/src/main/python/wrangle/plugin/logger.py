import traceback
from datetime import datetime

from .config import config

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
        line_text = "" if line is None else str(line)
        if len(line_text) > 0:
            print(f"{prefix}{line_text}")
    if exception is not None:
        traceback_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
        print(f"{prefix}{(chr(10) + prefix).join(''.join(traceback_lines).splitlines())}", flush=True)
