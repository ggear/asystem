#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

for SHARE_DIR in ${SHARE_DIRS}; do ${ROOT_DIR}/lib/clean.sh ${SHARE_DIR}; done
