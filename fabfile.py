###############################################################################
#
# Fabric2 management script, to be invoked by fab command
#
# TODO: Rewrite as BundleWrap/pyinfra/K8s?
#       - http://blog.rfox.eu/en/Explorations/Trying_Ansible_alternatives_in_python.html
#       - https://news.ycombinator.com/item?id=23506223
#
###############################################################################

import collections
import glob
import math
import os
import re
import signal
import sys
from os.path import *

import requests
from fabric import task
from packaging import version
from pathlib2 import Path

FAB_SKIP_GIT = 'FAB_SKIP_GIT'
FAB_SKIP_TESTS = 'FAB_SKIP_TESTS'
FAB_SKIP_DELTA = 'FAB_SKIP_DELTA'
FAB_SKIP_GROUP_BELOW = 'FAB_SKIP_GROUP_BELOW'
FAB_SKIP_GROUP_ABOVE = 'FAB_SKIP_GROUP_ABOVE'
FAB_SKIP_GROUP_ALLBUT = 'FAB_SKIP_GROUP_ALLBUT'

if FAB_SKIP_GROUP_ALLBUT in os.environ:
    os.environ[FAB_SKIP_GROUP_BELOW] = str(int(os.environ[FAB_SKIP_GROUP_ALLBUT]) + 1)
    os.environ[FAB_SKIP_GROUP_ABOVE] = str(int(os.environ[FAB_SKIP_GROUP_ALLBUT]) - 1)


@task(aliases=["sup"] + ["setup"[0:i] for i in range(1, len("setup"))])
def setup(context):
    _setup(context)
    _clean(context)
    _pull(context)


@task(aliases=["prg", "f"] + ["purge"[0:i] for i in range(3, len("purge"))])
def purge(context):
    _clean(context)
    _backup(context)
    _purge(context)


@task(aliases=["bup", "a"] + ["backup"[0:i] for i in range(2, len("backup"))])
def backup(context):
    _clean(context)
    _backup(context)


@task(aliases=["pll", "u"] + ["pull"[0:i] for i in range(3, len("pull"))])
def pull(context):
    _clean(context)
    _backup(context)
    _pull(context)


@task(aliases=["gnr"] + ["generate"[0:i] for i in range(1, len("generate"))])
def generate(context):
    _generate(context)


@task(aliases=["cln"] + ["clean"[0:i] for i in range(1, len("clean"))])
def clean(context):
    _clean(context)


@task(default=True, aliases=["bld"] + ["build"[0:i] for i in range(1, len("build"))])
def build(context):
    _setup(context)
    _clean(context)
    _generate(context)
    _build(context)


@task(aliases=["tst"] + ["test"[0:i] for i in range(1, len("test"))])
def test(context):
    _setup(context)
    _clean(context)
    _generate(context)
    _build(context)
    _unittest(context)
    _systest(context)


@task(aliases=["pkg"] + ["package"[0:i] for i in range(1, len("package"))])
def package(context):
    _setup(context)
    _clean(context)
    _generate(context)
    _build(context)
    _package(context)


@task(aliases=["ect"] + ["execute"[0:i] for i in range(1, len("execute"))])
def execute(context):
    _setup(context)
    _clean(context)
    _generate(context)
    _execute(context)


@task(aliases=["dpy"] + ["deploy"[0:i] for i in range(1, len("deploy"))])
def deploy(context):
    _generate(context)
    _deploy(context)


@task(aliases=["rls"] + ["release"[0:i] for i in range(1, len("release"))])
def release(context):
    _setup(context)
    _clean(context)
    _release(context)


def _setup(context):
    _print_header("asystem", "setup")
    _print_line("Versions:\n\tCompact: {}\n\tNumeric: {}\n\tAbsolute: {}\n".format(
        _get_versions()[2],
        _get_versions()[1],
        _get_versions()[0])
    )
    pull_conda = True
    for environment in ["python", "go", "rust"]:
        if len(_run_local(context, "conda env list | grep ${}_HOME || true".format(environment.upper()), hide='out').stdout) == 0:
            if pull_conda:
                pull_conda = False
                _print_header("asystem", "pull conda")
                _run_local(context, "conda update -y --all")
                _print_footer("asystem", "pull conda")
            _run_local(context, "conda create -y -n asystem-{} -c conda-forge {}=${}_VERSION"
                       .format(environment, environment, environment.upper()))
    _print_footer("asystem", "setup")


def _purge(context):
    _print_header("asystem", "purge")
    _run_local(context, "[ $(docker ps -a -q | wc -l) -gt 0 ] && docker rm -vf $(docker ps -a -q)", warn=True)
    _run_local(context, "[ $(docker images -a -q | wc -l) -gt 0 ] && docker rmi -f $(docker images -a -q)", warn=True)
    _run_local(context, "docker system prune --volumes -f")
    for environment in ["python", "go", "rust"]:
        if len(_run_local(context, "conda env list | grep ${}_HOME || true".format(environment.upper()), hide='out').stdout) > 0:
            _run_local(context, "conda remove -y -n asystem-{} --all".format(environment))
            _run_local(context,
                       "chmod -R 777 ${}_HOME 2>/dev/null && rm -rvf ${}_HOME || true".format(environment.upper(), environment.upper()))
    _print_footer("asystem", "purge")


