#!/bin/sh

while read -r HOSTS; do
  CERTIFICATE_HOST_PULL=$(echo "${HOSTS}" | cut -d ' ' -f1)
  CERTIFICATE_HOST_PUSH=$(echo "${HOSTS}" | cut -d ' ' -f2)
  CERTIFICATE_SERVICE_NAME=$(echo "${HOSTS}" | cut -d ' ' -f3)
  ssh -n -q -o "StrictHostKeyChecking=no" root@${CERTIFICATE_HOST_PUSH} "find /var/lib/asystem/install/${CERTIFICATE_SERVICE_NAME}/latest/config -name certificates.sh -exec {} pull ${CERTIFICATE_HOST_PULL} ${CERTIFICATE_HOST_PUSH} \;"
  ssh -n -q -o "StrictHostKeyChecking=no" root@${CERTIFICATE_HOST_PUSH} "find /var/lib/asystem/install/${CERTIFICATE_SERVICE_NAME}/latest/config -name certificates.sh -exec {} push ${CERTIFICATE_HOST_PULL} ${CERTIFICATE_HOST_PUSH} \;"
  logger -t pushcerts "Pushed new certificates to [${CERTIFICATE_HOST_PUSH}]"
done </var/lib/asystem/install/letsencrypt/latest/pushcerts-hosts.txt
