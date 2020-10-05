#!/bin/sh

cd src/main/resources/config
. ./.profile
. ./.env_prod

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST}:${GRAFANA_PORT}
export DASHBOARD_ASYSTEM_UID=0fcqnVOGz

cd ./grizzly
make dev

cd ../grafonnet-lib
./../grizzly/grr apply ./../dashboards_all.jsonnet