def _backup(context):
    _print_header("asystem", "backup")
    _run_local(context, "mkdir -p /Users/graham/Backup/asystem && "
                        "git check-ignore $(find . "
                        "-not -path './.git*' "
                        "-not -path './.deps*' "
                        "-not -path './.idea*' "
                        "-not -path '*__pycache__*' "
                        "-not -path '*.pytest_cache*' "
                        "-not -path '*/target/*' "
                        "-not -name asystem.iml "
                        "-type f -print) > /Users/graham/Backup/asystem/.gitexternal", DIR_ROOT)
    _run_local(context, "mkdir -p /Users/graham/Backup/asystem && "
                        "rsync -vr --files-from=/Users/graham/Backup/asystem/.gitexternal . /Users/graham/Backup/asystem", DIR_ROOT)
    _print_footer("asystem", "backup")


def _pull(context):
    _print_header("asystem", "pull main")
    _run_local(context, "git remote set-url origin https://github.com/$(git remote get-url origin | "
                        "sed 's/https:\\/\\/github.com\\///' | sed 's/git@github.com://')")
    _run_local(context, "git pull --all")
    _print_footer("asystem", "pull main")
    if _run_local(context, "pwd", hide='out').stdout.strip().split('/')[-1] == "asystem":
        _print_header("asystem", "pull dependencies")
        py_all_dict = {}
        py_all_path = join(DIR_ROOT, "py_all.txt")
        with open(py_all_path) as py_all_file:
            for py_all_line in py_all_file:
                if py_all_line.strip() != "" and not py_all_line.strip().startswith("#"):
                    if "==" not in py_all_line:
                        raise Exception("Error parsing line [{}] from python module file [{}], "
                                        "not a comment nor a versioned python module".format(py_all_line.strip(), py_all_path))
                    elif py_all_line.split("==")[0].strip() in py_all_dict:
                        raise Exception("Error parsing line [{}] from python module file [{}], "
                                        "duplicate python module".format(py_all_line.strip(), py_all_path))
                    else:
                        py_all_dict[py_all_line.split("==")[0].strip()] = py_all_line.split("==")[1].strip()
        for py_mod_path in glob.glob(join(DIR_ROOT_MODULE, "*/*/*/py_*.txt")):
            py_mod_versioned_path = join(py_mod_path.removesuffix(basename(py_mod_path)), "." + basename(py_mod_path))
            with open(py_mod_versioned_path, "w") as py_mod_versioned_file:
                with open(py_mod_path) as py_mod_file:
                    for py_mod_line in py_mod_file:
                        if py_mod_line.strip() != "" and not py_mod_line.strip().startswith("#"):
                            if py_mod_line.strip() not in py_all_dict:
                                raise Exception("Error parsing line [{}] from python module file [{}], "
                                                "python module version not found in file [{}]" \
                                                .format(py_mod_line.strip(), py_mod_path, py_all_path))
                            else:
                                py_mod_versioned_file.write(
                                    "{}=={}\n".format(py_mod_line.strip(), py_all_dict[py_mod_line.strip()]))
        _run_local(context, "pip install --default-timeout=1000 -r {}".format(py_all_path))
        _run_local(context, "pip list --outdated")
        _print_footer("asystem", "pull dependencies")
    _generate(context, filter_changes=False, is_pull=True)


