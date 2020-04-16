import glob
import math
import os
import os.path
import sys

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
    _build(context)


@task
def unittest(context):
    _build(context)
    _unittest(context)


@task
def package(context):
    _build(context)
    _package(context)


@task
def systest(context):
    _build(context)
    _package(context)
    _systest(context)


@task
def run(context):
    _build(context)
    _package(context)
    _run(context)


@task
def release(context):
    _release(context)


@task
def deploy(context):
    _deploy(context)


def _setup(context, module="asystem"):
    _print_header(module, "setup")
    _print_line("Versions:\n\tCompact: {}\n\tNumeric: {}\n\tAbsolute: {}\n".format(VERSION_COMPACT, VERSION_NUMERIC, VERSION_ABSOLUTE))
    if len(_run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) == 0:
        _run_local(context, "conda create -y -n $CONDA_ENV python=2.7")
        _print_line("Installing requirements ...")
        for requirement in glob.glob('*/*/*/reqs_*.txt'):
            _run_local(context, "pip install -r {}".format(requirement))
    _print_footer(module, "setup")


def _purge(context, module="asystem"):
    _print_header(module, "purge")
    if len(_run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) > 0:
        _run_local(context, "conda remove -y -n $CONDA_ENV --all")
    _run_local(context, "docker image prune -f -a")
    _print_footer(module, "purge")


def _clean(context):
    for module in _get_modules(context, "target", False):
        _print_header(module, "clean")
        _run_local(context, "rm -rf {}/{}/target".format(ROOT_DIR, module))
        _print_footer(module, "clean")


def _build(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "build")
        _print_line("Preparing resources ...")
        _run_local(context, "mkdir -p target && cp -rvf src target/package", module)
        _run_local(context, "envsubst < setup.py > setup.py.new && "
                            "mv setup.py.new setup.py",
                   os.path.join(module, "target/package"), env=TEMPLATE_VARIABLES)
        _run_local(context, "envsubst < main/python/{}/application.py > main/python/{}/application.py.new && "
                            "mv main/python/{}/application.py.new main/python/{}/application.py".format(
            os.path.dirname(module), os.path.dirname(module),
            os.path.dirname(module), os.path.dirname(module)),
                   os.path.join(module, "target/package"), env=TEMPLATE_VARIABLES)
        _run_local(context, "python setup.py sdist", os.path.join(module, "target/package"))
        _print_footer(module, "build")


def _unittest(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "python setup.py test", os.path.join(module, "target/package"))
        _print_footer(module, "unittest")


def _package(context):
    for module in _get_modules(context, "Dockerfile"):
        _print_header(module, "package")
        _run_local(context, "docker image build -t {}:{} .".format(os.path.dirname(module), VERSION_ABSOLUTE), module)
        _run_local(context, "docker image ls {}".format(os.path.dirname(module)))
        _run_local(context, "mkdir -p target/image", module)
        _print_line("\nTo run a shell from the docker image run:")
        _print_line("docker run -it {}:{} /bin/bash\n".format(os.path.dirname(module), VERSION_ABSOLUTE))
        _print_footer(module, "package")


def _systest(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "systest")
        _print_line("Preparing environment ...")
        _run_local(context, "rm -rvf target/runtime-system", module)
        _run_local(context, "cp -rvf src/main/resources/config target/runtime-system", module)
        _run_local(context, "docker stop anode-systest || true && docker rm anode-systest || true", hide='err')
        _print_line("Starting server ...")
        _run_local(context, "docker run -d --name anode-systest -v {}/{}/target/runtime-system:/etc/anode -p 8091:8091 {}:{} anode".format(
            ROOT_DIR, module, os.path.dirname(module), VERSION_ABSOLUTE))
        _print_line("Running system tests ...")
        _print_line("Stopping and removing server ...")
        _run_local(context, "docker stop anode-systest || true && docker rm anode-systest || true")
        _print_footer(module, "systest")


def _run(context):
    for module in _get_modules(context, "src/setup.py"):
        _print_header(module, "run")
        _print_line("Preparing environment ...")
        _run_local(context, "rm -rvf target/runtime-system", module)
        _run_local(context, "cp -rvf src/main/resources/config target/runtime-system", module)
        _run_local(context, "docker stop anode-systest || true && docker rm anode-systest || true", hide='err')
        _print_line("Starting server ...")
        _run_local(context, "docker run --name anode-systest -v {}/{}/target/runtime-system:/etc/anode -p 8091:8091 {}:{} anode -v".format(
            ROOT_DIR, module, os.path.dirname(module), VERSION_ABSOLUTE))
        _print_line("Stopping and removing server ...")
        _run_local(context, "docker stop anode-systest || true && docker rm anode-systest || true")
        _print_footer(module, "run")


def _release(context):
    for module in _get_modules(context, "Dockerfile"):
        _print_header(module, "release")
        _print_line("Saving docker image ...")
        _run_local(context, "docker image save -o {}-{}.tar.gz {}:{}".format(
            os.path.dirname(module), VERSION_ABSOLUTE, os.path.dirname(module),
            VERSION_ABSOLUTE), os.path.join(module, "target/image"))
        _print_footer(module, "release")


def _deploy(context):
    for module in _get_modules(context, "deploy"):
        _print_header(module, "deploy")
        # TODO: Pickup deploy files and execute remotely
        _print_footer(module, "deploy")


def _get_modules(context, filter_path=None, filter_changes=True):
    working_modules = []
    working_dirs = _run_local(context, "pwd", hide='out').stdout.encode("utf8").strip().split('/')
    if working_dirs[-1] == "asystem":
        for filtered_module in filter(lambda module: os.path.isdir(module) and (
                not filter_changes or _run_local(context, "git status --porcelain {}".format(module), ROOT_DIR, hide='out').stdout
        ), glob.glob('*/*')):
            working_modules.append(filtered_module)
    else:
        root_dir_index = working_dirs.index("asystem")
        if (root_dir_index + 2) < len(working_dirs):
            working_modules.append(working_dirs[root_dir_index + 1] + "/" + working_dirs[root_dir_index + 2])
        else:
            for nested_modules in filter(lambda module: os.path.isdir(module), glob.glob('*')):
                working_modules.append("{}/{}".format(working_dirs[root_dir_index + 1], nested_modules))
    working_modules[:] = [module for module in working_modules
                          if filter_path is None or glob.glob("{}/{}/{}*".format(ROOT_DIR, module, filter_path))]
    return working_modules


def _run_local(context, command, working=".", **kwargs):
    with context.cd(os.path.join("./" if working == "." else ROOT_DIR, working)):
        return context.run(". {} && {}".format(PROFILE, command), **kwargs)


def _run_remote(context, command, **kwargs):
    return context.run(command, **kwargs)


def _print_line(message):
    print(message)
    sys.stdout.flush()


def _print_header(module, stage):
    _print_line(HEADER.format(stage.upper(), module.lower().replace('/', '-'), VERSION_ABSOLUTE))


def _print_footer(module, stage):
    _print_line(FOOTER.format(stage.upper(), module.lower().replace('/', '-'), VERSION_ABSOLUTE))


PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".profile")
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

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
