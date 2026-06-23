#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

mkdir -p ${SERVICE_HOME}/data
chmod -R 777 ${SERVICE_HOME}/data

# TODO: RE-enable once distruted lock implemented
#docker exec wrangle bash -c 'wrangle --force-reprocessing --enable-uploads'
