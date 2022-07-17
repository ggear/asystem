#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

export $(xargs <${ROOT_DIR}/.env)

export VERNEMQ_HOST=${VERNEMQ_HOST_PROD}

${ROOT_DIR}/src/main/resources/config/publish.sh
