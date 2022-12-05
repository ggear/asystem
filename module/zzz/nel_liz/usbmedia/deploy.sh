#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  echo "------------------------------------------------------------" && echo "IMPORT MEDIA: ${HOST}" && echo ""
  ssh -o StrictHostKeyChecking=no root@${HOST} "\$(find /root/install/usbmedia -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1)/config/import.sh"
  echo "------------------------------------------------------------"
done
