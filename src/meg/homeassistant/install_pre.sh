#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest

if [ -f "${SERVICE_HOME}/ip_bans.yaml" ]; then
  echo "Flushing IP bans:" && echo "---" && cat "${SERVICE_HOME}/ip_bans.yaml" && echo "---"
  rm -rf "${SERVICE_HOME}/ip_bans.yaml"
fi

rm -rf ${SERVICE_HOME}/custom_components && cp -rf ${ROOT_DIR}/data/custom_components ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/custom_packages && cp -rf ${ROOT_DIR}/data/custom_packages ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/ui-lovelace && cp -rf ${ROOT_DIR}/data/ui-lovelace ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/www && cp -rf ${ROOT_DIR}/data/www ${SERVICE_HOME}
