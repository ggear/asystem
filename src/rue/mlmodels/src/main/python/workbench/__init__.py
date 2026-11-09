import importlib
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../../../all/_/src/build/python"))

WORKBENCH_API = {
    "setup_workspace": "workbench.stage",
    "data_load": "workbench.data",
    "explore_plot": "workbench.plot",
    "data_plot": "workbench.plot",
    "evaluate_curves": "workbench.plot",
    "train_wasm_build": "workbench.wasm",
    "train_wasm_trace": "workbench.wasm",
    "evaluate_check": "workbench.model",
    "evaluate_measure": "workbench.model",
    "evaluate_predict": "workbench.replay",
    "evaluate_error_plot": "workbench.plot",
    "package_workspace": "workbench.stage",
    "register_workspace": "workbench.stage",
}


def __getattr__(name):
    if name not in WORKBENCH_API:
        raise AttributeError(f"module [workbench] has no attribute [{name}]")
    module = importlib.import_module(WORKBENCH_API[name])
    return getattr(module, name)
