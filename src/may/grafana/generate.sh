#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# Defined: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
VERSION="${GRIZZLY_VERSION}"
pull_repo "${ROOT_DIR}" "${1}" "grafana" "grizzly" "grafana/grizzly" "${VERSION}"

# Notes: https://github.com/grafana/grafonnet-lib/releases
VERSION=ggear-grafonnet
pull_repo "${ROOT_DIR}" "${1}" "grafana" "grafonnet-lib" "ggear/grafonnet-lib" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/image/libraries/grafonnet-lib"
mkdir -p "${ROOT_DIR}/src/main/resources/image/libraries/grafonnet-lib"
cp -rvf "${ROOT_DIR}/../../../.deps/grafana/grafonnet-lib/grafonnet" "${ROOT_DIR}/src/main/resources/image/libraries/grafonnet-lib"
