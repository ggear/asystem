#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

for SHARE_DIR in ${SHARE_DIRS}; do ${PYTHON_DIR}/python ${ROOT_DIR}/lib/rename.py ${SHARE_DIR}/tmp; done
