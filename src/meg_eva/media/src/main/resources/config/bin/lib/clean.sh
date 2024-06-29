#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/../.env

SHARE_DIR=${1}
if [ ! -d "${SHARE_DIR}" ]; then
  echo "Usage: ${0} <share-dir>"
  exit 1
fi

find ${SHARE_DIR} -name "*_metatdata.yaml" -delete
${PYTHON_DIR}/python ${ROOT_DIR}/analyse.py ${SHARE_DIR}/media "14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8" --clean
