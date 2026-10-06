#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# DEFINED: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION=${MLSERVER_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "mlserver" "mlserver" "seldonio/mlserver" "${VERSION}" || exit $?