def _generate(context, filter_module=None, filter_changes=True, filter_host=None, is_release=False, is_pull=False):
    version_types = [
        "up to date",
        "to update",
        "errors",
    ]
    version_regexs = [
        r"Module \[.*(?P<module_path>\.deps.*)\] \[INFO\].*\[(?P<version_checkedout>.*)\].*",
        r"Module \[.*(?P<module_path>\.deps.*)\] \[WARN\].*\[(?P<version_checkedout>.*)\].*\[(?P<version_upstream>.*)\]",
        r"Module \[.*(?P<module_path>\.deps.*)\] \[ERROR\] (?P<version_error>.*)",
    ]
    version_formats = [
        "Module [{}] is up to date with version [{}]",
        "Module [{}] requires update from version [{}] to [{}]",
        "Module [{}] threw errors determining versions: {}",
    ]
    version_messages = {type: [] for type in version_types}
    module_generate_stdout = {}
    for module in _get_modules(context, filter_module=filter_module, filter_changes=filter_changes):
        _print_header(module, "generate env", host=filter_host)
        _write_env(context, module, join(DIR_ROOT_MODULE, module, "target/release") if is_release else join(DIR_ROOT_MODULE, module),
                   filter_host=filter_host, is_release=is_release)
        _print_footer(module, "generate env", host=filter_host)
    for module in _get_modules(context, "src/build/python/*/generate.py", filter_changes=False):
        _print_header(module, "generate python script", host=filter_host)
        _run_local(context, "python {}/{}/src/build/python/{}/generate.py".format(DIR_ROOT_MODULE, module, _name(module)), DIR_ROOT)
        _print_footer(module, "generate python script", host=filter_host)
    for module in _get_modules(context, "generate.sh", filter_changes=False):
        _print_header(module, "generate shell script", host=filter_host)
        module_generate_stdout[module] = \
            _run_local(context, "{}/{}/generate.sh {}".format(DIR_ROOT_MODULE, module, is_pull), join(DIR_ROOT_MODULE, module)).stdout
        _print_footer(module, "generate shell script", host=filter_host)
    if is_pull:
        for module in module_generate_stdout:
            for line in module_generate_stdout[module].splitlines():
                for i in range(3):
                    match = re.match(version_regexs[i], line)
                    if match is not None:
                        version_messages[version_types[i]].append(version_formats[i].format(*match.groupdict().values()))

        def get_docker_image_metadata(config_path, config_regexs):
            with open(config_path, 'r') as config_file:
                for config_line in config_file:
                    for config_regex in config_regexs:
                        config_match = re.match(config_regex, config_line.strip())
                        if config_match is not None:
                            docker_image_metadata_dict = {"namespace": "library", "skipped": False} | config_match.groupdict()
                            if docker_image_metadata_dict["version_current"].startswith("$GO_VERSION"):
                                docker_image_metadata_dict["skipped"] = True
                            docker_image_metadata_version_tokens = docker_image_metadata_dict["version_current"].split('-', 1)
                            docker_image_metadata_version_suffix = "$" if len(docker_image_metadata_version_tokens) == 1 else \
                                (".*-" + docker_image_metadata_version_tokens[-1] + "$")
                            for config_version_regex in [
                                r"^v([0-9]*\.[0-9]*\.[0-9]*)" + docker_image_metadata_version_suffix,
                                r"^([0-9]*\.[0-9]*\.[0-9]*)" + docker_image_metadata_version_suffix,
                                r"^([0-9]*\.[0-9]*)" + docker_image_metadata_version_suffix,
                            ]:
                                if re.match(config_version_regex, docker_image_metadata_dict["version_current"]):
                                    docker_image_metadata_dict["version_regex"] = config_version_regex
                                    break
                            return docker_image_metadata_dict

        for module in _get_modules(context, filter_module=filter_module, filter_changes=filter_changes):
            docker_image_metadata = None
            docker_file_path = join(DIR_ROOT_MODULE, module, "Dockerfile")
            docker_compose_path = join(DIR_ROOT_MODULE, module, "docker-compose.yml")
            if exists(docker_file_path):
                docker_image_metadata = get_docker_image_metadata(docker_file_path, [
                    r"FROM (?P<namespace>.*)/(?P<repository>.*):(?P<version_current>.*) AS image_base",
                    r"FROM (?P<repository>.*):(?P<version_current>.*) AS image_base",
                ])
            elif exists(docker_compose_path):
                docker_image_metadata = get_docker_image_metadata(docker_compose_path, [
                    r"image: (?P<namespace>.*)/(?P<repository>.*):(?P<version_current>.*)",
                    r"image: (?P<repository>.*):(?P<version_current>.*)",
                ])
            if docker_image_metadata is not None and \
                    all(key in docker_image_metadata for key in
                        ["namespace", "repository", "version_current", "version_regex", "skipped"]) \
                    and not docker_image_metadata["skipped"]:
                if not docker_image_metadata["version_current"].startswith("$GO_VERSION"):
                    docker_image_tags_url = "https://hub.docker.com/v2/namespaces/{}/repositories/{}/tags?page_size=150" \
                        .format(docker_image_metadata["namespace"], docker_image_metadata["repository"])
                    print("Getting docker image versions from [{}] ... ".format(docker_image_tags_url), end="", flush=True)
                    docker_image_tags_json = requests.get(docker_image_tags_url).json()
                    print("done", flush=True)
                    docker_image_tags = []
                    if "results" in docker_image_tags_json:
                        for docker_image_metatdata_hub in \
                                sorted(docker_image_tags_json["results"], key=lambda x: x['last_updated'], reverse=True):
                            docker_image_version = docker_image_metatdata_hub["name"]
                            if not any(substring.lower() in docker_image_version.lower()
                                       for substring in ["rc", ".0b", "beta", "windows"]) and any(
                                i.isdigit() for i in docker_image_version):
                                docker_image_tags.append(docker_image_version)
                                docker_image_version_match = re.match(docker_image_metadata["version_regex"], docker_image_version)
                                if docker_image_version_match is not None and \
                                        version.parse(docker_image_version_match.groups()[0]) >= \
                                        version.parse(re.match(docker_image_metadata["version_regex"],
                                                               docker_image_metadata["version_current"]).groups()[0]):
                                    docker_image_metadata["version_upstream"] = docker_image_version
                                    break;
                    else:
                        version_messages[version_types[2]] \
                            .append(version_formats[2].format(module, "Could not determine versions from Docker Hub API request [{}]"
                                                              .format(docker_image_tags_url)))
                    if "version_upstream" in docker_image_metadata:
                        version_type = 0 if docker_image_metadata["version_current"] == docker_image_metadata["version_upstream"] else 1
                        version_messages[version_types[version_type]].append(version_formats[version_type].format(
                            module,
                            docker_image_metadata["version_current"],
                            docker_image_metadata["version_upstream"]
                        ))
                    else:
                        version_messages[version_types[2]].append(version_formats[2].format(
                            module, "Could not get upstream version with current [{}], regex [{}] and upstream versions:\n{}"
                            .format(
                                docker_image_metadata["version_current"],
                                docker_image_metadata["version_regex"],
                                "\n".join(docker_image_tags))))
            elif exists(docker_file_path) or exists(docker_compose_path):
                if docker_image_metadata is None or "skipped" not in docker_image_metadata or not docker_image_metadata["skipped"]:
                    version_messages[version_types[2]].append(version_formats[2].format(
                        module, "Could not determine versions from parsed metadata {}".format(docker_image_metadata)))
        for type in version_types:
            _print_header("asystem", "pull versions {}".format(type), host=filter_host)
            for message in sorted(version_messages[type]):
                print(message)
            _print_footer("asystem", "pull versions {}".format(type), host=filter_host)


