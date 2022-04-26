#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

chmod -R 777 ${SERVICE_HOME}/data
docker exec -e WRANGLE_REPROCESS_ALL_FILES=true --user telegraf wrangle telegraf --debug --once
