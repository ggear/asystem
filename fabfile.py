from fabric import task


@task(default=True)
def default(context):
    build(context)
    package(context)
    test(context)


@task
def build(context):
    print("Build")


@task
def package(context):
    print("Package")


@task
def test(context):
    print("Test")


@task
def release(context):
    print("Release")


@task
def deploy(context):
    print("Deploy")
