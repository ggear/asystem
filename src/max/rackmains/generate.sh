#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODEL_DIR="${ROOT_DIR}/src/build/resources/model"

export PYTHONPATH="${ROOT_DIR}/../../all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"
if [ "${1}" == "True" ]; then
  MLFLOW_TRACKING_URI="$(sed -n 's/^MLFLOW_TRACKING_URI=//p' "${ROOT_DIR}/../../may/mlflow/.env_all")"
  export MLFLOW_TRACKING_URI
  python -m asystem.model pull rackmains_ups_battery release "${MODEL_DIR}/release" --signature "${MODEL_DIR}/default/signature.json" || exit $?
fi
python -m asystem.model verify "${MODEL_DIR}/default" || exit $?
python -m asystem.model verify "${MODEL_DIR}/release" || exit $?
