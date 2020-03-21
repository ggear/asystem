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
    print_footer("asystem-anode-python", "clean")


@task
def build(context):
    print_header("asystem-anode-python", "build")
    print_line("Preparing resources ...")
    run_local(context, "mkdir target && cp -rvf src target/package")
    run_local(context, "envsubst < setup.py > setup.py.new && "
                       "mv setup.py.new setup.py", "target/package", env=TEMPLATE_VARIABLES)
    run_local(context, "envsubst < main/python/anode/application.py > main/python/anode/application.py.new && "
                       "mv main/python/anode/application.py.new main/python/anode/application.py", "target/package", env=TEMPLATE_VARIABLES)
    run_local(context, "python setup.py sdist", "target/package")
    print_footer("asystem-anode-python", "build")


@task
def test(context):
    print_header("asystem-anode-python", "test")
    print_line("Running tests ...")
    sys.stdout.flush()
    run_local(context, "python setup.py -q test", "target/package")
    print_footer("asystem-anode-python", "test")


@task
def package(context):
    print_header("asystem-anode-python", "package")
    run_local(context, "docker image build -t anode:{} .".format(VERSION_ABSOLUTE))
    run_local(context, "docker image ls anode")
    run_local(context, "mkdir -p target/image")
    print_line("\nTo run a shell from the docker image run:")
    print_line("docker run -it anode:{} /bin/bash\n".format(VERSION_ABSOLUTE))
    print_footer("asystem-anode-python", "package")


@task
def release(context):
    print_header("asystem-anode-python", "release")
    print_line("Saving docker image ...")
    sys.stdout.flush()
    run_local(context, "docker image save -o test.tar.gz anode:{}".format(VERSION_ABSOLUTE), "target/image")
    print_footer("asystem-anode-python", "release")


@task
def deploy(context):
    print_header("asystem-anode-python", "deploy")
    print_footer("asystem-anode-python", "deploy")
