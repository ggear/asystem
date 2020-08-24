#!/bin/sh

set -x

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit
[ ! -d "./certificates" ] && [ -d "./letsencrypt/archive/janeandgraham.com" ] && cp -rvfpL letsencrypt/live/janeandgraham.com certificates
[ ! -d "./certificates" ] && mkdir "./certificates" && touch "./certificates/cert.pem"
if [ $(fswatch -1 -x --event=Updated "${SERVICE_HOME}/letsencrypt/live/janeandgraham.com/privkey.pem" | grep -c "Updated") -eq 2 ]; then
  sleep 2
  if [ ! $(cmp ./certificates/cert.pem ./letsencrypt/live/janeandgraham.com/cert.pem >/dev/null) ]; then
    cp -rvfpL letsencrypt/live/janeandgraham.com/* certificates
    cat ./certificates/fullchain.pem ./certificates/privkey.pem >./certificates/fullchain_privkey.pem
    if [ -f "${SERVICE_INSTALL}/hosts" ]; then
      while read -r host; do
        ANODE_HOME=$(ssh -o "StrictHostKeyChecking=no" root@${host} \
          "find /home/asystem/anode -maxdepth 1 -mindepth 1 | sort | tail -n 1")
        ANODE_INSTALL=$(ssh -o "StrictHostKeyChecking=no" root@${host} \
          "find /var/lib/asystem/install/\$(hostname)/anode -maxdepth 1 -mindepth 1 | sort | tail -n 1")
        if [ -n "${ANODE_HOME}" ] && [ -n "${ANODE_INSTALL}" ]; then
          scp -o "StrictHostKeyChecking=no" \
            ./certificates/fullchain_privkey.pem root@${host}:"${ANODE_HOME}/.pem"
          scp -o "StrictHostKeyChecking=no" root@${host} \
            "docker-compose -f "${ANODE_INSTALL}"/docker-compose.yml --env-file "${ANODE_INSTALL}"/.env restart"
        fi
      done <"${SERVICE_INSTALL}/hosts"
    fi
    scp -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@unifi:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
    scp -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@unifi:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
    ssh -o "StrictHostKeyChecking=no" root@unifi "unifi-os restart"
    logger "Loaded new ASystem certificates"
  fi
fi
