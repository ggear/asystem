#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

HOST_NGINX=$(basename $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name nginx))
HOST_LETSENCRYPT=$(basename $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))
DIR_LETSENCRYPT=$(sshpass -f /Users/graham/.ssh/.password ssh -q "root@${HOST_LETSENCRYPT}" 'find /home/asystem/letsencrypt -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1')

sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:${DIR_LETSENCRYPT}/certificates/privkey.pem" "${ROOT_DIR}/${HOST_NGINX}/nginx/src/main/resources/config/.key.pem" 2>/dev/null
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:${DIR_LETSENCRYPT}/certificates/fullchain.pem" "${ROOT_DIR}/${HOST_NGINX}/nginx/src/main/resources/config/certificate.pem" 2>/dev/null
echo "Pulled latest nginx certificate"
