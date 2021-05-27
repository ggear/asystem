###############################################################################
#
# Fabric2 management script, to be invoked by fab command
#
###############################################################################

import glob
import math
import os
import signal
import sys
from os.path import *

from fabric import task
from pathlib2 import Path

FAB_SKIP_GIT = 'FAB_SKIP_GIT'
FAB_SKIP_TESTS = 'FAB_SKIP_TESTS'
FAB_SKIP_DELTA = 'FAB_SKIP_DELTA'


@task(default=True)
def default(context):
    _setup(context)
    _clean(context)
    _pull(context)
    _build(context)
    _unittest(context)
    _systest(context)


@task
def setup(context):
    _setup(context)


@task
def purge(context):
    _purge(context)


@task
def backup(context):
    _clean(context)
    _backup(context)


@task
def pull(context):
    _pull(context)


@task
def clean(context):
    _clean(context)


@task
def build(context):
    _setup(context)
    _clean(context)
    _pull(context)
    _build(context)


@task
def unittest(context):
    _setup(context)
    _clean(context)
    _pull(context)
    _build(context)
    _unittest(context)


@task
def package(context):
    _setup(context)
    _clean(context)
    _pull(context)
    _build(context)
    _package(context)


@task
def systest(context):
    _setup(context)
    _systest(context)


@task
def run(context):
    _setup(context)
    _clean(context)
    _pull(context)
    _run(context)


@task
def deploy(context):
    _pull(context)
    _deploy(context)


@task
def release(context):
    _setup(context)
    _clean(context)
    _release(context)


def _setup(context):
    _print_header("asystem", "setup")
    _print_line(
        "Versions:\n\tCompact: {}\n\tNumeric: {}\n\tAbsolute: {}\n".format(_get_versions()[2], _get_versions()[1], _get_versions()[0]))
    if len(_run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) == 0:
        _run_local(context, "conda create -y -n $CONDA_ENV python=2.7")
        _print_line("Installing requirements ...")
        for requirement in glob.glob("{}/*/*/*/reqs_*.txt".format(DIR_ROOT)):
            _run_local(context, "pip install -r {}".format(requirement))

    # TODO: Update requirements or manage
    # sudo npm install -g karma jasmine karma-jasmine karma-chrome-launcher html-minifier uglify-js --unsafe-perm=true --allow-root

    _print_footer("asystem", "setup")


def _purge(context):
    _print_header("asystem", "purge docker")
    _run_local(context, "[ $(docker ps -a -q | wc -l) -gt 0 ] && docker rm -vf $(docker ps -a -q)", warn=True)
    _run_local(context, "[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q)", warn=True)
    _run_local(context, "docker system prune --volumes -f")
    _print_footer("asystem", "purge docker")
    _print_header("asystem", "purge conda")
    if len(_run_local(context, "conda env list | grep $PYTHON_HOME || true", hide='out').stdout) > 0:
        _run_local(context, "conda remove -y -n $CONDA_ENV --all")
    _print_footer("asystem", "purge conda")


def _backup(context):
    _print_header("asystem", "backup")
    _run_local(context, "mkdir -p /Users/graham/_/doc/bup/asystem && "
                        "git check-ignore $(find . -type f -print) | grep -v ./asystem.iml | grep -v ./.git "
                        "> /Users/graham/_/doc/bup/asystem/.gitexternal", DIR_ROOT)
    _run_local(context, "mkdir -p /Users/graham/_/doc/bup/asystem && "
                        "rsync -vr --files-from=/Users/graham/_/doc/bup/asystem/.gitexternal . /Users/graham/_/doc/bup/asystem", DIR_ROOT)
    _print_footer("asystem", "backup")


