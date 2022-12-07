#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit

. ${SERVICE_INSTALL}/.env

scp -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@${NGINX_HOST}:/home/asystem/nginx/latest/.key.pem
scp -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@${NGINX_HOST}:/home/asystem/nginx/latest/certificate.pem
ssh -qno "StrictHostKeyChecking=no" root@${NGINX_HOST} "cd /var/lib/asystem/install/nginx/latest && docker-compose --compatibility restart"
logger -t pushcerts "Loaded new nginx certificates on ${NGINX_HOST}"

scp -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@${UDMUTILITIES_HOST}:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
scp -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@${UDMUTILITIES_HOST}:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
ssh -qno "StrictHostKeyChecking=no" root@${UDMUTILITIES_HOST} "unifi-os restart"
logger -t pushcerts "Loaded new unifi certificates on ${UDMUTILITIES_HOST}"
