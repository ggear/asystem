#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

"${ROOT_DIR}/media-normalise.sh"
"${ROOT_DIR}/media-analyse.sh"
"${ROOT_DIR}/media-refresh.sh"
"${ROOT_DIR}/media-space.sh"
