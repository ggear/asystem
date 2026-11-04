#!/usr/bin/env bash

set -o nounset
set -o errexit
set -o pipefail

export PYTHONPATH="/asystem/bin/python${PYTHONPATH:+:${PYTHONPATH}}"

timeout 600 python3 -m project_runtime.pull
exec mlserver start "${MLFLOW_MODEL_DIR}"
