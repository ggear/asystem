#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit

. ${SERVICE_INSTALL}/.env

scp -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@${NGINX_IP}:/home/asystem/nginx/latest/.key.pem
scp -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@${NGINX_IP}:/home/asystem/nginx/latest/certificate.pem
ssh -q -o "StrictHostKeyChecking=no" root@${NGINX_IP} "cd /var/lib/asystem/install/nginx/latest && docker-compose --compatibility restart"
logger -t pushcerts "Loaded new nginx certificates on ${NGINX_IP}"

scp -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@${UDMUTILITIES_IP}:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
scp -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@${UDMUTILITIES_IP}:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
ssh -q -o "StrictHostKeyChecking=no" root@${UDMUTILITIES_IP} "unifi-os restart"
logger -t pushcerts "Loaded new unifi certificates on ${UDMUTILITIES_IP}"
