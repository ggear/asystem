#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")
HOSTS=$(echo ${HOSTS} | xargs -n1 | sort | xargs)
HOST="$(grep $(echo "${HOSTS}" | head -1) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(echo "${HOSTS}" | head -1)"

echo "------------------------------------------------------------" && echo "Server [${HOST}] media truncate starting"
#ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/bin/media-truncate.sh"
#ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/bin/media-refresh.sh"
echo "Server [${HOST}] media truncate completed" && echo "------------------------------------------------------------"

for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  echo "------------------------------------------------------------" && echo "Server [${HOST}] media operations starting"
  ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/bin/media-clean.sh"
#  ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/bin/media-analyse.sh"
  ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/bin/media-space.sh"
  echo "Server [${HOST}] media operations completed" && echo "------------------------------------------------------------"
done
