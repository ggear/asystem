#!/bin/sh
###############################################################################
#
# Generic service run script, to be invoked by the fabric management script
#
###############################################################################

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_HOME_OLD=$(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | head -n 1)
SERVICE_HOME_OLDEST=$(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | tail -n -$(($(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | wc -l) - 1)) 2>/dev/null)
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_HOST_IP=$(ifconfig enp1s0f0 | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*')

cd "${SERVICE_INSTALL}" || exit
[ -f "./run_pre.sh" ] && chmod +x ./run_pre.sh && ./run_pre.sh
[ -f "${SERVICE_NAME}-${VERSION_ABSOLUTE}.tar.gz" ] && docker image load -i ${SERVICE_NAME}-${VERSION_ABSOLUTE}.tar.gz
docker stop "${SERVICE_NAME}" >/dev/null 2>&1
docker wait "${SERVICE_NAME}" >/dev/null 2>&1
docker system prune --volumes -f 2>&1 >/dev/null
if [ ! -d "$SERVICE_HOME" ]; then
  if [ -d "$SERVICE_HOME_OLD" ]; then
    cp -rvfp "$SERVICE_HOME_OLD" "$SERVICE_HOME"
  else
    mkdir -p "${SERVICE_HOME}"
  fi
  rm -rvf "$SERVICE_HOME_OLDEST"
fi
[ "$(ls -A config | wc -l)" -gt 0 ] && cp -rvfp $(find config -mindepth 1) "${SERVICE_HOME}"
touch .env
chmod 600 .env
if [ -f "docker-compose.yml" ] && ([ ! -f ".env" ] || [ $(grep -c "# Installed" .env) -eq 0 ]); then
  cat <<EOF >>.env

# Installed on $(date)
RESTART=always
VERSION=${VERSION_ABSOLUTE}
DATA_DIR=${SERVICE_HOME}
LOCAL_IP=${SERVICE_HOST_IP}
EOF
  [ -f ".config/.profile" ] && sed 's/export //g' config/.profile >>.env
fi
if [ -f ".env" ]; then
  export VERSION=${VERSION_ABSOLUTE}
  export DATA_DIR=${SERVICE_HOME}
  export LOCAL_IP=${SERVICE_HOST_IP}
  envsubst <.env >.env.new && mv -f .env.new .env
fi
docker-compose --no-ansi up --force-recreate -d
[ -f "./run_post.sh" ] && chmod +x ./run_post.sh && ./run_post.sh
sleep 2
if [ $(docker ps -f name="${SERVICE_NAME}" | grep -c "$SERVICE_NAME") -eq 0 ]; then
  echo && echo "Container failed to start" && echo && exit 1
fi
echo "----------" && docker ps -f name="${SERVICE_NAME}"
docker logs "${SERVICE_NAME}" && echo "----------"