def _pull(context, filter_module=None, is_release=False):
    # TODO: Re-enable when I start contributing on multiple machines
    # _print_header("asystem", "pull git")
    # _run_local(context, "git pull --all")
    # _print_footer("asystem", "pull git")

    for module in _get_modules(context, filter_module=filter_module):
        _print_header(module, "pull env")
        _write_env(context, module, join(DIR_ROOT, module, "target/release") if is_release else join(DIR_ROOT, module), is_release)
        _print_footer(module, "pull env")
    if filter_module is None:
        for module in _get_modules(context, "pull.sh", filter_changes=False):
            _print_header(module, "pull resources")
            _run_local(context, "{}/{}/pull.sh".format(DIR_ROOT, module), DIR_ROOT)
            _print_footer(module, "pull resources")
        for module in _get_modules(context, "src/main/python/*/metadata/build.py", filter_changes=False):
            _print_header(module, "pull process")
            _run_local(context, "python {}/{}/src/main/python/{}/metadata/build.py".format(DIR_ROOT, module, _name(module)), DIR_ROOT)
            _print_footer(module, "pull process")


def _clean(context, filter_module=None):
    if filter_module is not None:
        _print_header("asystem", "clean transients")
        _run_local(context, "find . -name *.pyc -prune -exec rm -rf {} \;")
        _run_local(context, "find . -name __pycache__ -prune -exec rm -rf {} \;")
        _run_local(context, "find . -name .coverage -prune -exec rm -rf {} \;")
        _run_local(context, "find . -name Cargo.lock -prune -exec rm -rf {} \;")
        _run_local(context, "find . -name .DS_Store -prune -exec rm -rf {} \;")
        _print_footer("asystem", "clean transients")
    for module in _get_modules(context, filter_module=filter_module, filter_changes=False):
        _print_header(module, "clean target")
        _run_local(context, "rm -rf {}/{}/target".format(DIR_ROOT, module))
        _print_footer(module, "clean target")


def _build(context, filter_module=None, is_release=False):
    for module in _get_modules(context, filter_module=filter_module):
        _print_header(module, "build process")
        _process_target(context, module, is_release)
        _print_footer(module, "build process")
    for module in _get_modules(context, "src", filter_module=filter_module):
        _print_header(module, "build compile")
        if isdir(join(DIR_ROOT, module, "src/main/python")):
            _print_line("Linting sources ...")

            # TODO: Re-enable once I have cleaned up anode codebase
            # _run_local(context, "pylint --disable=all src/main/python/*", module)

        if isfile(join(DIR_ROOT, module, "src/setup.py")):
            _run_local(context, "python setup.py sdist", join(module, "target/package"))
        cargo_file = join(DIR_ROOT, module, "Cargo.toml")
        if isfile(cargo_file):
            _run_local(context, "mkdir -p target/package && cp -rvfp Cargo.toml target/package", module, hide='err', warn=True)
            with open(cargo_file, 'r') as cargo_file_source:
                cargo_file_text = cargo_file_source.read()
                cargo_file_text = cargo_file_text.replace('version = "0.0.0-SNAPSHOT"', 'version = "{}"'.format(_get_versions()[0]))
                cargo_file_text = cargo_file_text.replace('path = "src/', 'path = "')
                with open(join(DIR_ROOT, module, 'target/package/Cargo.toml'), 'w') as cargo_file_destination:
                    cargo_file_destination.write(cargo_file_text)
            _run_local(context, "cargo update && cargo build", join(module, "target/package"))
        _print_footer(module, "build compile")


def _unittest(context):
    for module in _get_modules(context, "src/test/python/unit/unit_tests.py"):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "python unit_tests.py", join(module, "src/test/python/unit"))
        _print_footer(module, "unittest")
    for module in _get_modules(context, "src/test/rust/unit/unit_tests.rs"):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "cargo test", join(module, "target/package"))
        _print_footer(module, "unittest")


def _package(context, filter_module=None):
    for module in _get_modules(context, "Dockerfile", filter_module=filter_module):
        _print_header(module, "package")
        _run_local(context, "docker image build -t {}:{} .".format(_name(module), _get_versions()[0]), module)
        _print_footer(module, "package")


def _systest(context):
    for module in _get_modules(context, "src/test/python/system/system_tests.py"):
        _up_module(context, module)
        _print_header(module, "systest")
        test_exit_code = _run_local(context, "python system_tests.py", join(module, "src/test/python/system"), warn=True).exited
        _down_module(context, module)
        if test_exit_code != 0:
            _print_line("Tests ... failed")
            _run_local(context, "false")
        _print_footer(module, "systest")


