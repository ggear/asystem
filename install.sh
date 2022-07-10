#!/bin/sh
###############################################################################
#
# Generic service run script, to be invoked by the fabric management script
#
###############################################################################

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_HOME_OLD=$(find $(dirname ${SERVICE_HOME}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1)
SERVICE_HOME_OLDEST=$(find $(dirname ${SERVICE_HOME}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | head -n $(($(find $(dirname ${SERVICE_HOME}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | wc -l) - 1)))
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
[ -f "./install_prep.sh" ] && chmod +x ./install_prep.sh && ./install_prep.sh || true
[ -f "${SERVICE_NAME}-${SERVICE_VERSION_ABSOLUTE}.tar.gz" ] && docker image load -i ${SERVICE_NAME}-${SERVICE_VERSION_ABSOLUTE}.tar.gz
if [ -f "docker-compose.yml" ]; then
  docker stop "${SERVICE_NAME}" >/dev/null 2>&1
  docker stop "${SERVICE_NAME}" >/dev/null 2>&1
  docker wait "${SERVICE_NAME}" >/dev/null 2>&1
  docker wait "${SERVICE_NAME}" >/dev/null 2>&1
  docker system prune --volumes -f 2>&1 >/dev/null
fi
if [ ! -d "$SERVICE_HOME" ]; then
  if [ -d "$SERVICE_HOME_OLD" ]; then
    cp -rfp "$SERVICE_HOME_OLD" "$SERVICE_HOME"
  else
    mkdir -p "${SERVICE_HOME}"
    chmod 777 "${SERVICE_HOME}"
  fi
  rm -rf $SERVICE_HOME_OLDEST
fi
rm -f ${SERVICE_HOME}/../latest && ln -sfv ${SERVICE_HOME} ${SERVICE_HOME}/../latest
[ "$(ls -A config | wc -l)" -gt 0 ] && cp -rfp $(find config -mindepth 1 -maxdepth 1) "${SERVICE_HOME}"
touch .env
chmod 600 .env
[ -f "./install_pre.sh" ] && chmod +x ./install_pre.sh && ./install_pre.sh || true
if [ -f "docker-compose.yml" ]; then
  docker-compose --compatibility --no-ansi up --force-recreate -d
  if [ $(docker ps | grep "${SERVICE_NAME}_bootstrap" | wc -l) -eq 1 ]; then
    docker logs "${SERVICE_NAME}_bootstrap" -f
  fi
  echo "----------" && docker ps -f name="${SERVICE_NAME}" && echo "----------"
  sleep 5 && docker logs "${SERVICE_NAME}" && echo "----------"
  if [ $(docker ps -f name="${SERVICE_NAME}" | grep -c "$SERVICE_NAME") -eq 0 ]; then
    echo && echo "Container failed to start" && echo "" && exit 1
  else
    docker system prune --volumes -f -a 2>&1 >/dev/null
    echo "Container started successfully ..." && echo "----------"
  fi
fi
[ -f "./install_post.sh" ] && chmod +x ./install_post.sh && ./install_post.sh || true
