#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd "${SERVICE_HOME}" || exit
[ ! -d "./certificates" ] && [ -d "./letsencrypt/archive/janeandgraham.com" ] && cp -rvfpL letsencrypt/live/janeandgraham.com certificates && logger -t pushcerts "Cached existing certificates"
while :; do
  if [ $(fswatch -1 "${SERVICE_HOME}/letsencrypt/live/janeandgraham.com" | wc -l) -gt 0 ]; then
    sleep 5
    [ ! -d "./certificates" ] && mkdir "./certificates" && touch "./certificates/privkey.pem"
    if [ -f ./letsencrypt/live/janeandgraham.com/privkey.pem ] && [ ! $(diff ./certificates/privkey.pem ./letsencrypt/live/janeandgraham.com/privkey.pem | wc -l) -gt 0 ]; then
      cp -rvfpL letsencrypt/live/janeandgraham.com/* certificates &&
        cat ./certificates/fullchain.pem ./certificates/privkey.pem >./certificates/fullchain_privkey.pem &&
        logger -t pushcerts "Cached new certificates"
      if [ -f "${SERVICE_INSTALL}/hosts" ]; then
        while read -r host; do
          ANODE_HOME=$(ssh -q -n -o "StrictHostKeyChecking=no" root@${host} "find /home/asystem/anode -maxdepth 1 -mindepth 1 2>/dev/null | sort | tail -n 1")
          ANODE_INSTALL=$(ssh -q -n -o "StrictHostKeyChecking=no" root@${host} \
            "find /var/lib/asystem/install/\$(hostname)/anode -maxdepth 1 -mindepth 1 2>/dev/null | sort | tail -n 1")
          if [ -n "${ANODE_HOME}" ] && [ -n "${ANODE_INSTALL}" ]; then
            scp -q -o "StrictHostKeyChecking=no" \
              ./certificates/fullchain_privkey.pem root@${host}:"${ANODE_HOME}/.pem"
            ssh -q -n -o "StrictHostKeyChecking=no" root@${host} \
              "docker-compose -f '${ANODE_INSTALL}/docker-compose.yml' --env-file '${ANODE_INSTALL}/.env' restart"
            logger -t pushcerts "Loaded new anode certificates on ${host}"
          fi
        done <"${SERVICE_INSTALL}/hosts"
      fi
      scp -q -o "StrictHostKeyChecking=no" ./certificates/privkey.pem root@udm-rack:/mnt/data/unifi-os/unifi-core/config/unifi-core.key
      scp -q -o "StrictHostKeyChecking=no" ./certificates/fullchain.pem root@udm-rack:/mnt/data/unifi-os/unifi-core/config/unifi-core.crt
      ssh -q -o "StrictHostKeyChecking=no" root@udm-rack "unifi-os restart"
      logger -t pushcerts "Loaded new unifi certificates on udm-rack"
    fi
  fi
done
