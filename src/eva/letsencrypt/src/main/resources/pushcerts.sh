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
      while read -r HOSTS; do
        CERTIFICATE_HOST_PULL=$(echo "${HOSTS}" | cut -d ' ' -f1)
        CERTIFICATE_HOST_PUSH=$(echo "${HOSTS}" | cut -d ' ' -f2)
        CERTIFICATE_SERVICE_NAME=$(echo "${HOSTS}" | cut -d ' ' -f3)
        ssh -n -q -o "StrictHostKeyChecking=no" root@${CERTIFICATE_HOST_PUSH} "find /var/lib/asystem/install/${CERTIFICATE_SERVICE_NAME}/latest/config -name certificates.sh -exec {} pull ${CERTIFICATE_HOST_PULL} ${CERTIFICATE_HOST_PUSH} \;"
        ssh -n -q -o "StrictHostKeyChecking=no" root@${CERTIFICATE_HOST_PUSH} "find /var/lib/asystem/install/${CERTIFICATE_SERVICE_NAME}/latest/config -name certificates.sh -exec {} push ${CERTIFICATE_HOST_PULL} ${CERTIFICATE_HOST_PUSH} \;"
        logger -t pushcerts "Pushed new certificates to [${CERTIFICATE_HOST_PUSH}]"
      done </var/lib/asystem/install/letsencrypt/latest/pushcerts-hosts.txt
    fi
  fi
done
