#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

docker exec influxdb_macmini-liz /root/.influxdbv2/setup.sh
