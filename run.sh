#!/bin/sh
###############################################################################
#
# Generic service run script
#
###############################################################################

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_HOME_OLD=$(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | head -n 1)
SERVICE_HOME_OLDEST=$(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | tail -n -$(($(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | wc -l) - 1)) 2>/dev/null)
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_HOST_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1')

cd "${SERVICE_INSTALL}" || exit
[ -f "${SERVICE_NAME}-${VERSION_ABSOLUTE}.tar.gz" ] && docker image load -i ${SERVICE_NAME}-${VERSION_ABSOLUTE}.tar.gz
docker stop "${SERVICE_NAME}" 2>&1 >/dev/null || docker wait "${SERVICE_NAME}" 2>&1 >/dev/null
if [ ! -d "$SERVICE_HOME" ]; then
  if [ -d "$SERVICE_HOME_OLD" ]; then
    cp -rvf "$SERVICE_HOME_OLD" "$SERVICE_HOME"
  else
    mkdir -p "${SERVICE_HOME}"
  fi
  rm -rvf "$SERVICE_HOME_OLDEST"
fi
[ "$(ls -A config | wc -l)" -gt 0 ] && cp -rvf $(find config -mindepth 1) "${SERVICE_HOME}"
VERSION=${VERSION_ABSOLUTE} DATA_DIR="${SERVICE_HOME}" LOCAL_IP="${SERVICE_HOST_IP}" docker-compose --no-ansi up --force-recreate -d
