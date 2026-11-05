#!/usr/bin/env bash

set -o nounset
set -o errexit
set -o pipefail

export PYTHONPATH="/asystem/bin/python${PYTHONPATH:+:${PYTHONPATH}}"

timeout 600 python3 -m registry.sync --once || echo "WARN initial sync failed, the server starts with what is on disk"
python3 -m registry.sync &
exec mlserver start "${MLFLOW_MODEL_DIR}"
