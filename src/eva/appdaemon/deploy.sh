#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOME="/home/asystem/$(basename ${ROOT_DIR})/latest"
INSTALL="/var/lib/asystem/install/$(basename ${ROOT_DIR})/latest"
HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"

ssh root@${HOST} "rm -rf ${HOME}/apps && rm -rf ${HOME}/dashboards"
scp -r ${ROOT_DIR}/src/main/resources/data/apps ${ROOT_DIR}/src/main/resources/data/dashboards root@${HOST}:${HOME}

