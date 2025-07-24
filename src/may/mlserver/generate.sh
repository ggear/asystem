#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# Defined: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
pull_repo "${ROOT_DIR}" "${1}" "mlserver" "mlserver" "seldonio/mlserver" "${MLSERVER_VERSION}"
