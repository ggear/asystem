#!/bin/bash

. .env

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

if [ -f "${SERVICE_HOME}/ip_bans.yaml" ]; then
  echo "Flushing IP bans:" && echo "---" && cat "${SERVICE_HOME}/ip_bans.yaml" && echo "---"
  rm -rf "${SERVICE_HOME}/ip_bans.yaml"
fi

rm -rf ${SERVICE_HOME}/custom_components && cp -rf ${SERVICE_INSTALL}/data/custom_components ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/custom_packages && cp -rf ${SERVICE_INSTALL}/data/custom_packages ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/ui-lovelace && cp -rf ${SERVICE_INSTALL}/data/ui-lovelace ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/www && cp -rf ${SERVICE_INSTALL}/data/www ${SERVICE_HOME}
