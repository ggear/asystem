#!/bin/sh

cd src/main/resources/config
. ./.profile
. ../../../../.env_prod

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST}:${GRAFANA_PORT}

echo $GRAFANA_URL


cd ./grizzly
make dev

cd ../grafonnet-lib
./../grizzly/grr apply ./../dashboards/template/generated/dashboards_all.jsonnet
