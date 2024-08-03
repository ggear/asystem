#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/../.env_media"

WORKING_DIR=${1}
if [ ! -d "${WORKING_DIR}" ]; then
  echo "Usage: ${0} <working-dir>"
  exit 1
fi

echo -n "Normalising '${WORKING_DIR}' ... "
if [ $(uname) == "Linux" ]; then
  command -v setfacl &>/dev/null && setfacl -bR "${WORKING_DIR}"
  id "graham" &>/dev/null && getent group "users" &>/dev/null && find "${WORKING_DIR}" -exec chown "graham:users" {} \;
  find "${WORKING_DIR}" -type d -exec chmod 750 {} \;
  find "${WORKING_DIR}" -type f -name "*.sh" -exec chmod 750 {} \;
  find "${WORKING_DIR}" -type f ! -name "*.sh" -exec chmod 640 {} \;
fi
find "${WORKING_DIR}" -type f -name nohup -exec rm -f {} \;
find "${WORKING_DIR}" -type f -name .DS_Store -exec rm -f {} \;
echo "done"
