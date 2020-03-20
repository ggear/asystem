import os

from pathlib2 import Path

def run_local(context, command, working=".", **kwargs):
    with context.cd(working):
        return context.run(". {} && {}".format(PROFILE, command), echo=ECHO_COMMAND, **kwargs)


def run_remote(context, command, **kwargs):
    return context.run(command, echo=ECHO_COMMAND, **kwargs)


def print_header(module, stage):
    print(HEADER.format(stage.upper(), module.lower(), VERSION))


def print_footer(module, stage):
    print(FOOTER.format(stage.upper(), module.lower(), VERSION))


ECHO_COMMAND = False
PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".profile")
VERSION = Path(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".version")).read_text()

HEADER = \
    "------------------------------------------------------------\n" \
    "{} STARTING: {}-{}\n" \
    "------------------------------------------------------------"
FOOTER = \
    "------------------------------------------------------------\n" \
    "\033[32m{} SUCCESSFUL: {}-{}\033[00m\n" \
    "------------------------------------------------------------"
