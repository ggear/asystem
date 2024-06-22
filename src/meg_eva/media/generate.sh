#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

cp -rvf ${ROOT_DIR}/src/reqs_run.txt ${ROOT_DIR}/src/main/resources/config/.python_reqs.txt
for FILE in "rename.py" "analyse.py"; do
  cp -rvf ${ROOT_DIR}/src/main/python/media/${FILE} ${ROOT_DIR}/src/main/resources/config
  echo -e "\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n\n$(cat ${ROOT_DIR}/src/main/resources/config/${FILE})" > ${ROOT_DIR}/src/main/resources/config/${FILE}
done
