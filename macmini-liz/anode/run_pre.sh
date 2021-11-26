#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
mkdir -p ${SERVICE_HOME}
cp -rvfp ${SERVICE_INSTALL}/.env ${SERVICE_HOME}/.profile
