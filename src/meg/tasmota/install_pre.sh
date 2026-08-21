#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

if [ "${SERVICE_VERSION_CHANGED:-true}" != "true" ]; then
  echo "Broker publish skipped, version [${SERVICE_VERSION_ABSOLUTE:-unknown}] unchanged by command [${SERVICE_COMMAND:-unknown}]"
  exit 0
fi

"${ROOT_DIR}/image/broker.sh"

