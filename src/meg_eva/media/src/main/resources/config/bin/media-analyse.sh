#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

for SHARE_DIR in ${SHARE_DIRS}; do ${PYTHON_DIR}/python ${ROOT_DIR}/lib/analyse.py ${SHARE_DIR}/media "14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8"; done
