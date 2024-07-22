#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

[[ $(uname) == "Linux" ]] && "${ROOT_DIR}/lib/import.sh" /share/2
