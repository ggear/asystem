#!/bin/bash
###############################################################################
# Generic module install script, to be invoked by the Fabric management script
###############################################################################

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_HOME_OLD=$(find $(dirname ${SERVICE_HOME}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1)
SERVICE_HOME_OLDEST=$(find $(dirname ${SERVICE_HOME}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | head -n $(($(find $(dirname ${SERVICE_HOME}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | wc -l) - 1)))
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
[ -f "./install_prep.sh" ] && chmod +x ./install_prep.sh && ./install_prep.sh || true
cd ${SERVICE_INSTALL} || exit
[ -f "${SERVICE_NAME}-${SERVICE_VERSION_ABSOLUTE}.tar.gz" ] && docker image load -i ${SERVICE_NAME}-${SERVICE_VERSION_ABSOLUTE}.tar.gz
if [ -f "docker-compose.yml" ]; then
  docker stop "${SERVICE_NAME}" >/dev/null 2>&1
  docker stop "${SERVICE_NAME}"_bootstrap >/dev/null 2>&1
  docker wait "${SERVICE_NAME}" >/dev/null 2>&1
  docker wait "${SERVICE_NAME}"_bootstrap >/dev/null 2>&1
  docker system prune --volumes -f 2>&1 >/dev/null
fi
if [ ! -d "$SERVICE_HOME" ]; then
  mkdir -p "${SERVICE_HOME}"
  chmod 777 "${SERVICE_HOME}"
  if [ "$(stat -f -c %T ${SERVICE_HOME})" = "btrfs" ]; then chattr +C ${SERVICE_HOME}; fi
  if [ -d "$SERVICE_HOME_OLD" ]; then
    echo "Copying old home to new ... "
    cp -rfpa "$SERVICE_HOME_OLD/." "$SERVICE_HOME"
  fi
  rm -rf $SERVICE_HOME_OLDEST
fi

[ "$(ls -A data | wc -l)" -gt 0 ] && cp -rfpv $(find data -mindepth 1 -maxdepth 1) "${SERVICE_HOME}"
rm -f ${SERVICE_HOME}/../latest && ln -sfv ${SERVICE_HOME} ${SERVICE_HOME}/../latest
touch .env
chmod 600 .env
[ -f "./install_pre.sh" ] && chmod +x ./install_pre.sh && ./install_pre.sh || true
if [ -f "docker-compose.yml" ]; then
  docker compose --compatibility --ansi never up --force-recreate -d
  if [ $(docker ps | grep "${SERVICE_NAME}_bootstrap" | wc -l) -eq 1 ]; then
    sleep 1
    docker logs "${SERVICE_NAME}_bootstrap" -f
  fi
  echo "----------" && docker ps -f name="${SERVICE_NAME}" && echo "----------"
  if find "${SERVICE_INSTALL}" -name checkexecuting.sh -quit | grep -q . && find "${SERVICE_INSTALL}" -name checkhealthy.sh -quit | grep -q .; then
    echo
    while ! docker exec "${SERVICE_NAME}" /asystem/etc/checkexecuting.sh; do
      echo "Waiting for service to start executing ... " && sleep 1
    done
    echo && echo "Checking service health ... " && echo
    docker exec "${SERVICE_NAME}" /asystem/etc/checkhealthy.sh -v
    service_healthy=$?
    sleep 1 && echo
    [ ${service_healthy} -eq 0 ] && echo "✅ Service is healthy" || echo "❌ Service is unhealthy"
  fi
  if [ $(docker ps -f name="${SERVICE_NAME}" | grep -c "$SERVICE_NAME") -eq 0 ]; then
    echo && echo "Service failed to start" && echo "" && exit 1
  else
    docker system prune --volumes -f -a 2>&1 >/dev/null
    echo "Service started successfully" && echo "----------"
  fi
fi
[ -f "./install_post.sh" ] && chmod +x ./install_post.sh && ./install_post.sh || true
