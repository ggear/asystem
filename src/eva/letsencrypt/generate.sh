#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

mkdir -p "${ROOT_DIR}/src/main/resources/config"
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:/home/asystem/letsencrypt/latest/certificates/privkey.pem" "${ROOT_DIR}/src/main/resources/config/.privkey.pem"
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:/home/asystem/letsencrypt/latest/certificates/fullchain.pem" "${ROOT_DIR}/src/main/resources/config/fullchain.pem"
echo "Pulled latest nginx certificate"
