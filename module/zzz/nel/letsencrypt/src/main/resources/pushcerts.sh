#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit
[ ! -d "./certificates" ] && [ -d "./letsencrypt/archive/janeandgraham.com" ] && cp -rvfpL letsencrypt/live/janeandgraham.com certificates && logger -t pushcerts "Cached existing certificates"
while :; do
  if [ $(fswatch -1 "${SERVICE_HOME}/letsencrypt/live/janeandgraham.com" | wc -l) -gt 0 ]; then
    sleep 5
    [ ! -d "./certificates" ] && mkdir "./certificates" && touch "./certificates/privkey.pem"
    if [ -f ./letsencrypt/live/janeandgraham.com/privkey.pem ] && [ $(diff ./certificates/privkey.pem ./letsencrypt/live/janeandgraham.com/privkey.pem | wc -l) -gt 0 ]; then
      cp -rvfpL letsencrypt/live/janeandgraham.com/* certificates &&
        cat ./certificates/fullchain.pem ./certificates/privkey.pem >./certificates/fullchain_privkey.pem &&
        logger -t pushcerts "Cached new certificates"
      if [ -f ${SERVICE_INSTALL}/hosts ]; then
        cat ${SERVICE_INSTALL}/hosts | while read host; do
          NGINX_HOME=$(ssh -q -n -o "StrictHostKeyChecking=no" -o ConnectTimeout=2 root@${host} "[[ -d /home/asystem/nginx/latest ]] && echo /home/asystem/nginx/latest")
          NGINX_INSTALL=$(ssh -q -n -o "StrictHostKeyChecking=no" -o ConnectTimeout=2 root@${host} "[[ -d /var/lib/asystem/install/nginx/latest ]] && echo /var/lib/asystem/install/nginx/latest")
          if [ "${NGINX_HOME}" != ""  ] && [ "${NGINX_INSTALL}" != "" ]; then
            scp -qo "StrictHostKeyChecking=no" ./certificates/privkey.pem root@${host}:"${NGINX_HOME}/.key.pem"
            scp -qo "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@${host}:"${NGINX_HOME}/certificate.pem"
            ssh -qno "StrictHostKeyChecking=no" root@${host} "cd ${NGINX_INSTALL} && docker-compose --compatibility restart"
            logger -t pushcerts "Loaded new nginx certificates on ${host}"
          fi
        done
      fi
      scp -qo "StrictHostKeyChecking=no" ./certificates/privkey.pem root@udm-net:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
      scp -qo "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@udm-net:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
      ssh -qo "StrictHostKeyChecking=no" root@udm-net "unifi-os restart"
      logger -t pushcerts "Loaded new unifi certificates on udm-net"
    fi
  fi
done