def _run(context):
    for module in _get_modules(context, "docker-compose.yml"):
        _up_module(context, module, up_this=False)
        _print_header(module, "run")

        def server_stop(signal, frame):
            _down_module(context, module)

        signal.signal(signal.SIGINT, server_stop)
        run_dev_path = join(DIR_ROOT, module, "run_dev.sh")
        if isfile(run_dev_path):
            _run_local(context, "run_dev.sh", module)
        else:
            _run_local(context, "docker-compose --ansi never up --force-recreate", module)
        _print_footer(module, "run")
        break


def _deploy(context):
    for module in _get_modules(context, "deploy.sh"):
        _print_header(module, "deploy")
        _run_local(context, "deploy.sh", module)
        _print_footer(module, "deploy")


def _release(context):
    if FAB_SKIP_TESTS not in os.environ:
        _pull(context)
        _build(context)
        _unittest(context)
        _systest(context)
    _get_versions_next_release()
    _clean(context)
    _pull(context, is_release=True)
    _build(context, is_release=True)
    _package(context)
    modules = _get_modules(context, "src")
    hosts = set(filter(len, _run_local(context, "find {} -type d ! -name '.*' -mindepth 1 -maxdepth 1"
                                       .format(DIR_ROOT), hide='out').stdout.replace(DIR_ROOT + "/", "").replace("_", "\n").split("\n")))
    if FAB_SKIP_GIT not in os.environ:
        print("Tagging repository ...")
        _run_local(context, "git add -A && git commit -m 'Update asystem-{}' && git tag -a {} -m 'Release asystem-{}'"
                   .format(_get_versions()[0], _get_versions()[0], _get_versions()[0]), env={"HOME": os.environ["HOME"]})
    for module in modules:
        _print_header(module, "release")
        group_path = Path(join(DIR_ROOT, module, ".group"))
        if group_path.exists() and group_path.read_text().strip().isnumeric() and int(group_path.read_text().strip()) >= 0:
            _run_local(context, "mkdir -p target/release", module)
            _run_local(context, "cp -rvfp docker-compose.yml target/release", module, hide='err', warn=True)
            if isfile(join(DIR_ROOT, module, "Dockerfile")):
                file_image = "{}-{}.tar.gz".format(_name(module), _get_versions()[0])
                print("docker -> target/release/{}".format(file_image))
                _run_local(context, "docker image save -o {} {}:{}"
                           .format(file_image, _name(module), _get_versions()[0]), join(module, "target/release"))
            if glob.glob(join(DIR_ROOT, module, "target/package/main/resources/*")):
                _run_local(context, "cp -rvfp target/package/main/resources/* target/release", module)
            else:
                _run_local(context, "mkdir -p target/release/config", module)
            Path(join(DIR_ROOT, module, "target/release/hosts")).write_text("\n".join(hosts) + "\n")
            if glob.glob(join(DIR_ROOT, module, "target/package/run*")):
                _run_local(context, "cp -rvfp target/package/run* target/release", module)
            else:
                _run_local(context, "touch target/release/run.sh", module)
            for host in _get_hosts(context, module):
                _print_header("{}/{}".format(host, _name(module)), "release")
                ssh_pass = _ssh_pass(context, host)
                install = "{}/{}/{}".format(DIR_INSTALL, module, _get_versions()[0])
                print("Copying release to {} ... ".format(host))
                _run_local(context, "{}ssh -q root@{} 'rm -rf {} && mkdir -p {}'".format(ssh_pass, host, install, install))
                _run_local(context, "{}scp -qpr $(find target/release -maxdepth 1 -type f) root@{}:{}".format(ssh_pass, host, install),
                           module)
                _run_local(context, "{}scp -qpr target/release/config root@{}:{}".format(ssh_pass, host, install), module)
                print("Installing release to {} ... ".format(host))
                _run_local(context, "{}ssh -q root@{} 'chmod +x {}/run.sh && {}/run.sh'".format(ssh_pass, host, install, install))
                _run_local(context, "{}ssh -q root@{} 'docker system prune --volumes -f'".format(ssh_pass, host), hide='err', warn=True)
                _run_local(context, "{}ssh -q root@{} 'find $(dirname {}) -maxdepth 1 -mindepth 1 2>/dev/null | sort | "
                                    "head -n $(($(find $(dirname {}) -maxdepth 1 -mindepth 1 2>/dev/null | wc -l) - 2)) | xargs rm -rf'"
                           .format(ssh_pass, host, install, install), hide='err', warn=True)
                _print_footer("{}/{}".format(host, _name(module)), "release")
        else:
            print("Module ignored")
        _print_footer(module, "release")
    _get_versions_next_snapshot()
    if FAB_SKIP_GIT not in os.environ:
        print("Pushing repository ...")
        _run_local(context, "git add -A && git commit -m 'Update asystem-{}' && git push --all && git push origin --tags"
                   .format(_get_versions()[0], _get_versions()[0], _get_versions()[0]), env={"HOME": os.environ["HOME"]})


