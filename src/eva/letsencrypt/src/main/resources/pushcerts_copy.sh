#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit

. ${SERVICE_INSTALL}/.env

scp -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@${NGINX_SERVICE}:/home/asystem/nginx/latest/.key.pem
scp -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@${NGINX_SERVICE}:/home/asystem/nginx/latest/certificate.pem
ssh -q -o "StrictHostKeyChecking=no" root@${NGINX_SERVICE} "cd /var/lib/asystem/install/nginx/latest && docker compose --compatibility restart"
logger -t pushcerts "Loaded new nginx certificates on ${NGINX_SERVICE}"

scp -O -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" ./certificates/privkey.pem root@${UDMUTILITIES_SERVICE}:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
scp -O -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" ./certificates/fullchain.pem root@${UDMUTILITIES_SERVICE}:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
ssh -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" root@${UDMUTILITIES_SERVICE} "unifi-os restart"
logger -t pushcerts "Loaded new unifi certificates on ${UDMUTILITIES_SERVICE}"
