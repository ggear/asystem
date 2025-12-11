#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# NOTES: https://github.com/pyenv/pyenv/releases
VERSION=v2.6.16
pull_repo "${ROOT_DIR}" "${1}" "python" "pyenv" "pyenv/pyenv" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv"
mkdir -p "${ROOT_DIR}/src/main/resources"
cp -rvf "${ROOT_DIR}/../../../.deps/python/pyenv" "${ROOT_DIR}/src/main/resources"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv/.git"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv/.github"
rm -rf "${ROOT_DIR}/src/main/resources/pyenv/bin/pyenv"
