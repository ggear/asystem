#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

[[ $(uname) == "Linux" ]] && "${ROOT_DIR}/lib/ingress.sh" /share/3
