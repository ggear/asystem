#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

mkdir -p ${SERVICE_HOME}/data
chmod -R 777 ${SERVICE_HOME}/data
docker exec -e WRANGLE_ENABLE_DATA_TRUNC=true -e WRANGLE_DISABLE_DATA_DELTA=true --user root wrangle telegraf --debug --once