def _clean(context, filter_module=None, filter_host=None):
    if filter_module is not None:
        _print_header("asystem", "clean transients", host=filter_host)
        _run_local(context, "find . -name *.pyc -prune -exec rm -rf {} \\;")
        _run_local(context, "find . -name __pycache__ -prune -exec rm -rf {} \\;")
        _run_local(context, "find . -name .pytest_cache -prune -exec rm -rf {} \\;")
        _run_local(context, "find . -name .coverage -prune -exec rm -rf {} \\;")
        _run_local(context, "find . -name Cargo.lock -prune -exec rm -rf {} \\;")
        _print_footer("asystem", "clean transients", host=filter_host)
    for module in _get_modules(context, filter_module=filter_module, filter_changes=False):
        _print_header(module, "clean target", host=filter_host)

        # TODO: Disable deleting .env, leave last build in place for running push.py scripts
        # _run_local(context, "rm -rf {}/{}/.env".format(DIR_ROOT, module))

        _run_local(context, "rm -rf {}/{}/target".format(DIR_ROOT_MODULE, module))
        _print_footer(module, "clean target", host=filter_host)
    _run_local(context, "find . -name .DS_Store -exec rm -r {} \\;")


def _build(context, filter_module=None, filter_host=None, is_release=False):
    for module in _get_modules(context, filter_module=filter_module):
        _print_header(module, "build process", host=filter_host)
        _process_target(context, module, is_release)
        _print_footer(module, "build process", host=filter_host)
    for module in _get_modules(context, "src", filter_module=filter_module):
        _print_header(module, "build compile", host=filter_host)
        if isdir(join(DIR_ROOT_MODULE, module, "src/main/python")):
            _print_line("Linting sources ...")

            # TODO: Re-enable once I have cleaned up python codebases
            # _run_local(context, "pylint --disable=all src/main/python/*", module)

        if isfile(join(DIR_ROOT_MODULE, module, "src/setup.py")):
            _run_local(context, "python setup.py sdist", join(module, "target/package"))
        if isdir(join(DIR_ROOT_MODULE, module, "src/main/go/pkg")):
            _run_local(context, "[ ! -d ${GOPATH} ] && mkdir -vp ${GOPATH}/{bin,src,pkg} || true")
            _run_local(context, "go mod tidy", join(module, "src/main/go/pkg"))
            _run_local(context, "go mod download", join(module, "src/main/go/pkg"))
            _run_local(context, "GOCACHE={} go build".format(join(DIR_ROOT_MODULE, module, "target/gocache")),
                       join(module, "src/main/go/pkg"))
        if isdir(join(DIR_ROOT_MODULE, module, "src/main/go/cmd")):
            _run_local(context, "go mod tidy", join(module, "src/main/go/cmd"))
            _run_local(context, "go mod download", join(module, "src/main/go/cmd"))
        if isdir(join(DIR_ROOT_MODULE, module, "src/test/go/unit")):
            _run_local(context, "go mod tidy", join(module, "src/test/go/unit"))
            _run_local(context, "go mod download", join(module, "src/test/go/unit"))
        if isdir(join(DIR_ROOT_MODULE, module, "src/test/go/system")):
            _run_local(context, "go mod tidy", join(module, "src/test/go/system"))
            _run_local(context, "go mod download", join(module, "src/test/go/system"))
        cargo_file = join(DIR_ROOT_MODULE, module, "Cargo.toml")
        if isfile(cargo_file):
            _run_local(context, "mkdir -p target/package && cp -rvfp Cargo.toml target/package", module, hide='err', warn=True)
            with open(cargo_file, 'r') as cargo_file_source:
                cargo_file_text = cargo_file_source.read()
                cargo_file_text = cargo_file_text.replace('version = "0.0.0-SNAPSHOT"', 'version = "{}"'.format(_get_versions()[0]))
                cargo_file_text = cargo_file_text.replace('path = "src/', 'path = "')
                with open(join(DIR_ROOT_MODULE, module, 'target/package/Cargo.toml'), 'w') as cargo_file_destination:
                    cargo_file_destination.write(cargo_file_text)
            _run_local(context, "cargo update && cargo build", join(module, "target/package"))
        _print_footer(module, "build compile", host=filter_host)


