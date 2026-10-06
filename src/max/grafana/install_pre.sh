#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
# shellcheck disable=SC2153
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest

rm -rf "${SERVICE_HOME}/dashboards" && cp -rf "${ROOT_DIR}/data/dashboards" "${SERVICE_HOME}"
rm -rf "${SERVICE_HOME}/provisioning"
rm -rf "${SERVICE_HOME}/config"
