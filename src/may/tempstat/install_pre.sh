#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091 # .env is generated at build time, not available to shellcheck
. "${ROOT_DIR}/.env"

"${ROOT_DIR}/image/vernemq.sh"