def _group(module):
    return dirname(module)


def _name(module):
    return basename(module)


def _get_modules(context, filter_path=None, filter_module=None, filter_changes=True):
    if filter_module is None:
        working_modules = []
        filter_changes = filter_changes if FAB_SKIP_DELTA not in os.environ else False
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
        grouped_modules = {}
        for module in working_modules:
            group_path = Path(join(DIR_ROOT, module, ".group"))
            group = group_path.read_text().strip() if group_path.exists() else "ZZZZZ"
            if group not in grouped_modules:
                grouped_modules[group] = [module]
            else:
                grouped_modules[group].append(module)
        sorted_modules = []
        for group in sorted(grouped_modules):
            sorted_modules.extend(grouped_modules[group])
        return sorted_modules
    else:
        return [filter_module] if filter_path is None or os.path.exists(join(DIR_ROOT, filter_module, filter_path)) else []


def _ssh_pass(context, host):
    ssh_prefix = "sshpass -f /Users/graham/.ssh/.password " \
        if _run_local(context, "ssh -qo StrictHostKeyChecking=no -o PasswordAuthentication=no -o BatchMode=yes root@{} exit"
                      .format(host), hide="err", warn=True).exited > 0 else ""
    if _run_local(context, "{}ssh -q root@{} 'echo Connected to {}'".format(ssh_prefix, host, host), hide="err", warn=True).exited > 0:
        print("Error: Cannot connect via [{}ssh -q root@{}]".format(ssh_prefix, host))
        exit(1)
    return ssh_prefix


def _get_service(context, module):
    return module.split("/")[1]


def _get_hosts(context, module):
    return module.split("/")[0].split("_")


def _get_dependencies(context, module):
    run_deps = []
    run_deps_path = join(DIR_ROOT, module, "run_deps.txt")
    if isfile(run_deps_path):
        with open(run_deps_path, "r") as run_deps_file:
            for run_dep in run_deps_file:
                run_dep = run_dep.strip()
                if run_dep != "" and not run_dep.startswith("#"):
                    run_deps.append(run_dep)
    return run_deps + [module]


