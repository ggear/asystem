#!/bin/bash

SHARE_DIR=${1}
if [ ! -d "${SHARE_DIR}" ]; then
  echo "Usage: ${0} <share-dir>"
  exit 1
fi
echo -n "Cleaning ${SHARE_DIR} ... "
find ${SHARE_DIR} -name "*_metatdata.yaml" -delete
echo "done"
