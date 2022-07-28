#!/bin/sh

SERVICE_HOME=/home/asystem/homeassistant/latest
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/homeassistant/latest

rm -rf ${SERVICE_HOME}/custom_components && cp -rf ${SERVICE_INSTALL}/config/custom_components ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/custom_packages && cp -rf ${SERVICE_INSTALL}/config/custom_packages ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/ui-lovelace && cp -rf ${SERVICE_INSTALL}/config/ui-lovelace ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/www && cp -rf ${SERVICE_INSTALL}/config/www ${SERVICE_HOME}
