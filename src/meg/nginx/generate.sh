#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

${ROOT_DIR}/src/main/resources/config/certs.sh pull
