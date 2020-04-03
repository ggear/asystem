import glob
import math
import os
import os.path
import sys

from fabric import task
from pathlib2 import Path


@task
def setup(context, module="asystem"):
    print_header(module, "setup")
    print_line("Versions:\n\tCompact: {}\n\tNumeric: {}\n\tAbsolute: {}\n".format(VERSION_COMPACT, VERSION_NUMERIC, VERSION_ABSOLUTE))
    if len(run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) == 0:
        run_local(context, "conda create -y -n $CONDA_ENV python=2.7")
        print_line("Installing requirements ...")
        for requirement in glob.glob('*/*/*/reqs_*.txt'):
            run_local(context, "pip install -r {}".format(requirement))
    print_footer(module, "setup")


@task
def purge(context, module="asystem"):
    print_header(module, "purge")
    if len(run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) > 0:
        run_local(context, "conda remove -y -n $CONDA_ENV --all")
    run_local(context, "docker image prune -f -a")
    print_footer(module, "purge")


@task(setup)
def clean(context):
    for module in get_modules(context, "target", False):
        print_header(module, "clean")
        run_local(context, "rm -rf {}/{}/target".format(ROOT_DIR, module))
        print_footer(module, "clean")


@task(setup)
def build(context):
    for module in get_modules(context, "src/setup.py"):
        print_header(module, "build")
        print_line("Preparing resources ...")
        run_local(context, "mkdir -p target && cp -rvf src target/package", module)
        module_profile = get_module_profile(context, os.path.join(ROOT_DIR, module, "src", ".profile"))
        run_local(context, "envsubst < setup.py > setup.py.new && "
                           "mv setup.py.new setup.py",
                  os.path.join(module, "target/package"), env=TEMPLATE_VARIABLES)
        run_local(context, "envsubst < main/python/{}/application.py > main/python/{}/application.py.new && "
                           "mv main/python/{}/application.py.new main/python/{}/application.py".format(
            module_profile["APPLICATION_NAME"], module_profile["APPLICATION_NAME"],
            module_profile["APPLICATION_NAME"], module_profile["APPLICATION_NAME"]),
                  os.path.join(module, "target/package"), env=TEMPLATE_VARIABLES)
        run_local(context, "python setup.py sdist", os.path.join(module, "target/package"))
        print_footer(module, "build")


@task(setup)
def test(context):
    for module in get_modules(context, "src/setup.py"):
        print_header(module, "test")
        module_profile = get_module_profile(context, os.path.join(ROOT_DIR, module, "src", ".profile"))
        print_line("Running tests ...")
        run_local(context, "python setup.py test", os.path.join(module, "target/package"), env=module_profile)
        print_footer(module, "test")


@task(setup)
def package(context):
    for module in get_modules(context, "Dockerfile"):
        print_header(module, "package")
        module_profile = get_module_profile(context, os.path.join(ROOT_DIR, module, "src", ".profile"))
        run_local(context, "docker image build -t {}:{} .".format(module_profile["APPLICATION_NAME"], VERSION_ABSOLUTE), module)
        run_local(context, "docker image ls {}".format(module_profile["APPLICATION_NAME"]))
        run_local(context, "mkdir -p target/image", module)
        print_line("\nTo run a shell from the docker image run:")
        print_line("docker run -it {}:{} /bin/bash\n".format(module_profile["APPLICATION_NAME"], VERSION_ABSOLUTE))
        print_footer(module, "package")


@task(setup)
def release(context):
    for module in get_modules(context, "Dockerfile"):
        print_header(module, "release")
        module_profile = get_module_profile(context, os.path.join(ROOT_DIR, module, "src", ".profile"))
        print_line("Saving docker image ...")
        run_local(context, "docker image save -o {}-{}.tar.gz {}:{}".format(
            module_profile["APPLICATION_NAME"], VERSION_ABSOLUTE, module_profile["APPLICATION_NAME"],
            VERSION_ABSOLUTE), os.path.join(module, "target/image"))
        print_footer(module, "release")

@task(setup)
def deploy(context):
    for module in get_modules(context, "deploy"):
        print_header(module, "deploy")
        #TODO: Pickup deploy files and execute remotely
        print_footer(module, "deploy")


@task(default=True)
def default(context):
    clean(context)
    build(context)
    test(context)
    package(context)
    release(context)
    deploy(context)


def get_modules(context, filter_path=None, filter_changes=True):
    working_modules = []
    working_dirs = run_local(context, "pwd", hide='out').stdout.encode("utf8").strip().split('/')
    if working_dirs[-1] == "asystem":
        for filtered_module in filter(lambda module: os.path.isdir(module) and (
                not filter_changes or run_local(context, "git status --porcelain {}".format(module), ROOT_DIR, hide='out').stdout
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


def get_module_profile(context, path):
    module_profile = {}
    with open(path, 'r') as file:
        for line in file.readlines():
            if "export" in line and "=" in line:
                tokens = line.replace("export ", "").replace("\"", "").strip().split("=")
                module_profile[tokens[0]] = tokens[1]
    return module_profile


def run_local(context, command, working=".", **kwargs):
    with context.cd(os.path.join("./" if working == "." else ROOT_DIR, working)):
        return context.run(". {} && {}".format(PROFILE, command), echo=ECHO, **kwargs)


def run_remote(context, command, **kwargs):
    return context.run(command, echo=ECHO, **kwargs)


def print_line(message):
    print(message)
    sys.stdout.flush()


def print_header(module, stage):
    print_line(HEADER.format(stage.upper(), module.lower().replace('/', '-'), VERSION_ABSOLUTE))


def print_footer(module, stage):
    print_line(FOOTER.format(stage.upper(), module.lower().replace('/', '-'), VERSION_ABSOLUTE))


ECHO = False
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
