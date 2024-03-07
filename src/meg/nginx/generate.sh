#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

${ROOT_DIR}/src/main/resources/config/certs.sh pull ${HOST_LETSENCRYPT} ${HOST}
