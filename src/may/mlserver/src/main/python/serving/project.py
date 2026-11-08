import hashlib
import json
from os.path import isfile, join

from . import run_onnx, run_pyfunc, run_static, run_wasm


class Project:
    def __init__(self, directory, manifest, signature_json):
        self.directory = directory
        self.manifest = manifest
        self.signature_json = signature_json
        self.signature = json.loads(signature_json)
        self.name = manifest["name"]
        self._predict = None

    def predict(self, inputs):
        required = {entry["name"] for entry in self.signature["inputs"] if entry["parameters"]["required"]}
        if not required <= inputs.keys():
            raise ValueError(f"missing required inputs [{sorted(required - inputs.keys())}]")
        if self._predict is None:
            self._predict = _predictor(self.manifest, self.directory, self.signature_json)
        return self._predict(inputs)


def load_project(directory):
    manifest_path = join(directory, "project.json")
    if not isfile(manifest_path):
        raise ValueError(f"manifest missing [{manifest_path}]")
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
    for name, sha256 in manifest["files"].items():
        path = join(directory, name)
        if not isfile(path):
            raise ValueError(f"file absent [{name}]")
        digest = hashlib.sha256()
        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != sha256:
            raise ValueError(f"file checksum mismatch [{name}]")
    if manifest["flavour"] != "static" and "evaluation.json" not in manifest["files"]:
        raise ValueError(f"no acceptance evaluation for flavour [{manifest['flavour']}]")
    if "evaluation.json" in manifest["files"]:
        with open(join(directory, "evaluation.json")) as evaluation_file:
            if json.load(evaluation_file).get("passed") is not True:
                raise ValueError("acceptance not passed")
    with open(join(directory, "signature.json")) as signature_file:
        signature_json = signature_file.read()
    return Project(directory, manifest, signature_json)


def _predictor(manifest, directory, signature_json):
    flavour = manifest["flavour"]
    if flavour == "static":
        return run_static.load_static(json.dumps(manifest["constants"]), signature_json)
    loaders = {"wasm": run_wasm.load_wasm, "onnx": run_onnx.load_onnx, "pyfunc": run_pyfunc.load_pyfunc}
    if flavour not in loaders:
        raise ValueError(f"no consumer for flavour [{flavour}]")
    return loaders[flavour](join(directory, manifest["model"]), signature_json)
