#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

"${ROOT_DIR}/media-normalise.sh"
"${ROOT_DIR}/media-rename.sh"
"${ROOT_DIR}/media-analyse.sh"
"${ROOT_DIR}/media-refresh.sh"
"${ROOT_DIR}/media-report.sh"
