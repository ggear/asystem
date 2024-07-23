#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

"${ROOT_DIR}/lib/refresh.sh"
