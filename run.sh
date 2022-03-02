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
SERVICE_HOST_IP=$(ifconfig $(ifconfig | grep enp | cut -d':' -f1) | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*')
SERVICE_HOST_NAME=$(hostname)

cd ${SERVICE_INSTALL} || exit
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
    cp -rvfp "$SERVICE_HOME_OLD" "$SERVICE_HOME"
  else
    mkdir -p "${SERVICE_HOME}"
    chmod 777 "${SERVICE_HOME}"
  fi
  rm -rvf $SERVICE_HOME_OLDEST
fi

rm -f ../latest && ln -sfv . ../latest
rm -f ${SERVICE_HOME}/../latest && ln -sfv ${SERVICE_HOME} ${SERVICE_HOME}/../latest

[ "$(ls -A config | wc -l)" -gt 0 ] && cp -rvfp $(find config -mindepth 1 -maxdepth 1) "${SERVICE_HOME}"
touch .env
chmod 600 .env
[ -f "./run_pre.sh" ] && chmod +x ./run_pre.sh && ./run_pre.sh
[ -f "docker-compose.yml" ] && docker-compose --compatibility --no-ansi up --force-recreate -d && sleep 2
[ -f "./run_post.sh" ] && chmod +x ./run_post.sh && ./run_post.sh
if [ -f "docker-compose.yml" ]; then
  if [ $(docker ps -f name="${SERVICE_NAME}" | grep -c "$SERVICE_NAME") -eq 0 ]; then
    echo && echo "Container failed to start" && echo && exit 1
  else
    docker system prune --volumes -f -a 2>&1 >/dev/null
  fi
  echo "----------" && docker ps -f name="${SERVICE_NAME}" && echo "----------"

  if [ $(docker ps | grep "${SERVICE_NAME}_bootstrap" | wc -l) -eq 1 ]; then
    docker logs "${SERVICE_NAME}_bootstrap" -f
  fi
  sleep 5 && docker logs "${SERVICE_NAME}" && echo "----------"
fi
