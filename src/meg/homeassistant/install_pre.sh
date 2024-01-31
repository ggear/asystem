#!/bin/sh

SERVICE_HOME=/home/asystem/homeassistant/latest
SERVICE_INSTALL=/var/lib/asystem/install/homeassistant/latest

if [ -f "${SERVICE_HOME}/ip_bans.yaml" ]; then
  echo "New dnsmasq config validated with changes:" && echo "---" && cat "${SERVICE_HOME}/ip_bans.yaml" && echo "---"
  rm -rf "${SERVICE_HOME}/ip_bans.yaml"
fi

rm -rf ${SERVICE_HOME}/custom_components && cp -rf ${SERVICE_INSTALL}/config/custom_components ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/custom_packages && cp -rf ${SERVICE_INSTALL}/config/custom_packages ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/ui-lovelace && cp -rf ${SERVICE_INSTALL}/config/ui-lovelace ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/www && cp -rf ${SERVICE_INSTALL}/config/www ${SERVICE_HOME}
