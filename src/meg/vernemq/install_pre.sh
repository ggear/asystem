#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

if [ "${SERVICE_COMMAND:-install}" != "install" ]; then
  echo "Retained store flush skipped, command [${SERVICE_COMMAND:-unknown}] is not [install]"
  exit 0
fi

echo "Flushing the retained store [${SERVICE_DATA_DIR}/data]"
rm -rf "${SERVICE_DATA_DIR:?}/data"
mkdir -p "${SERVICE_DATA_DIR}/data"
chmod 1777 "${SERVICE_DATA_DIR}/data"
