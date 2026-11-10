#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

for FLAVOUR in static wasm onnx pyfunc; do
  cp "${ROOT_DIR}/../../rue/mlmodels/src/main/python/mlmodels/runtime/${FLAVOUR}.py" "${ROOT_DIR}/src/main/python/serving/${FLAVOUR}.py" || exit $?
done

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${MLSERVER_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "mlserver" "mlserver" "seldonio/mlserver" "${VERSION}" || exit $?
