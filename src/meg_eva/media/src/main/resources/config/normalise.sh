#!/bin/bash

SHARE_DIR=${1}
if [ ! -d "${SHARE_DIR}" ]; then
  echo "Usage: ${0} <share-dir>"
  exit 1
fi
echo -n "Normalising ${SHARE_DIR} ... "
if [ "$(grep -c graham /etc/passwd)" -gt 0 ] && [ "$(grep -c users /etc/group)" -gt 0 ]; then
  setfacl -bR "${SHARE_DIR}"
  find "${SHARE_DIR}" -type f -exec chmod 640 {} \;
  find "${SHARE_DIR}" -type d -exec chmod 750 {} \;
  find "${SHARE_DIR}" -exec chown graham:users {} \;
  find "${SHARE_DIR}" -type f -name nohup -exec rm -f {} \;
  find "${SHARE_DIR}" -type f -name .DS_Store -exec rm -f {} \;
else
  find "${SHARE_DIR}" -type f -exec chmod 666 {} \;
  find "${SHARE_DIR}" -type d -exec chmod 777 {} \;
fi
echo "done"
