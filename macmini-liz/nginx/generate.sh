#!/bin/sh

ROOT_DIR="$PWD"
while [ "$(basename ${ROOT_DIR})" != "asystem" ]; do ROOT_DIR=$(dirname ${ROOT_DIR}); done
HOST_NGINX=$(basename $(dirname $(find ${ROOT_DIR} -type d -mindepth 1 -maxdepth 2 ! -path '/*/.*' | grep nginx)))
HOST_LETSENCRYPT=$(basename $(dirname $(find ${ROOT_DIR} -type d -mindepth 1 -maxdepth 2 ! -path '/*/.*' | grep letsencrypt)))
DIR_LETSENCRYPT=$(sshpass -f /Users/graham/.ssh/.password ssh -q "root@${HOST_LETSENCRYPT}" 'find /home/asystem/letsencrypt -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1')

sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:${DIR_LETSENCRYPT}/certificates/privkey.pem" "${ROOT_DIR}/${HOST_NGINX}/nginx/src/main/resources/config/.key.pem" 2>/dev/null
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:${DIR_LETSENCRYPT}/certificates/fullchain.pem" "${ROOT_DIR}/${HOST_NGINX}/nginx/src/main/resources/config/certificate.pem" 2>/dev/null
echo "Pulled latest nginx certificate"
