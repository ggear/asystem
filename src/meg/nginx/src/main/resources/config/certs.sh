#!/bin/bash

ROOT_DIR=$(realpath $(readlink -f "$0")/../../../../..)

HOST_NGINX="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

if [ -z "${1}" ] || [ "${1}" = "pull" ]; then
  mkdir -p "${ROOT_DIR}/src/main/resources"
  scp -qpr "root@${HOST_LETSENCRYPT}:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com/privkey.pem" "${ROOT_DIR}/src/main/resources/config/.key.pem"
  scp -qpr "root@${HOST_LETSENCRYPT}:/home/asystem/letsencrypt/latest/letsencrypt/live/janeandgraham.com/fullchain.pem" "${ROOT_DIR}/src/main/resources/config/certificate.pem"
  echo "Pulled latest certificates from [@${HOST_LETSENCRYPT}] to [@localhost:${ROOT_DIR}/src/main/resources/config]"
elif [ "${1}" = "push" ]; then
  for DIR in "/home/asystem/nginx/latest" "/var/lib/asystem/install/nginx/latest/config"; do
    scp -qpr "${ROOT_DIR}/src/main/resources/config/.key.pem" "root@${HOST_NGINX}:${DIR}"
    scp -qpr "${ROOT_DIR}/src/main/resources/config/certificate.pem" "root@${HOST_NGINX}:${DIR}"
    echo "Pushed local certificates to [@${HOST_NGINX}:${DIR}]"
  done
  echo "Restarting service on [@${HOST_NGINX}] ... "
  ssh "root@${HOST_NGINX}" "/var/lib/asystem/install/nginx/latest/install.sh"
fi
