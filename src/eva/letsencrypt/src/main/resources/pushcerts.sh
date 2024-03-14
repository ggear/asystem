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

      # TODO: Implement, udm-net ssh from fails?
      # TODO: Build.py to write out hosts file to drive certifcates.sh invocations
      # ssh -q -o "StrictHostKeyChecking=no" root@${NGINX_SERVICE} "/var/lib/asystem/install/nginx/latest/config/certificates.sh push $(hostname) ${NGINX_SERVICE}"
      # ssh -q -o "StrictHostKeyChecking=no" -o "HostKeyAlgorithms=+ssh-rsa" -o "PubkeyAcceptedAlgorithms=+ssh-rsa" root@${UDMUTILITIES_SERVICE} "/var/lib/asystem/install/udmutilities/latest/config/certificates.sh push $(hostname) ${UDMUTILITIES_SERVICE}"

      logger -t pushcerts "Pushed new certificates"
    fi
  fi
done
