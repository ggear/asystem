#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

pull_repo "${ROOT_DIR}" "${1}" "python" "pyenv" "pyenv/pyenv" "v${PYENVBIN_VERSION}"
[ -e "${ROOT_DIR}/../../../.deps/python/pyenv/plugins/python-build/share/python-build/${PYTHON_VERSION}" ] || { echo "pyenv [${PYENVBIN_VERSION}] has no python-build definition for python [${PYTHON_VERSION}], bump PYENVBIN_VERSION in .env_fab" >&2; exit 1; }
