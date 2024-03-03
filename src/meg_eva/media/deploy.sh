#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  echo "------------------------------------------------------------" && echo "Server [${HOST}] media operations starting"
  ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/config/all.sh"
  echo "Server [${HOST}] media operations completed" && echo "------------------------------------------------------------"
done