def _unittest(context, filter_module=None):
    for module in _get_modules(context, "src/test/python/unit/unit_test.py", filter_module=filter_module):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "python unit_test.py", join(module, "src/test/python/unit"))
        _print_footer(module, "unittest")
    for module in _get_modules(context, "src/test/go/unit/unit_test.go", filter_module=filter_module):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "go mod tidy", join(module, "src/test/go/unit"))
        _run_local(context, "go mod download", join(module, "src/test/go/unit"))
        _run_local(context, "go test --race", join(module, "src/test/go/unit"))
        _print_footer(module, "unittest")
    for module in _get_modules(context, "src/test/rust/unit/unit_test.rs", filter_module=filter_module):
        _print_header(module, "unittest")
        _print_line("Running unit tests ...")
        _run_local(context, "cargo test", join(module, "target/package"))
        _print_footer(module, "unittest")


def _package(context, filter_module=None, filter_host=None, is_release=False):
    for module in _get_modules(context, "Dockerfile", filter_module=filter_module):
        _print_header(module, "package", host=filter_host)
        host_arch = HOSTS[_get_host(module) if filter_host is None else _get_host_label(filter_host)][1]
        if is_release and host_arch != "x86_64":
            _run_local(context, "docker buildx build "
                                "--progress=plain "
                                "--build-arg PYTHON_VERSION "
                                "--build-arg GO_VERSION "
                                "--platform linux/{} --output type=docker --tag {}:{} ."
                       .format(host_arch, _name(module), _get_versions()[0]), module)
        else:
            _run_local(context, "docker image build "
                                "--progress=plain "
                                "--build-arg PYTHON_VERSION "
                                "--build-arg GO_VERSION "
                                "--tag {}:{} ."
                       .format(_name(module), _get_versions()[0]), module)
        _print_footer(module, "package", host=filter_host)


def _systest(context, filter_module=None):
    for module in _get_modules(context, "src/test/*/system", filter_module=filter_module):
        _up_module(context, module)
        _print_header(module, "systest")
        test_exit_code = 1
        if isfile(join(DIR_ROOT_MODULE, module, "src/test/python/system/system_test.py")):
            test_exit_code = _run_local(context, "python system_test.py", join(module, "src/test/python/system"), warn=True).exited
        elif isdir(join(DIR_ROOT_MODULE, module, "src/test/go/system")):
            _run_local(context, "go mod tidy", join(module, "src/test/go/system"))
            _run_local(context, "go mod download", join(module, "src/test/go/system"))
            test_exit_code = _run_local(context, "go test --race", join(module, "src/test/go/system"), warn=True).exited
        else:
            print("Could not find test to run")
        _down_module(context, module)
        if test_exit_code != 0:
            _print_line("Tests ... failed")
            _run_local(context, "false")
        _print_footer(module, "systest")


def _execute(context):
    for module in _get_modules(context, "docker-compose.yml"):
        _up_module(context, module, up_this=False)
        _print_header(module, "execute")

        def server_stop(signal, frame):
            _down_module(context, module)

        signal.signal(signal.SIGINT, server_stop)
        run_dev_path = join(DIR_ROOT_MODULE, module, "run_dev.sh")
        if isfile(run_dev_path):
            _run_local(context, "run_dev.sh", module)
        else:
            _run_local(context, "docker compose --ansi never up --force-recreate --remove-orphans", module)
        _print_footer(module, "execute")
        break


def _deploy(context):
    for module in _get_modules(context, "deploy.sh"):
        _print_header(module, "deploy")
        _run_local(context, "./deploy.sh", module)
        _run_local(context,
                   "[ -f docker-compose.yaml ] && echo 'Tail logs command: while true; do sleep 1 && docker logs -f {} 2>&1; done' || true"
                   .format(_get_service(module)), module)
        _print_footer(module, "deploy")


