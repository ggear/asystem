#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

# shellcheck disable=SC1091
. "${ROOT_DIR}/.env"

# shellcheck disable=SC2153
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest

chmod 600 "${SERVICE_HOME}/cluster_1/admin.json" "${SERVICE_HOME}/cluster_1/init.json"
