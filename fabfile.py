import glob
import os.path

from fabric import task

from fablib import *


@task(default=True)
def default(context):
    print_header("asystem", "initialise")

    print_line("Versions:\n\tCompact: {}\n\tNumeric: {}\n\tAbsolute: {}\n".format(VERSION_COMPACT, VERSION_NUMERIC, VERSION_ABSOLUTE))

    if len(run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) == 0:
        run_local(context, "conda create -y -n $CONDA_ENV python=2.7")
        print_line("Installing requirements ...")
        for requirement in glob.glob('*/*/*/reqs_*.txt'):
            run_local(context, "pip install -r {}".format(requirement))
    print_footer("asystem", "initialise")
    for module_changed in filter(lambda module:
                                 os.path.isdir(module) and
                                 context.run("git status --porcelain {}".format(module), hide='out').stdout,
                                 glob.glob('*/*')):
        if os.path.isfile(os.path.join(module_changed, "fabfile.py")):
            run_local(context, "fab", module_changed)


@task
def clean(context):
    print_header("asystem", "clean")
    if len(run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) > 0:
        run_local(context, "conda remove -y -n $CONDA_ENV --all")
    run_local(context, "docker image prune -f -a")
    print_footer("asystem", "clean")