def _release(context):
    modules = _get_modules(context)
    for module in modules:
        if FAB_SKIP_TESTS not in os.environ:
            _generate(context, filter_module=module)
            _build(context, filter_module=module)
            _unittest(context, filter_module=module)
            _systest(context, filter_module=module)
    _get_versions_next_release()
    if FAB_SKIP_GIT not in os.environ:
        print("Tagging repository ...")
        _run_local(context, "git add -A && git commit -m 'Update asystem-{}' && git tag -a {} -m 'Release asystem-{}'"
                   .format(_get_versions()[0], _get_versions()[0], _get_versions()[0]), env={"HOME": os.environ["HOME"]})
    for module in modules:
        for host in _get_hosts(module):
            _clean(context, filter_module=module, filter_host=host)
            _generate(context, filter_module=module, filter_host=host, is_release=True)
            _build(context, filter_module=module, filter_host=host, is_release=True)
            _package(context, filter_module=module, filter_host=host, is_release=True)
            _print_header(module, "release", host=host)
            host_up = True
            try:
                ssh_pass = _ssh_pass(context, host)
            except:
                host_up = False
            group_path = Path(join(DIR_ROOT_MODULE, module, ".group"))
            if group_path.exists() and group_path.read_text().strip().isnumeric() and int(group_path.read_text().strip()) >= 0 and host_up:
                _run_local(context, "mkdir -p target/release", module)
                _run_local(context, "cp -rvfp docker-compose.yml target/release", module, hide='err', warn=True)
                if isfile(join(DIR_ROOT_MODULE, module, "Dockerfile")):
                    file_image = "{}-{}.tar.gz".format(_name(module), _get_versions()[0])
                    print("docker -> target/release/{}".format(file_image))
                    _run_local(context, "docker image save {}:{} | pigz -9 > {}"
                               .format(_name(module), _get_versions()[0], file_image), join(module, "target/release"))
                if glob.glob(join(DIR_ROOT_MODULE, module, "target/package/main/resources/*")):
                    _run_local(context, "cp -rvfp target/package/main/resources/* target/release", module)
                _run_local(context, "mkdir -p target/release/config", module)
                Path(join(DIR_ROOT_MODULE, module, "target/release/hosts")) \
                    .write_text("\n".join(["{}-{}".format(HOSTS[host][0], host) for host in HOSTS]) + "\n")
                if glob.glob(join(DIR_ROOT_MODULE, module, "target/package/install*")):
                    _run_local(context, "cp -rvfp target/package/install* target/release", module)
                else:
                    _run_local(context, "touch target/release/install.sh", module)
                install = "{}/{}/{}".format(DIR_INSTALL, _get_service(module), _get_versions()[0])
                print("Copying release to {} ... ".format(host))
                _run_local(context, "{}ssh -q root@{} 'rm -rf {} && mkdir -p {}'"
                           .format(ssh_pass, host, install, install))
                _run_local(context, "{}scp -qprO $(find target/release -maxdepth 1 -type f) root@{}:{}"
                           .format(ssh_pass, host, install), module)
                _run_local(context, "{}scp -qprO target/release/config root@{}:{}"
                           .format(ssh_pass, host, install), module)
                print("Installing release to {} ... ".format(host))
                _run_local(context, "{}ssh -q root@{} 'rm -f {}/../latest && ln -sfv {} {}/../latest'"
                           .format(ssh_pass, host, install, install, install))
                _run_local(context, "{}ssh -q root@{} 'chmod +x {}/install.sh && {}/install.sh'"
                           .format(ssh_pass, host, install, install))
                _run_local(context, "{}ssh -q root@{} 'docker system prune --volumes -f'"
                           .format(ssh_pass, host), hide='err', warn=True)
                _run_local(context, "{}ssh -q root@{} 'find $(dirname {}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | "
                                    "head -n $(($(find $(dirname {}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | wc -l) - 2)) | "
                                    "xargs rm -rf'"
                           .format(ssh_pass, host, install, install), hide='err', warn=True)
                install_local_path = Path(join(DIR_ROOT_MODULE, module, "install_local.sh"))
                if install_local_path.exists():
                    _run_local(context, install_local_path)
            else:
                print("Module ignored")
            _print_footer(module, "release", host=host)
    _get_versions_next_snapshot()
    if FAB_SKIP_GIT not in os.environ:
        print("Pushing repository ...")
        _run_local(context, "git add -A && git commit -m 'Update asystem-{}' && git push --all && git push origin --tags"
                   .format(_get_versions()[0], _get_versions()[0], _get_versions()[0]), env={"HOME": os.environ["HOME"]})


def _group(module):
    return dirname(module)


def _name(module):
    return basename(module)


def _get_module_paths(context):
    module_paths = {}
    for module_path in _run_local(context, "find {} -not -path '{}/.*' -type d -mindepth 2 -maxdepth 2"
            .format(DIR_ROOT_MODULE, DIR_ROOT_MODULE), hide='out').stdout.strip().split("\n"):
        module_path_elements = module_path.split("/")
        module_paths[module_path_elements[-1]] = "{}/{}".format(module_path_elements[-2], module_path_elements[-1])
    return module_paths


def _get_modules_all(filter_path=None):
    modules = {}
    for module_path in glob.glob(join(DIR_ROOT_MODULE, "*/*")):
        group_path = Path(join(module_path, ".group"))
        if isfile(group_path) and group_path.read_text().strip().isdigit() and int(group_path.read_text().strip()) >= 0 and \
                (filter_path is None or isfile(join(module_path, filter_path))):
            module = module_path.replace(dirname(dirname(module_path)) + "/", "")
            for host in _get_hosts(module):
                if host not in modules:
                    modules[host] = []
                modules[host].append(_get_service(module))
    return modules


