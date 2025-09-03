#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# Defined: [/asystem/.env_fab](https://github.com/ggear/asystem/blob/master/.env_fab)
pull_repo "${ROOT_DIR}" "${1}" "python" "pyenv" "pyenv/pyenv" "${PYENV_VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv"
mkdir -p "${ROOT_DIR}/src/main/resources"
cp -rvf "${ROOT_DIR}/../../../.deps/python/pyenv" "${ROOT_DIR}/src/main/resources"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv/.git"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv/.github"
