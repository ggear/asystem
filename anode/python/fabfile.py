import sys

sys.path.append('../..')

from fablib import *
from fabric import task


@task(default=True)
def default(context):
    clean(context)
    build(context)
    test(context)
    package(context)
    release(context)
    deploy(context)


@task
def clean(context):
    print_header("asystem-anode-python", "clean")
    run_local(context, "rm -rf target")
    run_local(context, "docker image prune -f")
    print_footer("asystem-anode-python", "clean")


@task
def build(context):
    print_header("asystem-anode-python", "build")
    print("Preparing resources ...")
    run_local(context, "mkdir target && cp -rvf src target/package")
    run_local(context, "python setup.py sdist", "target/package")
    print_footer("asystem-anode-python", "build")


@task
def test(context):
    print_header("asystem-anode-python", "test")
    print("Running tests ...")
    sys.stdout.flush()
    run_local(context, "python setup.py -q test", "target/package")
    print_footer("asystem-anode-python", "test")


@task
def package(context):
    print_header("asystem-anode-python", "package")
    run_local(context, "docker image build -t anode:1.0 .")
    run_local(context, "docker image ls anode")
    run_local(context, "mkdir -p target/image")
    print("To run a shell from the docker image run:")
    print("docker run -it anode:1.0 /bin/bash")
    print_footer("asystem-anode-python", "package")


@task
def release(context):
    print_header("asystem-anode-python", "release")
    print("Saving docker image ...")
    run_local(context, "docker image save -o test.tar.gz anode:1.0", "target/image")
    print_footer("asystem-anode-python", "release")


@task
def deploy(context):
    print_header("asystem-anode-python", "deploy")
    print_footer("asystem-anode-python", "deploy")
