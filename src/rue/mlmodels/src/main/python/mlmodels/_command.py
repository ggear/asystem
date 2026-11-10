import argparse
import json
import logging
import os
import re
import sys
from os.path import isfile, join, relpath

from mlmodels._constants import PROJECT_MANIFEST, PROJECT_SIGNATURE
from mlmodels._errors import GateError
from mlmodels._lint_notebook import fix_notebook, lint_notebook
from mlmodels._lint_project import fix_hints, lint_project, verify_project
from mlmodels._lint_workspace import lint_workspace
from mlmodels._project import write_text
from mlmodels._registry import check_release, registry_address
from mlmodels._runner import ANSI, run_notebook
from mlmodels._scaffold import scaffold_notebook
from mlmodels._signature import render_rust


def model_command(arguments=None):
    parser = argparse.ArgumentParser(prog="mlmodels")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify").add_argument("project_dir")
    commands.add_parser("replay").add_argument("project_dir")
    commands.add_parser("lint").add_argument("project_dir")
    generate = commands.add_parser("generate")
    generate.add_argument("project_dir")
    generate.add_argument("--rust")
    check_release_parser = commands.add_parser("check-release")
    check_release_parser.add_argument("project_dir")
    check_release_parser.add_argument("--source-dir")
    changed = commands.add_parser("changed")
    changed.add_argument("workspace_dir")
    changed.add_argument("pins_path")
    check_metadata = commands.add_parser("check-metadata")
    check_metadata.add_argument("workspace_dir")
    check_metadata.add_argument("pins_path")
    release = commands.add_parser("release")
    release.add_argument("source_dir")
    release.add_argument("--version", required=True)
    release.add_argument("--mlserver")
    publish = commands.add_parser("publish")
    publish.add_argument("source_dir")
    publish.add_argument("--mlserver")
    status = commands.add_parser("status")
    status.add_argument("source_dir")
    status.add_argument("--mlserver")
    docker_args = commands.add_parser("docker-args")
    docker_args.add_argument("source_dir")
    docker_args.add_argument("pins_path")
    embed = commands.add_parser("embed")
    embed.add_argument("consumer_dir")
    embed.add_argument("source_dir")
    embed.add_argument("name")
    options = parser.parse_args(arguments)

    def hints(rules):
        for hint in fix_hints(rules):
            print(f"HINT {hint}", file=sys.stderr)

    def hints_in(text):
        hints(re.findall(r"\b((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3})\b", text))

    try:
        if options.command == "verify":
            print(f"verified model [{verify_project(options.project_dir)['name']}]")
        elif options.command == "lint":
            findings = lint_project(options.project_dir)
            for rule, message in findings:
                print(f"{options.project_dir} {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            return 1 if findings else 0
        elif options.command == "changed":
            from mlmodels._metadata import inputs_changed

            with open(join(options.workspace_dir, "notebook.ipynb")) as notebook_file:
                packages = any(cell["cell_type"] == "code" and "package_model(" in "".join(cell["source"]) for cell in json.load(notebook_file)["cells"])
            if not packages:
                print("unpackaged")
            else:
                print("changed" if inputs_changed(options.workspace_dir, options.pins_path) else "unchanged")
        elif options.command == "check-metadata":
            from mlmodels._metadata import PROJECT_DIR, lint_metadata

            with open(join(options.workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)) as manifest_file:
                findings = lint_metadata(options.workspace_dir, json.load(manifest_file)["flavour"], options.pins_path)
            for rule, message in findings:
                print(f"{options.workspace_dir} {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            return 1 if findings else 0
        elif options.command == "release":
            from mlmodels._release import release_workspaces, stale_consumers

            tracking_uri = registry_address(os.environ.get("MLFLOW_TRACKING_URI"))
            released = release_workspaces(options.source_dir, options.version, tracking_uri, options.mlserver)
            print(f"released workspaces {released}")
            for consumer in stale_consumers(options.source_dir):
                print(f"WARN consumer embeds an older release [{relpath(consumer, options.source_dir)}]", file=sys.stderr)
        elif options.command == "publish":
            from mlmodels._metadata import read_metadata
            from mlmodels._release import publish_workspace, workspaces

            tracking_uri = registry_address(os.environ.get("MLFLOW_TRACKING_URI"))
            for name, directory in workspaces(options.source_dir).items():
                metadata = read_metadata(directory) if isfile(join(directory, "metadata.json")) else None
                if metadata is not None and metadata["release"] is not None and metadata["target"]["kind"] == "served":
                    print(f"published model [{name}] [{publish_workspace(name, directory, tracking_uri, options.mlserver)}]")
        elif options.command == "status":
            from mlmodels._release import status_lines

            for level, message in status_lines(options.source_dir, os.environ.get("MLFLOW_TRACKING_URI") and registry_address(os.environ["MLFLOW_TRACKING_URI"]), options.mlserver):
                print(f"{level} {message}", file=sys.stderr)
        elif options.command == "docker-args":
            from mlmodels._metadata import CONSUMER_PINS, package_key, read_pins, read_runtime
            from mlmodels._release import workspaces

            pins = {package_key(name): (name, version) for name, version in read_pins(options.pins_path, None).items()}
            declared = sorted(
                {package_key(name) for directory in workspaces(options.source_dir).values() if isfile(join(directory, "metadata.json")) for name in read_runtime(directory).get("python", ())}
            )
            unpinned = [name for name in declared if name not in pins]
            if unpinned:
                raise GateError("Image", "runtime", f"python dependencies with no project wide pin {unpinned}")
            wanted = dict.fromkeys((*(package_key(pin) for pin in CONSUMER_PINS if package_key(pin) in pins), *declared))
            print(f'--build-arg "PINS={" ".join(f"{pins[key][0]}=={pins[key][1]}" for key in wanted)}"')
        elif options.command == "embed":
            from mlmodels._release import embed_consumer

            print(f"embed [{embed_consumer(options.consumer_dir, options.source_dir, options.name)}] consumer [{options.consumer_dir}]")
        elif options.command == "check-release":
            findings = check_release(options.project_dir)
            if options.source_dir:
                from mlmodels._release import slot_findings

                findings = [*findings, *slot_findings(options.project_dir, options.source_dir)]
            for rule, message in findings:
                print(f"{options.project_dir} {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            return 1 if findings else 0
        elif options.command == "replay":
            from mlmodels._replay import replay_project

            findings = replay_project(options.project_dir)
            for rule, message in findings:
                print(f"ERROR {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            if findings:
                return 1
            print(f"replayed project [{options.project_dir}]")
        elif options.command == "generate":
            with open(join(options.project_dir, PROJECT_SIGNATURE)) as signature_file:
                signature = json.load(signature_file)
            if options.rust:
                write_text(options.rust, render_rust(signature))
    except GateError as error:
        print(f"FAILED stage [{error.stage}] gate [{error.gate}] [{error.cause}]", file=sys.stderr)
        hints_in(error.cause)
        return 1
    except (ValueError, KeyError, OSError) as error:
        print(f"ERROR model command failed [{options.command}] [{error}]", file=sys.stderr)
        hints_in(str(error))
        return 1
    return 0


def notebook_command(arguments=None):
    parser = argparse.ArgumentParser(prog="mlmodels notebook")
    commands = parser.add_subparsers(dest="command")
    new = commands.add_parser("new")
    new.add_argument("module")
    new.add_argument("model")
    new.add_argument("notebook")
    new.add_argument("flavour")
    new.add_argument("--root", default="src/main/notebook")
    new.add_argument("--local", action="store_true")
    lint = commands.add_parser("lint")
    lint.add_argument("--fix", action="store_true")
    lint.add_argument("paths", nargs="+")
    argv = sys.argv[1:] if arguments is None else arguments
    options = parser.parse_args(argv if argv and argv[0] in ("new", "lint") else ["lint", *argv])
    if options.command == "new":
        try:
            for path in scaffold_notebook(options.root, options.module, options.model, options.notebook, options.flavour, options.local):
                print(f"created [{path}]")
        except ValueError as error:
            print(f"ERROR notebook command failed [new] [{error}]", file=sys.stderr)
            return 1
        return 0
    failed = False
    for path in options.paths:
        if options.fix and fix_notebook(path):
            print(f"stripped outputs [{path}]")
        for rule, message, cell in lint_notebook(path):
            failed = True
            print(f"{path} [{'cell ' + str(cell) if cell is not None else 'notebook'}] {rule} {message}", file=sys.stderr)
    return 1 if failed else 0


def run_command(arguments=None):
    logging.getLogger("IPKernelApp").setLevel(logging.ERROR)
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 5:
        print("ERROR usage mlmodels run <workspace dir> <output dir> <register 0|1> <pins path> <source dir>", file=sys.stderr)
        return 2
    workspace_dir, output_dir, register, pins_path, source_dir = arguments
    try:
        run_notebook(workspace_dir, output_dir, register == "1", pins_path, source_dir)
    except Exception as error:
        print(f"ERROR {ANSI.sub('', str(error))}", file=sys.stderr)
        return 1
    return 0


def workspace_command(arguments=None):
    parser = argparse.ArgumentParser(prog="mlmodels workspace")
    parser.add_argument("paths", nargs="+")
    options = parser.parse_args(arguments)
    failed = False
    for path in options.paths:
        for rule, message in lint_workspace(path):
            failed = True
            print(f"{path} {rule} {message}", file=sys.stderr)
    return 1 if failed else 0


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    commands = {"notebook": notebook_command, "workspace": workspace_command, "run": run_command}
    if arguments and arguments[0] in commands:
        return commands[arguments[0]](arguments[1:])
    return model_command(arguments)
