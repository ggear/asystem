#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

if [[ $(uname) == "Linux" ]]; then
  "${ROOT_DIR}/lib/ingress.sh" /share/10
  exit $?
fi
exit 0