def _write_env(context, module, working_path=".", is_release=False):
    service = _get_service(context, module)
    _run_local(context, "mkdir -p {}".format(working_path), module)
    _run_local(context, "echo 'SERVICE_NAME={}' > {}/.env"
               .format(service, working_path), module)
    _run_local(context, "echo 'SERVICE_VERSION_ABSOLUTE={}' >> {}/.env"
               .format(_get_versions()[0], working_path), module)
    _run_local(context, "echo 'SERVICE_VERSION_NUMERIC={}' >> {}/.env"
               .format(_get_versions()[1], working_path), module)
    _run_local(context, "echo 'SERVICE_VERSION_COMPACT={}' >> {}/.env"
               .format(_get_versions()[2], working_path), module)
    _run_local(context, "echo 'SERVICE_RESTART={}' >> {}/.env"
               .format("always" if is_release else
                       "no", working_path), module)
    _run_local(context, "echo 'SERVICE_DATA_DIR={}' >> {}/.env"
               .format("{}/{}/{}".format(DIR_HOME, service, _get_versions()[0]) if is_release else
                       "{}/{}/target/runtime-system".format(DIR_ROOT, module), working_path), module)
    for dependency in _get_dependencies(context, module):
        if is_release:
            host_ips = []
            for host in _get_hosts(context, dependency):
                host_ips.append(_run_local(context, "dig +short {}".format(host), hide='out').stdout.strip())
            host_ip = ",".join(host_ips)
            host_name = ",".join(_get_hosts(context, dependency))
        else:
            host_name = "host.docker.internal"
            host_ip = _run_local(context, "[[ $(ipconfig getifaddr en0) != \"\" ]] && ipconfig getifaddr en0 || ipconfig getifaddr en1",
                                 hide='out').stdout.strip()
        if host_name == "" or host_ip == "":
            raise Exception("Cannot resolve service host and or IP")
        dependency_service = _get_service(context, dependency).upper()
        _run_local(context, "echo '' >> {}/.env".format(working_path))
        _run_local(context, "echo '{}_HOST={}' >> {}/.env"
                   .format(dependency_service, host_name, working_path), module)
        _run_local(context, "echo '{}_IP={}' >> {}/.env"
                   .format(dependency_service, host_ip, working_path), module)
        for dependency_env_file in [".env_all", ".env_prod" if is_release else ".env_dev", ".env_all_key"]:
            dependency_env_dev = "{}/{}/{}".format(DIR_ROOT, dependency, dependency_env_file)
            if isfile(dependency_env_dev):
                _run_local(context, "cat {} >> {}/.env".format(dependency_env_dev, working_path), module)
    _substitue_env(context, "{}/.env".format(working_path), working_path, ".env", working_path)


def _substitue_env(context, env_path, source_root, source_path, destination_root):
    env = {}
    if isfile(env_path):
        with open(env_path, 'r') as env_file:
            for env_line in env_file:
                env_line = env_line.replace("export ", "").rstrip()
                if "=" not in env_line:
                    continue
                if env_line.startswith("#"):
                    continue
                env_key, env_value = env_line.split("=", 1)
                env[env_key] = env_value
        _run_local(context, "envsubst '{}' < {}/{} > {}.new && mv {}.new {}"
                   .format(" ".join(["$" + sub for sub in env.keys()]),
                           source_root, source_path, source_path, source_path, source_path), destination_root, env=env)


def _process_target(context, module, is_release=False):
    _run_local(context, "mkdir -p target/package && cp -rvfp src/* run* target/package", module, hide='err', warn=True)
    package_resource_path = join(DIR_ROOT, module, "src/pkg_res.txt")
    if isfile(package_resource_path):
        with open(package_resource_path, "r") as package_resource_file:
            for package_resource in package_resource_file:
                package_resource = package_resource.strip()
                if package_resource != "" and not package_resource.startswith("#"):
                    package_resource = package_resource.replace("../run", "run")
                    package_resource_source = DIR_ROOT if package_resource == "run.sh" and \
                                                          not isfile(join(DIR_ROOT, module, package_resource)) \
                        else join(DIR_ROOT, module, "target/package")
                    _substitue_env(context, join(DIR_ROOT, module, "target/release/.env" if is_release else ".env"),
                                   package_resource_source, package_resource, join(module, "target/package"))
                    if is_release:
                        if package_resource.endswith(".html") or package_resource.endswith(".css"):
                            _run_local(context, "html-minifier --collapse-whitespace --remove-comments --remove-optional-tags"
                                                " --remove-redundant-attributes --remove-script-type-attributes --remove-tag-whitespace"
                                                " --use-short-doctype --minify-css true --minify-js true {} > {}.new && mv {}.new {}"
                                       .format(package_resource, package_resource, package_resource, package_resource),
                                       join(module, "target/package"))
                        elif package_resource.endswith(".js"):
                            _run_local(context, "uglifyjs {} -c -m > {}.new && mv {}.new {}"
                                       .format(package_resource, package_resource, package_resource, package_resource),
                                       join(module, "target/package"))

                    # TODO: I think this can be removed, was causing issues
                    # runtime_resource = join(DIR_ROOT, module,
                    #                         package_resource.replace("main/resources/config", "target/runtime-system"))
                    # if isfile(runtime_resource):
                    #     _run_local(context, "cp -rvf {}/{} {}".format(package_resource_source, package_resource, runtime_resource))


