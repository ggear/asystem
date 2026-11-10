import logging
import sys


class LogFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return message if record.levelno == logging.INFO else f"{record.levelname} {message}"


def configure_log():
    log = logging.getLogger("mlmodels")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(LogFormatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
