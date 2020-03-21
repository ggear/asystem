import math
import os
import sys

from pathlib2 import Path


def run_local(context, command, working=".", **kwargs):
    with context.cd(working):
        return context.run(". {} && {}".format(PROFILE, command), echo=ECHO_COMMANDS, **kwargs)


def run_remote(context, command, **kwargs):
    return context.run(command, echo=ECHO_COMMANDS, **kwargs)


def print_line(message):
    print(message)
    sys.stdout.flush()


def print_header(module, stage):
    print(HEADER.format(stage.upper(), module.lower(), VERSION_ABSOLUTE))
    sys.stdout.flush()


def print_footer(module, stage):
    print(FOOTER.format(stage.upper(), module.lower(), VERSION_ABSOLUTE))
    sys.stdout.flush()


ECHO_COMMANDS = False
PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".profile")
VERSION_ABSOLUTE = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".version")).read_text()
VERSION_NUMERIC = int(VERSION_ABSOLUTE.replace(".", "").replace("-SNAPSHOT", "")) * (-1 if "SNAPSHOT" in VERSION_ABSOLUTE else 1)
VERSION_COMPACT = int((math.fabs(VERSION_NUMERIC) - 101001000) * (-1 if "SNAPSHOT" in VERSION_ABSOLUTE else 1))

TEMPLATE_VARIABLES = {
    "VERSION_COMPACT": str(VERSION_COMPACT),
    "VERSION_NUMERIC": str(VERSION_NUMERIC),
    "VERSION_ABSOLUTE": VERSION_ABSOLUTE,
}

HEADER = \
    "------------------------------------------------------------\n" \
    "{} STARTING: {}-{}\n" \
    "------------------------------------------------------------"
FOOTER = \
    "------------------------------------------------------------\n" \
    "\033[32m{} SUCCESSFUL: {}-{}\033[00m\n" \
    "------------------------------------------------------------"