def _up_module(context, module, up_this=True):
    if isfile(join(DIR_ROOT, module, "docker-compose.yml")):
        for run_dep in _get_dependencies(context, module):
            _clean(context, filter_module=run_dep)
            _pull(context, filter_module=run_dep)
            _build(context, filter_module=run_dep)
            _package(context, filter_module=run_dep)
            _print_header(run_dep, "run prepare")
            _run_local(context, "mkdir -p target/runtime-system", run_dep)
            dir_config = join(DIR_ROOT, run_dep, "target/package/main/resources/config")
            if isdir(dir_config) and len(os.listdir(dir_config)) > 0:
                _run_local(context, "cp -rvfp $(find {} -mindepth 1 -maxdepth 1) target/runtime-system".format(dir_config), run_dep)
            _print_footer(run_dep, "run prepare")
            if run_dep != module or up_this:
                _print_header(run_dep, "run")
                _run_local(context, "docker-compose --ansi never up --force-recreate -d", run_dep)
                _print_footer(run_dep, "run")


def _down_module(context, module, down_this=True):
    if isfile(join(DIR_ROOT, module, "docker-compose.yml")):
        _print_line("Stopping servers ...")
        for run_dep in reversed(_get_dependencies(context, module)):
            if run_dep != module or down_this:
                _run_local(context, "docker-compose --ansi never down -v", run_dep)


def _run_local(context, command, working=".", **kwargs):
    with context.cd(join("./" if working == "." else DIR_ROOT, working)):
        return context.run(". {} && {}".format(FILE_ENV, command), **kwargs)


def _run_remote(context, command, **kwargs):
    return context.run(command, **kwargs)


def _get_versions(version_absolute=None):
    if version_absolute is None:
        version_absolute = Path(join(dirname(abspath(__file__)), ".version")).read_text()
    version_numeric = int(version_absolute.replace(".", "").replace("-SNAPSHOT", "")) * (-1 if "SNAPSHOT" in version_absolute else 1)
    version_compact = int((math.fabs(version_numeric) - 101001000) * (-1 if "SNAPSHOT" in version_absolute else 1))
    return version_absolute, version_numeric, version_compact


def _get_versions_next(versions=None):
    if versions is None:
        versions = _get_versions()
    version_next_numeric = abs(versions[1]) if "SNAPSHOT" in versions[0] else (abs(versions[1]) + 1)
    version_next_absolute = u"{}.{}.{}".format(
        int(version_next_numeric / 10000000) % 10000,
        int(version_next_numeric / 10000) % 10000,
        version_next_numeric % 10000)
    return _get_versions(version_next_absolute)


def _get_versions_next_release():
    versions_next_release = _get_versions(_get_versions_next()[0])
    Path(join(dirname(abspath(__file__)), ".version")).write_text(versions_next_release[0])
    return versions_next_release


def _get_versions_next_snapshot():
    versions_next_snapshot = _get_versions(_get_versions_next(_get_versions(
        _get_versions()[0].replace("-SNAPSHOT", "") if "SNAPSHOT" in _get_versions()[0] else _get_versions()[0]))[0] + "-SNAPSHOT")
    Path(join(dirname(abspath(__file__)), ".version")).write_text(versions_next_snapshot[0])
    return versions_next_snapshot


def _print_line(message):
    print(message)
    sys.stdout.flush()


def _print_header(module, stage):
    _print_line(HEADER.format(stage.upper(), module.lower().replace('/', '-'), _get_versions()[0]))


def _print_footer(module, stage):
    _print_line(FOOTER.format(stage.upper(), module.lower().replace('/', '-'), _get_versions()[0]))


DIR_ROOT = dirname(abspath(__file__))
DIR_HOME = "/home/asystem"
DIR_INSTALL = "/var/lib/asystem/install"

FILE_ENV = join(dirname(abspath(__file__)), ".env_fab")

HEADER = \
    "------------------------------------------------------------\n" \
    "{} STARTING: {}-{}\n" \
    "------------------------------------------------------------"
FOOTER = \
    "------------------------------------------------------------\n" \
    "\033[32m{} SUCCESSFUL: {}-{}\033[00m\n" \
    "------------------------------------------------------------"
