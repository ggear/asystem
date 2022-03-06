#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

rm -rf ${SERVICE_HOME}/custom_components && cp -rvf ${SERVICE_INSTALL}/config/custom_components ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/custom_packages && cp -rvf ${SERVICE_INSTALL}/config/custom_packages ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/ui-lovelace && cp -rvf ${SERVICE_INSTALL}/config/ui-lovelace ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/www && cp -rvf ${SERVICE_INSTALL}/config/www ${SERVICE_HOME}
