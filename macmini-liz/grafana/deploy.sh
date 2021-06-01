#!/bin/sh

. .env
export GRAFANA_URL=http://${GRAFANA_USER}:${GRAFANA_KEY}@${GRAFANA_HOST_PROD}:${GRAFANA_PORT}
cd src/main/resources/libraries/grizzly
make dev
cd ../grafonnet-lib

#curl -XPOST --silent ${GRAFANA_URL}/api/user/using/1 | jq
#./../grizzly/grr apply ./../dashboards/template/generated/dashboards_all.jsonnet

curl -XPOST --silent ${GRAFANA_URL}/api/user/using/2 | jq
./../grizzly/grr apply ./../../config/dashboards/template/private/generated/dashboards_all.jsonnet
