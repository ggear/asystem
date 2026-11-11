import json
import logging

from mlmodels._constants import PROJECT_FLAVOURS, RUN_FIRST
from mlmodels._errors import GateError
from mlmodels._model import model_content, model_install

LOG = logging.getLogger(__name__)


def define_model(ws, *, model, flavour, source, label, constants=None, runs=None):
    if isinstance(model, bool) or not isinstance(model, int) or model < RUN_FIRST or model in ws.models:
        raise GateError("Define", "model", f"model must be an unused integer from [{RUN_FIRST}] [{model}]")
    if flavour not in PROJECT_FLAVOURS:
        raise GateError("Define", "flavour", f"flavour must be one of {list(PROJECT_FLAVOURS)} [{flavour}]")
    if not isinstance(label, str) or not label.strip():
        raise GateError("Define", "label", f"label must say what model [{model}] is")
    constants = {} if constants is None else dict(constants)
    try:
        json.dumps(constants)
    except TypeError as error:
        raise GateError("Define", "constants", f"constants of model [{model}] must be plain numbers, text, lists and dicts [{error}]") from error
    if runs is None:
        runs = sorted({member.run for member in ws.splits["training"].members}) if "training" in ws.splits else []
    file_name, content, values = model_content(ws, flavour, source, constants)
    ws.models[model] = model_install(ws, model, label, flavour, runs, file_name, content, values)
    ws.models[model].fitted = constants
    LOG.info("Define model [%s] [%s] as [%s] with runs [%s]", model, label, flavour, ", ".join(str(run) for run in runs))
