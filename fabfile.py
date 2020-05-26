import glob
import math
import signal
import sys
from os.path import *

from fabric import task
from pathlib2 import Path


@task(default=True)
def default(context):
    _setup(context)
    _clean(context)
    _build(context)
    _unittest(context)
    _package(context)
    _systest(context)
    _release(context)
    _deploy(context)


@task
def setup(context):
    _setup(context)


@task
def purge(context):
    _purge(context)


@task
def clean(context):
    _clean(context)


@task
def build(context):
    _setup(context)
    _clean(context)
    _build(context)


@task
def unittest(context):
    _setup(context)
    _clean(context)
    _build(context)
    _unittest(context)


@task
def package(context):
    _setup(context)
    _clean(context)
    _build(context)
    _package(context)


@task
def systest(context):
    _setup(context)
    _clean(context)
    _build(context)
    _package(context)
    _systest(context)


@task
def run(context):
    _setup(context)
    _clean(context)
    _build(context)
    _package(context)
    _run(context)


@task
def release(context):
    _setup(context)
    _release(context)


@task
def deploy(context):
    _setup(context)
    _deploy(context)


def _setup(context, module="asystem"):
    _print_header(module, "setup")
    _print_line("Versions:\n\tCompact: {}\n\tNumeric: {}\n\tAbsolute: {}\n".format(VERSION_COMPACT, VERSION_NUMERIC, VERSION_ABSOLUTE))
    if len(_run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) == 0:
        _run_local(context, "conda create -y -n $CONDA_ENV python=2.7")
        _print_line("Installing requirements ...")
        for requirement in glob.glob("{}/*/*/*/reqs_*.txt".format(DIR_ROOT)):
            _run_local(context, "pip install -r {}".format(requirement))

    # TODO: Update requirements or manage
    # sudo npm install -g karma jasmine karma-jasmine karma-chrome-launcher --unsafe-perm=true --allow-root

    _print_footer(module, "setup")


def _purge(context, module="asystem"):
    _print_header(module, "purge")
    _run_local(context, "docker system prune --volumes -f")
    if len(_run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) > 0:
        _run_local(context, "conda remove -y -n $CONDA_ENV --all")
    _print_footer(module, "purge")


def _clean(context):
    for module in _get_modules(context, "target", False):
        _print_header(module, "clean")
        _run_local(context, "rm -rf {}/{}/target".format(DIR_ROOT, module))
        _print_footer(module, "clean")


def _build(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "build")
        _print_line("Preparing resources ...")
        _run_local(context, "mkdir -p target && cp -rvf src target/package", module)
        _run_local(context, "envsubst < setup.py > setup.py.new && "
                            "mv setup.py.new setup.py",
                   join(module, "target/package"), env=TEMPLATE_VARIABLES)
        _run_local(context, "envsubst < main/python/{}/application.py > main/python/{}/application.py.new && "
                            "mv main/python/{}/application.py.new main/python/{}/application.py"
                   .format(_name(module), _name(module), _name(module), _name(module)), join(module, "target/package"),
                   env=TEMPLATE_VARIABLES)
        _run_local(context, "python setup.py sdist", join(module, "target/package"))
        _print_footer(module, "build")


def _unittest(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "python unit_tests.py", join(module, "src/test/python/unit"))
    _print_footer(module, "unittest")


def _package(context):
    for module in _get_modules(context, "Dockerfile"):
        _print_header(module, "package")
        _run_local(context, "docker image build -t {}:latest -t {}:{} ."
                   .format(_name(module), _name(module), VERSION_ABSOLUTE), module)
        _run_local(context, "docker image ls {}".format(_name(module)))
        _run_local(context, "mkdir -p target/image", module)
        _print_line("\nTo run a shell from the docker image run:")
        _print_line("docker run -it {}:{} /bin/bash\n".format(_name(module), VERSION_ABSOLUTE))
        _print_footer(module, "package")


