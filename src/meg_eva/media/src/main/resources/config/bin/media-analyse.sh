#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

if [ ! -z "${SHARE_DIR}" ]; then
  ${PYTHON_DIR}/python ${ROOT_DIR}/lib/analyse.py ${SHARE_DIR}
else
  for SHARE_DIRS_ITEM in ${SHARE_DIRS}; do ${PYTHON_DIR}/python ${ROOT_DIR}/lib/analyse.py ${SHARE_DIRS_ITEM}; done
fi