def _get_modules(context, filter_path=None, filter_module=None, filter_changes=True):
    if filter_module is None:
        working_modules = []
        filter_changes = filter_changes if \
            (FAB_SKIP_DELTA not in os.environ and
             FAB_SKIP_GROUP_BELOW not in os.environ and
             FAB_SKIP_GROUP_ABOVE not in os.environ) \
            else False
        working_dirs = _run_local(context, "pwd", hide='out').stdout.strip().split('/')
        root_dir_index = working_dirs.index("asystem")
        if "src" not in working_dirs or working_dirs.index("src") == (len(working_dirs) - 1):
            for filtered_module in \
                    [module_tmp for module_tmp in glob.glob("{}*/*".format("src/" if "src" not in working_dirs else ""))
                     if isdir(module_tmp) and (not filter_changes or _run_local(context, "git status --porcelain {}"
                            .format(module_tmp), DIR_ROOT, hide='out').stdout
                    )]:
                working_modules.append(filtered_module.replace("src/", ""))
        else:
            if (root_dir_index + 3) < len(working_dirs):
                working_modules.append(working_dirs[root_dir_index + 2] + "/" + working_dirs[root_dir_index + 3])
            else:
                for nested_modules in [module_tmp for module_tmp in glob.glob('*') if isdir(module_tmp)]:
                    working_modules.append("{}/{}".format(working_dirs[root_dir_index + 2], nested_modules))
        working_modules[:] = [module for module in working_modules
                              if filter_path is None or glob.glob("{}/{}/{}*".format(DIR_ROOT_MODULE, module, filter_path))]
        grouped_modules = {}
        for module in working_modules:
            group_path = Path(join(DIR_ROOT_MODULE, module, ".group"))
            group = int(group_path.read_text().strip()) if group_path.exists() else -1
            if (FAB_SKIP_GROUP_BELOW not in os.environ or int(os.environ[FAB_SKIP_GROUP_BELOW]) > group) and \
                    (FAB_SKIP_GROUP_ABOVE not in os.environ or int(os.environ[FAB_SKIP_GROUP_ABOVE]) < group):
                if group not in grouped_modules:
                    grouped_modules[group] = [module]
                else:
                    grouped_modules[group].append(module)
        sorted_modules = []
        for group in sorted(grouped_modules):
            sorted_modules.extend(grouped_modules[group])
        module_services = [_get_service(module) for module in sorted_modules]
        if (len(set(module_services)) != len(module_services)):
            raise Exception("Non-unique service names {} detected in module definitions"
                            .format([service for service, count in collections.Counter(module_services).items() if count > 1]))
        return sorted_modules
    else:
        return [filter_module] if filter_path is None or glob.glob("{}/{}/{}*".format(DIR_ROOT_MODULE, filter_module, filter_path)) else []


def _ssh_pass(context, host):
    ssh_prefix = "sshpass -f /Users/graham/.ssh/.password " \
        if _run_local(context,
                      "ssh -q -o StrictHostKeyChecking=no -o PasswordAuthentication=no -o BatchMode=yes -o ConnectTimeout=1 root@{} exit"
                      .format(host), hide="err", warn=True).exited > 0 else ""
    if _run_local(context, "{}ssh -q -o ConnectTimeout=1 root@{} 'echo Connected to {}'".format(ssh_prefix, host, host), hide="err",
                  warn=True).exited > 0:
        raise Exception("Error connecting to server via [{}ssh -q root@{}]".format(ssh_prefix, host))
    return ssh_prefix


def _get_service(module):
    return module.split("/")[1]


def _get_host(module):
    return module.split("/")[0].split("_")[0]


def _get_host_label(host):
    return host.split("-")[1]


def _get_hosts(module):
    return [(HOSTS[host][0] + "-" + host) for host in module.split("/")[0].split("_")]


def _get_dependencies(context, module):
    run_deps = []
    run_deps_path = join(DIR_ROOT_MODULE, module, "run_deps.txt")
    module_paths = _get_module_paths(context)
    if isfile(run_deps_path):
        with open(run_deps_path, "r") as run_deps_file:
            for run_dep in run_deps_file:
                run_dep = run_dep.strip()
                if run_dep != "" and not run_dep.startswith("#"):
                    run_deps.append(module_paths[run_dep] if run_dep in module_paths else run_dep)
    return run_deps + [module]


def _write_env(context, module, working_path=".", filter_host=None, is_release=False):
    service = _get_service(module)
    _run_local(context, "mkdir -p {}".format(working_path), module)
    _run_local(context, "echo 'GO_VERSION=$GO_VERSION' > {}/.env"
               .format(working_path), module)
    _run_local(context, "echo 'PYTHON_VERSION=$PYTHON_VERSION\n' >> {}/.env"
               .format(working_path), module)
    _run_local(context, "echo 'SERVICE_NAME={}' >> {}/.env"
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
                       "{}/{}/target/runtime-system".format(DIR_ROOT_MODULE, module), working_path), module)
    for dependency in _get_dependencies(context, module):
        host_ips_prod = []
        host_names_prod = _get_hosts(dependency) if _name(module) != _name(dependency) or filter_host is None else [filter_host]
        _run_local(context, "dscacheutil -flushcache")
        for host in host_names_prod:
            host_ip = _run_local(context, "dig +short {}".format(host), hide='out').stdout.strip()
            if host_ip == "":
                host_ip = "127.0.1.1"
            elif host_ip == "127.0.1.1":
                host_ip = "10.0.0.1"
            else:
                "10.0.2." + host_ip.split('.')[3]
            host_ips_prod.append(host_ip)
        host_ip_prod = ",".join(host_ips_prod)
        host_name_prod = ",".join(host_names_prod)
        host_name_dev = "host.docker.internal"
        host_ip_dev = _run_local(context, "[[ $(ipconfig getifaddr en0) != \"\" ]] && " +
                                 "ipconfig getifaddr en0 || ipconfig getifaddr en1", hide='out').stdout.strip()
        dependency_service = _get_service(dependency).upper()
        dependency_domain = "{}.local.janeandgraham.com".format(dependency_service.lower())
        _run_local(context, "echo '' >> {}/.env".format(working_path))
        _run_local(context, "echo '{}_IP={}' >> {}/.env"
                   .format(dependency_service, host_ip_prod if is_release else host_ip_dev, working_path), module)
        _run_local(context, "echo '{}_HOST={}' >> {}/.env"
                   .format(dependency_service, host_name_prod if is_release else host_name_dev, working_path), module)
        _run_local(context, "echo '{}_SERVICE={}' >> {}/.env"
                   .format(dependency_service, dependency_domain if is_release else host_name_dev, working_path), module)
        _run_local(context, "echo '{}_IP_PROD={}' >> {}/.env"
                   .format(dependency_service, host_ip_prod, working_path), module)
        _run_local(context, "echo '{}_HOST_PROD={}' >> {}/.env"
                   .format(dependency_service, host_name_prod, working_path), module)
        _run_local(context, "echo '{}_SERVICE_PROD={}' >> {}/.env"
                   .format(dependency_service, dependency_domain, working_path), module)
        for dependency_env_file in [".env_all", ".env_prod" if is_release else ".env_dev", ".env_all_key"]:
            dependency_env_dev = "{}/{}/{}".format(DIR_ROOT_MODULE, dependency, dependency_env_file)
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
                   .format(" ".join(["$" + sub for sub in list(env.keys())]),
                           source_root, source_path, source_path, source_path, source_path), destination_root, env=env)


