#!/bin/bash

set -Eeuo pipefail

BROKER="$(dirname "$(readlink -f "$0")")/image/broker.sh"

[[ "${SERVICE_VERSION_CHANGED:-}" == "true" && -x "${BROKER}" ]] || exit 0

exec "${BROKER}"
