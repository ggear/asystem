#!/bin/sh

cd src/main/resources/config
. ./.profile
. ../../../../.env_prod

export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST}:${GRAFANA_PORT}?orgId=2

echo $GRAFANA_URL


cd ./grizzly
make dev

cd ../grafonnet-lib
./../grizzly/grr apply ./../dashboards//desktop/generated/dashboards_all.jsonnet