def _systest(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "systest")
        _print_line("Preparing environment ...")
        _run_local(context, "rm -rvf target/runtime-system", module)
        _run_local(context, "cp -rvf src/main/resources/config target/runtime-system", module)
        _run_local(context, "docker network prune -f")
        _print_line("Starting server ...")
        _run_local(context, "docker-compose --no-ansi up --force-recreate -d", "aswitch/vernemq")
        _run_local(context, "DATA_DIR=./target/runtime-system docker-compose --no-ansi up --force-recreate -d", module)
        _run_local(context, "sleep 2")
        _print_line("Running system tests ...")
        test_exit_code = _run_local(context, "karma start", join(module, "src/test/resources/karma"), warn=True).exited
        test_exit_code += _run_local(context, "python system_tests.py", join(module, "src/test/python/system"), warn=True).exited
        _print_line("Stopping and removing server ...")
        _run_local(context, "DATA_DIR=./target/runtime-system docker-compose --no-ansi down -v", module)
        _run_local(context, "docker-compose --no-ansi down -v", "aswitch/vernemq")
        if test_exit_code != 0:
            _print_line("Tests ... failed")
            _run_local(context, "false")
        _print_footer(module, "systest")


def _run(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "run")
        _print_line("Preparing environment ...")
        _run_local(context, "rm -rvf target/runtime-system", module)
        _run_local(context, "cp -rvf src/main/resources/config target/runtime-system", module)
        _run_local(context, "docker network prune -f")
        _print_line("Starting server ...")
        _run_local(context, "docker-compose --no-ansi up --force-recreate -d", "aswitch/vernemq")

        def server_stop(signal, frame):
            _print_line("Stopping and removing server ...")
            _run_local(context, "DATA_DIR=./target/runtime-system docker-compose --no-ansi down -v", module)
            _run_local(context, "docker-compose --no-ansi down -v", "aswitch/vernemq")

        signal.signal(signal.SIGINT, server_stop)
        _run_local(context, "DATA_DIR=./target/runtime-system docker-compose --no-ansi up --force-recreate", module)
        _print_footer(module, "run")


def _release(context):
    for module in _get_modules(context, "Dockerfile"):
        _print_header(module, "release")
        _print_line("Saving docker image ...")
        _run_local(context, "docker image save -o {}-{}.tar.gz {}:{}"
                   .format(_name(module), VERSION_ABSOLUTE, _name(module), VERSION_ABSOLUTE),
                   join(module, "target/image"))
        _print_footer(module, "release")


def _deploy(context):
    for module in _get_modules(context, "deploy"):
        _print_header(module, "deploy")
        # TODO: Pickup deploy files and execute remotely
        _print_footer(module, "deploy")


def _group(module):
    return dirname(dirname(module))


def _name(module):
    return dirname(module)


def _get_modules(context, filter_path=None, filter_changes=True):
    working_modules = []
    working_dirs = _run_local(context, "pwd", hide='out').stdout.encode("utf8").strip().split('/')
    if working_dirs[-1] == "asystem":
        for filtered_module in filter(lambda module_tmp: isdir(module_tmp) and (
                not filter_changes or _run_local(context, "git status --porcelain {}".format(module_tmp), DIR_ROOT, hide='out').stdout
        ), glob.glob('*/*')):
            working_modules.append(filtered_module)
    else:
        root_dir_index = working_dirs.index("asystem")
        if (root_dir_index + 2) < len(working_dirs):
            working_modules.append(working_dirs[root_dir_index + 1] + "/" + working_dirs[root_dir_index + 2])
        else:
            for nested_modules in filter(lambda module_tmp: isdir(module_tmp), glob.glob('*')):
                working_modules.append("{}/{}".format(working_dirs[root_dir_index + 1], nested_modules))
    working_modules[:] = [module for module in working_modules
                          if filter_path is None or glob.glob("{}/{}/{}*".format(DIR_ROOT, module, filter_path))]
    return working_modules


def _run_local(context, command, working=".", **kwargs):
    with context.cd(join("./" if working == "." else DIR_ROOT, working)):
        return context.run(". {} && {}".format(FILE_PROFILE, command), **kwargs)


def _run_remote(context, command, **kwargs):
    return context.run(command, **kwargs)


def _print_line(message):
    print(message)
    sys.stdout.flush()


def _print_header(module, stage):
    _print_line(HEADER.format(stage.upper(), module.lower().replace('/', '-'), VERSION_ABSOLUTE))


def _print_footer(module, stage):
    _print_line(FOOTER.format(stage.upper(), module.lower().replace('/', '-'), VERSION_ABSOLUTE))


DIR_ROOT = dirname(abspath(__file__))
FILE_PROFILE = join(dirname(abspath(__file__)), ".profile")

VERSION_ABSOLUTE = Path(join(dirname(abspath(__file__)), ".version")).read_text()
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
