#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/*$(hostname)*/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit
. ./.env
cd config/grizzly
GOPATH=$SERVICE_HOME/.go make dev
cd ../grafonnet-lib
GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@macmini-liz:3000 ./../grizzly/grr apply ./../dashboards/template/generated/dashboards_all.jsonnet
