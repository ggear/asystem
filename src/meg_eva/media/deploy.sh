#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

cp -rvf ${ROOT_DIR}/src/main/resources/config/bin/lib/other-transcode.rb /usr/local/bin/other-transcode
chmod +x /usr/local/bin/other-transcode

chmod +x ${ROOT_DIR}/src/main/resources/config/bin/*.sh ${ROOT_DIR}/src/main/resources/config/bin/lib/*.sh
for SCRIPT in ${ROOT_DIR}/src/main/resources/config/bin/*.sh; do
  rm -rf /usr/local/bin/asystem-$(basename ${SCRIPT} .sh)
  ln -vs ${SCRIPT} /usr/local/bin/asystem-$(basename ${SCRIPT} .sh)
done

HOST="$(grep $(echo "${HOSTS}" | head -1) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(echo "${HOSTS}" | head -1)"
echo "------------------------------------------------------------" && echo "Server [${HOST}] media clean starting"
ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/config/bin/media-clean.sh"
echo "Server [${HOST}] media clean completed" && echo "------------------------------------------------------------"

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")
for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  echo "------------------------------------------------------------" && echo "Server [${HOST}] media operations starting"
  ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/media/latest/config/bin/media.sh"
  echo "Server [${HOST}] media operations completed" && echo "------------------------------------------------------------"
done


