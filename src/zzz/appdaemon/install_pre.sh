#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest

rm -rf ${SERVICE_HOME}/apps && cp -rf ${ROOT_DIR}/data/apps ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/dashboards && cp -rf ${ROOT_DIR}/data/dashboards ${SERVICE_HOME}
