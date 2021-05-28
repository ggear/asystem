#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
docker exec -e WRANGLE_REPROCESS_ALL_FILES=true wrangle telegraf --debug --once