def _process_target(context, module, is_release=False):
    _run_local(context, "mkdir -p target/package && cp -rvfp src/* install* target/package", module, hide='err', warn=True)
    package_resource_path = join(DIR_ROOT_MODULE, module, "src/resources.txt")
    if isfile(package_resource_path):
        with open(package_resource_path, "r") as package_resource_file:
            for package_resource in package_resource_file:
                package_resource = package_resource.strip()
                if package_resource != "" and not package_resource.startswith("#"):
                    package_resource = package_resource.replace("../install", "install")
                    package_resource_source = DIR_ROOT if package_resource == "install.sh" and \
                                                          not isfile(join(DIR_ROOT_MODULE, module, package_resource)) \
                        else join(DIR_ROOT_MODULE, module, "target/package")
                    _substitue_env(context, join(DIR_ROOT_MODULE, module, "target/release/.env" if is_release else ".env"),
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


def _up_module(context, module, up_this=True):
    if isfile(join(DIR_ROOT_MODULE, module, "docker-compose.yml")):
        for run_dep in _get_dependencies(context, module):
            _clean(context, filter_module=run_dep)
            _generate(context, filter_module=run_dep)
            _build(context, filter_module=run_dep)
            _package(context, filter_module=run_dep)
            _print_header(run_dep, "run prepare")
            _run_local(context, "mkdir -p target/runtime-system", run_dep)
            dir_config = join(DIR_ROOT_MODULE, run_dep, "target/package/main/resources/config")
            if isdir(dir_config) and len(os.listdir(dir_config)) > 0:
                _run_local(context, "cp -rvfp $(find {} -mindepth 1 -maxdepth 1) target/runtime-system".format(dir_config), run_dep)
            _print_footer(run_dep, "run prepare")
            if run_dep != module or up_this:
                _print_header(run_dep, "run")
                _run_local(context, "docker compose --ansi never up --force-recreate --remove-orphans -d", run_dep)
                _print_footer(run_dep, "run")


def _down_module(context, module, down_this=True):
    if isfile(join(DIR_ROOT_MODULE, module, "docker-compose.yml")):
        _print_line("Stopping servers ...")
        for run_dep in reversed(_get_dependencies(context, module)):
            if run_dep != module or down_this:
                _run_local(context, "docker compose --ansi never down -v", run_dep)


def _run_local(context, command, working=".", **kwargs):
    with context.cd(join("./" if working == "." else DIR_ROOT_MODULE, working)):
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
    version_next_absolute = "{}.{}.{}".format(
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


def _print_header(module, stage, host=None):
    label = module if host is None else module.replace(_get_host_label(host), "[" + _get_host_label(host) + "]")
    _print_line(HEADER.format(stage.upper(), label.lower().replace('/', '-'), _get_versions()[0]))


def _print_footer(module, stage, host=None):
    label = module if host is None else module.replace(_get_host_label(host), "[" + _get_host_label(host) + "]")
    _print_line(FOOTER.format(stage.upper(), label.lower().replace('/', '-'), _get_versions()[0]))


DIR_HOME = "/home/asystem"
DIR_INSTALL = "/var/lib/asystem/install"
DIR_ROOT = dirname(abspath(__file__))
DIR_ROOT_MODULE = join(DIR_ROOT, "src")

FILE_ENV = join(dirname(abspath(__file__)), ".env_fab")

HOSTS = {line.split("=")[0]: line.split("=")[-1].split(",")
         for line in Path(join(dirname(abspath(__file__)), ".hosts")).read_text().strip().split("\n")}

HEADER = \
    "------------------------------------------------------------\n" \
    "{} STARTING: {}-{}\n" \
    "------------------------------------------------------------"
FOOTER = \
    "------------------------------------------------------------\n" \
    "\033[32m{} SUCCESSFUL: {}-{}\033[00m\n" \
    "------------------------------------------------------------"
