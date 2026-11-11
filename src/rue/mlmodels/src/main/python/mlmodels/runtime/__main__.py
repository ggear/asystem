import sys
import time
from os.path import join

from .loader import ModelError, build, read_json, read_project, replay
from .served import load_served


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) not in (1, 3):
        print("ERROR usage consumer <project dir> [<server> <name>]", file=sys.stderr)
        return 2
    try:
        findings = run(arguments[0], arguments[1:] or None)
    except (ModelError, ValueError) as error:
        print(f"ERROR [{error}]", file=sys.stderr)
        return 1
    for rule, message in findings:
        print(f"ERROR {rule} [{message}]", file=sys.stderr)
    return 1 if findings else 0


def run(directory, served):
    started = time.monotonic()
    project = read_project(directory)
    report("verify", f"{len(project.manifest['files']) + 1} files", started)
    started = time.monotonic()
    model = build(directory, project)
    predict = model.predict
    if served is not None:
        predict = load_served(f"{served[0]}/v2/models/{served[1]}/infer", project.signature_json)
    report("load", project.manifest["flavour"] if served is None else "served", started)
    started = time.monotonic()
    findings = replay(directory, model.signature(), predict)
    steps = sum(len(sequence["steps"]) for sequence in read_json(join(directory, "golden.json"))["sequences"])
    report("replay", f"{steps} steps", started)
    return findings


def report(stage, detail, started):
    print(f"    {stage:<12} ... done [{detail}] ({time.monotonic() - started:.2f}s)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
