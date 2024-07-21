#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

echo "Storage status ... done" && df -h $(echo ${SHARE_DIRS} | tr '\n' ' ') | cut -c 40-
