#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

HOST_NGINX="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:/home/asystem/letsencrypt/latest/certificates/privkey.pem" "${ROOT_DIR}/src/main/resources/config/.key.pem"
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:/home/asystem/letsencrypt/latest/certificates/fullchain.pem" "${ROOT_DIR}/src/main/resources/config/certificate.pem"
echo "Pulled latest nginx certificate"
