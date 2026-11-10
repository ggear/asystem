import importlib
import os
import sys
from typing import TYPE_CHECKING

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../../../all/_/src/build/python"))

if TYPE_CHECKING:
    from mlmodels._errors import GateError as GateError
    from mlmodels.workflow.collect import collect_run as collect_run
    from mlmodels.workflow.define import define_model as define_model
    from mlmodels.workflow.evaluate import evaluate_gate as evaluate_gate
    from mlmodels.workflow.evaluate import evaluate_metrics as evaluate_metrics
    from mlmodels.workflow.evaluate import evaluate_model as evaluate_model
    from mlmodels.workflow.evaluate import evaluate_models as evaluate_models
    from mlmodels.workflow.evaluate import evaluate_plot as evaluate_plot
    from mlmodels.workflow.explore import explore_plot as explore_plot
    from mlmodels.workflow.package import package_model as package_model
    from mlmodels.workflow.prepare import prepare_folds as prepare_folds
    from mlmodels.workflow.prepare import prepare_plot as prepare_plot
    from mlmodels.workflow.prepare import prepare_split as prepare_split
    from mlmodels.workflow.pull import pull_model as pull_model
    from mlmodels.workflow.register import register_model as register_model
    from mlmodels.workflow.setup import setup_workspace as setup_workspace

MLMODELS_API = {
    "setup_workspace": "mlmodels.workflow.setup",
    "collect_run": "mlmodels.workflow.collect",
    "prepare_split": "mlmodels.workflow.prepare",
    "prepare_folds": "mlmodels.workflow.prepare",
    "prepare_plot": "mlmodels.workflow.prepare",
    "explore_plot": "mlmodels.workflow.explore",
    "define_model": "mlmodels.workflow.define",
    "evaluate_model": "mlmodels.workflow.evaluate",
    "evaluate_metrics": "mlmodels.workflow.evaluate",
    "evaluate_gate": "mlmodels.workflow.evaluate",
    "evaluate_models": "mlmodels.workflow.evaluate",
    "evaluate_plot": "mlmodels.workflow.evaluate",
    "package_model": "mlmodels.workflow.package",
    "register_model": "mlmodels.workflow.register",
    "pull_model": "mlmodels.workflow.pull",
    "GateError": "mlmodels._errors",
}


def __getattr__(name):
    if name not in MLMODELS_API:
        raise AttributeError(f"module [mlmodels] has no attribute [{name}]")
    module = importlib.import_module(MLMODELS_API[name])
    return getattr(module, name)
