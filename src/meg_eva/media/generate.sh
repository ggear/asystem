#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

cp -rvf ${ROOT_DIR}/src/reqs_run.txt ${ROOT_DIR}/src/main/resources/config/.reqs.txt
for FILE in "rename.py" "analyse.py"; do
  echo -e "\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n" > ${ROOT_DIR}/src/main/resources/config/${FILE}
  cat ${ROOT_DIR}/src/main/python/media/${FILE} >> ${ROOT_DIR}/src/main/resources/config/${FILE}
done
